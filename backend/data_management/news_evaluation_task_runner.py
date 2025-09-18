from __future__ import annotations
import logging
import threading
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

import openai
import pandas as pd
from sqlmodel import Session

from models import Task, TaskStatus, engine
from utils import (
    get_task,
    update_task_progress,
    set_last_completed_task,
)
from market_data import fetch_top_symbols_by_turnover
from news_data import fetch_crypto_news, NewsItem
from llm_utils import evaluate_content_with_llm
from config.evaluation_criteria import CRYPTO_EVALUATION_CRITERIA, CATEGORY

logger = logging.getLogger(__name__)


def run_news_evaluation_task(
    task_id: str,
    top_n: int = 10,
    news_per_symbol: int = 3,
    openai_model: str = "gpt-oss-120b",
    stop_event: Optional[threading.Event] = None,
):
    """
    运行新闻评估任务：获取最新一天成交额top10的加密货币资讯并评估

    Args:
        task_id: 任务ID
        top_n: 获取前N个成交额最高的币种
        news_per_symbol: 每个币种获取的新闻数量
        openai_model: 使用的OpenAI模型
        stop_event: 停止事件
    """

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
        update_task_progress(task_id, 0.0, "开始新闻评估任务")

        # Step 1: 获取成交额Top交易对
        update_task_progress(task_id, 0.1, f"获取成交额Top {top_n} 交易对")
        if check_cancel():
            return

        top_symbols_df = fetch_top_symbols_by_turnover(top_n)
        if top_symbols_df.empty:
            raise Exception("Failed to fetch top symbols by turnover from Bybit.")

        symbols_to_process = top_symbols_df["symbol"].tolist()
        logger.info(
            f"Selected top {len(symbols_to_process)} symbols: {symbols_to_process}"
        )

        # Step 2: 获取新闻数据
        update_task_progress(
            task_id, 0.2, f"获取 {len(symbols_to_process)} 个币种的新闻数据"
        )
        if check_cancel():
            return

        news_by_symbol = fetch_crypto_news(symbols_to_process, limit=news_per_symbol)

        # 统计获取到的新闻数量
        total_news = sum(len(news_list) for news_list in news_by_symbol.values())
        logger.info(f"获取到总计 {total_news} 条新闻")

        # Step 3: 评估新闻内容
        update_task_progress(task_id, 0.3, "开始评估新闻内容")
        if check_cancel():
            return

        evaluation_results = []

        # 使用统一的评估标准
        criteria_dict = CRYPTO_EVALUATION_CRITERIA

        for i, (symbol, news_list) in enumerate(news_by_symbol.items()):
            if check_cancel():
                return

            progress = 0.3 + (0.6 * i / len(news_by_symbol))
            update_task_progress(
                task_id,
                progress,
                f"评估 {symbol} 新闻内容 ({i+1}/{len(news_by_symbol)})",
            )

            if not news_list:
                # 没有新闻数据的情况
                evaluation_results.append(
                    {
                        "symbol": symbol,
                        "base_coin": (
                            symbol.replace("USDT", "")
                            if symbol.endswith("USDT")
                            else symbol
                        ),
                        "news_count": 0,
                        "evaluation": {
                            "overall_score": 0,
                            "detailed_scores": {},
                            "top_scoring_criterion": "无数据",
                            "top_score": 0,
                        },
                        "news_summary": "未获取到相关新闻",
                        "error": "无新闻数据",
                    }
                )
                continue

            try:
                # 合并所有新闻内容
                combined_content = _combine_news_content(news_list)

                # 使用LLM评估
                evaluation = evaluate_content_with_llm(
                    model=openai_model,
                    content=combined_content,
                    criteria_dict=criteria_dict,
                    category=CATEGORY
                )
                
                # 调试日志
                logger.info(f"{symbol} 评估结果: {evaluation}")

                # 构建结果
                result = {
                    "symbol": symbol,
                    "base_coin": (
                        symbol.replace("USDT", "")
                        if symbol.endswith("USDT")
                        else symbol
                    ),
                    "news_count": len(news_list),
                    "evaluation": evaluation,
                    "news_summary": _create_news_summary(news_list),
                    "news_items": [_news_item_to_dict(item) for item in news_list],
                }

                evaluation_results.append(result)
                logger.info(
                    f"完成 {symbol} 评估，总分: {evaluation['overall_score']:.1f}"
                )

            except Exception as e:
                logger.error(f"评估 {symbol} 时出错: {e}")
                evaluation_results.append(
                    {
                        "symbol": symbol,
                        "base_coin": (
                            symbol.replace("USDT", "")
                            if symbol.endswith("USDT")
                            else symbol
                        ),
                        "news_count": len(news_list),
                        "evaluation": {
                            "overall_score": 0,
                            "detailed_scores": {},
                            "top_scoring_criterion": "评估失败",
                            "top_score": 0,
                        },
                        "news_summary": _create_news_summary(news_list),
                        "error": str(e),
                    }
                )

        # Step 4: 排序和整理结果
        update_task_progress(task_id, 0.95, "整理评估结果")
        if check_cancel():
            return

        # 按总分排序
        evaluation_results.sort(
            key=lambda x: x["evaluation"]["overall_score"], reverse=True
        )

        # 生成旭日图数据
        logger.info(f"开始生成旭日图数据，评估结果数量: {len(evaluation_results)}")
        sunburst_data = _generate_sunburst_data(evaluation_results)
        logger.info(f"旭日图数据生成完成: {sunburst_data}")

        # 构建最终结果
        result = {
            "data": evaluation_results,
            "count": len(evaluation_results),
            "sunburst_data": sunburst_data,  # 新增旭日图数据
            "summary": {
                "total_symbols": len(symbols_to_process),
                "total_news": total_news,
                "evaluation_model": openai_model,
                "top_performer": evaluation_results[0] if evaluation_results else None,
                "average_score": (
                    sum(r["evaluation"]["overall_score"] for r in evaluation_results)
                    / len(evaluation_results)
                    if evaluation_results
                    else 0
                ),
            },
        }

        # Step 5: 完成任务
        task.status = TaskStatus.COMPLETED
        task.progress = 1.0
        task.message = (
            f"新闻评估完成，共评估 {result['count']} 个币种，{total_news} 条新闻"
        )
        task.completed_at = datetime.now().isoformat()
        task.result = result
        set_last_completed_task(task)
        from utils import bump_task_version

        bump_task_version(task_id)
        logger.info(f"News evaluation task {task_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}", exc_info=True)
        task.status = TaskStatus.FAILED
        task.message = f"任务失败: {e}"
        task.completed_at = datetime.now().isoformat()
        task.error = str(e)
        from utils import bump_task_version

        bump_task_version(task_id)


