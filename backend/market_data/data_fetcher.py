from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd
from utils import update_task_progress
from .bybit_api import get_symbols, get_kline, get_spot_tickers

logger = logging.getLogger(__name__)


def fetch_symbols() -> pd.DataFrame:
    """Fetch all available symbols from Bybit"""
    logger.info("Fetching all symbols from Bybit...")
    df = get_symbols()
    if (
        "symbol" in df.columns
        and "baseCoin" in df.columns
        and "quoteCoin" in df.columns
    ):
        df["name"] = (
            df.get("name")
            if "name" in df.columns
            else (df["baseCoin"] + "/" + df["quoteCoin"])
        )
    logger.info(f"Successfully fetched {len(df)} symbols from Bybit")
    return df


def fetch_top_symbols_by_turnover(top_n: int = 50) -> pd.DataFrame:
    """获取按24小时成交额排序的前N个交易对（USDT现货）"""
    logger.info(f"Fetching top {top_n} symbols by 24h turnover from Bybit...")
    tickers = get_spot_tickers()
    if tickers.empty:
        logger.warning("Tickers empty, fallback to all symbols (unsorted)")
        all_symbols = fetch_symbols()
        return all_symbols.head(top_n)

    # 保留USDT计价的交易对（Bybit现货symbols本身是形如 'BTCUSDT'，tickers不直接给quote）
    # 这里用简单规则：以USDT结尾，但排除稳定币对稳定币的交易对
    tickers = tickers[tickers["symbol"].str.endswith("USDT", na=False)].copy()
    
    if tickers.empty:
        logger.warning("No USDT spot tickers found, fallback to head")
        all_symbols = fetch_symbols()
        return all_symbols.head(top_n)

    # 按24h成交额排序
    tickers = tickers.sort_values("turnover24h", ascending=False)
    top = tickers.head(top_n).copy()

    # 加入name列（BASE/USDT）
    top["baseCoin"] = top["symbol"].str.replace("USDT", "", regex=False)
    top["quoteCoin"] = "USDT"
    top["name"] = top["baseCoin"] + "/" + top["quoteCoin"]

    # 只返回和get_symbols一致的关键列
    return top[["symbol", "baseCoin", "quoteCoin", "name"]]


def fetch_history(
    symbols: List[str],
    start_date: date,
    end_date: date,
    task_id: Optional[str] = None,
    interval: str = "D",
) -> Dict[str, pd.DataFrame]:
    """Fetch historical k-line data for multiple symbols"""
    import time

    history: Dict[str, pd.DataFrame] = {}
    logger.info(f"Fetching historical data for {len(symbols)} symbols from {start_date} to {end_date}")

    for i, symbol in enumerate(symbols):
        if task_id:
            progress = 0.2 + (0.5 * i / len(symbols))
            update_task_progress(task_id, progress, f"获取历史数据 {i+1}/{len(symbols)}: {symbol}")

        try:
            df = get_kline(symbol, start_date, end_date, interval=interval)
            if not df.empty:
                df["symbol"] = symbol
                history[symbol] = df
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")

        # 简单的延迟控制
        if i < len(symbols) - 1:
            time.sleep(0.2)

    logger.info(f"Successfully fetched historical data for {len(history)}/{len(symbols)} symbols")
    return history



