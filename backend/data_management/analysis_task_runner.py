from __future__ import annotations
import logging
import threading
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import json
import os

import numpy as np
import pandas as pd
from sqlmodel import Session, select, func

from models import Task, TaskStatus, engine, DailyMarketData
from utils import (
    get_task,
    update_task_progress,
    set_last_completed_task,
)
from market_data import (
    fetch_symbols,
    fetch_history,
    fetch_top_symbols_by_turnover,
)
from factor import compute_factors
from .crypto_data_manager import (
    save_daily_data,
    save_crypto_symbol_info,
    load_daily_data_for_analysis
)

logger = logging.getLogger(__name__)


def run_analysis_task(
    task_id: str,
    top_n: int,
    selected_factors: Optional[List[str]] = None,
    collect_latest_data: bool = True,
    stop_event: Optional[threading.Event] = None,
):
    """The main crypto analysis task runner"""

    task = get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return

    def check_cancel() -> bool:
        if stop_event is not None and stop_event.is_set():
            task.status = TaskStatus.CANCELLED
            task.message = "任务已取消"
            task.completed_at = datetime.now().isoformat()
            logger.info(f"Task {task_id} cancelled by user")
            from utils import bump_task_version

            bump_task_version(task_id)
            return True
        return False

    try:
        task.status = TaskStatus.RUNNING
        from utils import bump_task_version

        bump_task_version(task_id)
        update_task_progress(task_id, 0.0, "开始分析任务")

        # Step 1: 获取成交额Top交易对，避免遍历所有交易对
        update_task_progress(task_id, 0.05, "获取成交额Top交易对")
        if check_cancel():
            return

        if collect_latest_data:
            # 当需要采集最新数据时，从Bybit API获取Top交易对
            top_symbols_df = fetch_top_symbols_by_turnover(top_n)
            if top_symbols_df.empty:
                raise Exception("Failed to fetch top symbols by turnover from Bybit.")
        else:
            # 当不需要采集最新数据时，直接使用数据库中有数据的交易对
            from sqlmodel import Session, select, func
            from models import DailyMarketData, engine

            with Session(engine) as session:
                # 获取数据库中有数据的交易对，按数据量排序
                stmt = (
                    select(
                        DailyMarketData.symbol,
                        func.count(DailyMarketData.symbol).label("count"),
                    )
                    .group_by(DailyMarketData.symbol)
                    .order_by(func.count(DailyMarketData.symbol).desc())
                    .limit(top_n)
                )
                results = session.exec(stmt).all()

                if not results:
                    raise Exception("No historical data found in database.")

                # 构造top_symbols_df
                symbols_data = []
                for symbol, count in results:
                    base_coin = (
                        symbol.replace("USDT", "")
                        if symbol.endswith("USDT")
                        else symbol
                    )
                    symbols_data.append(
                        {
                            "symbol": symbol,
                            "baseCoin": base_coin,
                            "quoteCoin": "USDT",
                            "name": f"{base_coin}/USDT",
                        }
                    )

                top_symbols_df = pd.DataFrame(symbols_data)
                logger.info(
                    f"Using {len(top_symbols_df)} symbols from database with historical data"
                )

        # Step 2: 保存交易对信息（仅Top列表）
        update_task_progress(task_id, 0.1, "保存交易对信息")
        if check_cancel():
            return
        save_crypto_symbol_info(top_symbols_df)

        # Step 3: 确认要处理的列表
        update_task_progress(task_id, 0.15, "筛选热门交易对")
        if check_cancel():
            return
        symbols_to_process = top_symbols_df["symbol"].tolist()
        logger.info(
            f"Selected top {len(symbols_to_process)} symbols to process by 24h turnover."
        )

        # Use daily data only
        interval = "D"
        days_back = 90  # 3 months for daily data
        period_name = "日"

        # Step 4-6: 获取K线数据
        if collect_latest_data:
            if check_cancel():
                return
            # 排除稳定币对稳定币的交易对，这些对技术分析意义不大
            from config.evaluation_criteria import STABLECOIN_PAIRS
            symbols_to_process = [s for s in symbols_to_process if s not in STABLECOIN_PAIRS]
            today = date.today()
            start_date = today - timedelta(days=days_back)
            update_task_progress(
                task_id,
                0.25,
                f"获取{period_name}K线（近{days_back}天，共 {len(symbols_to_process)} 个交易对）",
            )

            try:
                history_1h = fetch_history(
                    symbols_to_process,
                    start_date,
                    today,
                    task_id=task_id,
                    interval=interval,
                )

                # 检查是否获取到数据
                if not history_1h:
                    logger.warning("未获取到任何历史数据，尝试从数据库加载")
                    history_for_factors = load_daily_data_for_analysis(
                        symbols_to_process, limit=days_back
                    )
                else:
                    # 入库数据
                    update_task_progress(task_id, 0.4, f"保存{period_name}K线到数据库")
                    try:
                        saved_count = save_daily_data(history_1h)
                        logger.info(f"成功保存 {saved_count} 条{period_name}线数据")
                    except Exception as e:
                        logger.error(f"保存{period_name}数据失败: {e}")
                        # 保存失败不应该导致整个任务失败，继续使用获取到的数据
                    history_for_factors = history_1h

            except Exception as e:
                logger.error(f"获取历史数据失败: {e}")
                # 如果获取失败，尝试从数据库加载现有数据
                update_task_progress(
                    task_id, 0.35, "获取数据失败，从数据库加载现有数据"
                )
                history_for_factors = load_daily_data_for_analysis(
                    symbols_to_process, limit=days_back
                )
        else:
            # 从数据库加载数据用于计算
            history_for_factors = load_daily_data_for_analysis(
                symbols_to_process, limit=days_back
            )

        # Step 7: 准备数据进行因子计算
        update_task_progress(task_id, 0.7, "加载数据进行因子计算")
        if check_cancel():
            return

        # Step 8: Compute factors
        factor_msg = f"计算{'选定' if selected_factors else '所有'}因子"
        update_task_progress(task_id, 0.85, factor_msg)
        if check_cancel():
            return

        # We need a dataframe with 'symbol' and 'name' for compute_factors
        top_symbols_for_factors = top_symbols_df[
            top_symbols_df["symbol"].isin(symbols_to_process)
        ]

        df = compute_factors(
            top_symbols_for_factors,
            history_for_factors,
            task_id=task_id,
            selected_factors=selected_factors,
        )

        update_task_progress(task_id, 0.95, "数据清理和格式化")
        if check_cancel():
            return

        if not df.empty:
            df = df.replace({np.nan: None})
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                df[col] = df[col].astype(float, errors="ignore")

        data = df.to_dict(orient="records") if not df.empty else []

        result = {
            "data": data,
            "count": len(data),
            "extended": None,  # Removed extended analysis for now
        }

        # Step 9: Complete the task
        task.status = TaskStatus.COMPLETED
        task.progress = 1.0
        task.message = f"分析完成，共 {result['count']} 条结果"
        task.completed_at = datetime.now().isoformat()
        task.result = result
        set_last_completed_task(task)

        # 保存结果到ranking.json文件
        try:
            # 确保目录存在
            os.makedirs("data_management", exist_ok=True)
            ranking_file_path = "data_management/ranking.json"

            # 准备要保存的数据
            ranking_data = {
                "task_id": task_id,
                "completed_at": task.completed_at,
                "count": result['count'],
                "data": data
            }

            # 保存到JSON文件
            with open(ranking_file_path, 'w', encoding='utf-8') as f:
                json.dump(ranking_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Analysis results saved to {ranking_file_path}")
        except Exception as e:
            logger.error(f"Failed to save ranking.json: {e}")

        from utils import bump_task_version

        bump_task_version(task_id)
        logger.info(f"Analysis task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        task.status = TaskStatus.FAILED
        task.message = f"任务失败: {e}"
        task.completed_at = datetime.now().isoformat()
        task.error = str(e)
        from utils import bump_task_version

        bump_task_version(task_id)