def _combine_news_content(news_list: List[NewsItem]) -> str:
    """合并新闻内容用于评估"""
    combined = []
    for news in news_list:
        combined.append(f"标题: {news.title}")
        combined.append(f"内容: {news.content}")
        combined.append(f"来源: {news.source}")
        combined.append("---")

    return "\n".join(combined)


def _create_news_summary(news_list: List[NewsItem]) -> str:
    """创建新闻摘要"""
    if not news_list:
        return "无新闻数据"

    titles = [news.title for news in news_list]
    return (
        f"共{len(news_list)}条新闻: "
        + "; ".join(titles[:3])
        + ("..." if len(titles) > 3 else "")
    )


def _news_item_to_dict(news_item: NewsItem) -> Dict[str, Any]:
    """将NewsItem转换为字典"""
    return {
        "title": news_item.title,
        "content": news_item.content,
        "url": news_item.url,
        "published_at": news_item.published_at,
        "source": news_item.source,
        "symbol": news_item.symbol,
    }


def _generate_sunburst_data(evaluation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    生成旭日图数据结构，基于LLM返回的category分类
    
    结构：
    - 根节点：加密货币评估（所有分类的总分）
      - 第一层：币种分类（从LLM返回的category字段获取）
        - 第二层：具体币种（该币种的总体评分）
    """
    if not evaluation_results:
        return {"name": "加密货币评估", "children": []}
    
    # 按分类组织数据
    categories_data = {}
    
    # 处理每个币种的评估结果
    for result in evaluation_results:
        symbol = result["base_coin"]
        criteria_result = result["evaluation"].get("criteria_result", {})
        overall_score = result["evaluation"].get("overall_score", 0)
        
        # 从LLM返回结果中获取分类
        category = criteria_result.get("category", "未分类")
        
        logger.info(f"处理币种 {symbol}, LLM分类: {category}, 总分: {overall_score}")
        
        # 初始化分类数据
        if category not in categories_data:
            categories_data[category] = []
        
        # 添加币种数据（使用总体评分）
        if overall_score > 0:
            categories_data[category].append({
                "name": symbol,
                "value": round(overall_score, 1)
            })
    
    # 构建旭日图数据结构
    children = []
    total_value = 0
    
    for category_name, coins in categories_data.items():
        if coins:  # 只添加有数据的分类
            # 按分数排序
            coins.sort(key=lambda x: x["value"], reverse=True)
            
            # 计算该分类的总分（所有币种的总分之和）
            category_total = sum(coin["value"] for coin in coins)
            total_value += category_total
            
            children.append({
                "name": category_name,
                "value": round(category_total, 1),
                "children": coins
            })
    
    # 按分类总分排序
    children.sort(key=lambda x: x["value"], reverse=True)
    
    total_coins = sum(len(category["children"]) for category in children)
    logger.info(f"生成旭日图数据: {len(children)} 个分类, 总计 {total_coins} 个数据点, 总分值: {total_value}")
    
    return {
        "name": "加密货币评估",
        "value": round(total_value, 1),
        "children": children
    }
