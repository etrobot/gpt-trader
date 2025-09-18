from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
from sqlmodel import Session, select
from models import engine, CryptoSymbol, DailyMarketData

logger = logging.getLogger(__name__)


def get_latest_date_from_db() -> Optional[date]:
    """从数据库获取最新的数据日期"""
    with Session(engine) as session:
        latest_db_date = session.exec(
            select(DailyMarketData.date).order_by(DailyMarketData.date.desc()).limit(1)
        ).first()
        return latest_db_date


def get_missing_daily_data(symbols: List[str]) -> Dict[str, date]:
    """检查哪些交易对的日K数据缺失或不完整，返回需要从哪个日期开始补充数据"""
    missing_data = {}

    latest_trade_date = get_latest_date_from_db()
    if not latest_trade_date:
        # 数据库为空，从60天前开始获取
        start_date = date.today() - timedelta(days=60)
        for symbol in symbols:
            missing_data[symbol] = start_date
        return missing_data

    with Session(engine) as session:
        for symbol in symbols:
            # 查询该交易对最新的日期
            stmt = (
                select(DailyMarketData.date)
                .where(DailyMarketData.symbol == symbol)
                .order_by(DailyMarketData.date.desc())
                .limit(1)
            )

            result = session.exec(stmt).first()

            if result is None:
                # 该交易对没有任何数据，从60天前开始获取
                missing_data[symbol] = latest_trade_date - timedelta(days=60)
            else:
                # 检查最新日期是否是最新交易日
                latest_date_for_symbol = result
                if latest_date_for_symbol < latest_trade_date:
                    # 数据不是最新的，从最新日期的下一天开始补充
                    missing_data[symbol] = latest_date_for_symbol + timedelta(days=1)

    return missing_data


def save_daily_data(history_data: Dict[str, pd.DataFrame]):
    """保存日K数据到数据库"""
    total_saved = 0

    with Session(engine) as session:
        for symbol, df in history_data.items():
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                record_date = row["date"].date()
                # 检查是否已存在
                existing = session.exec(
                    select(DailyMarketData).where(
                        DailyMarketData.symbol == symbol,
                        DailyMarketData.date == record_date,
                    )
                ).first()

                if existing is None:
                    daily_data = DailyMarketData(
                        symbol=symbol,
                        date=record_date,
                        open_price=float(row.get("open", 0)),
                        high_price=float(row.get("high", 0)),
                        low_price=float(row.get("low", 0)),
                        close_price=float(row.get("close", 0)),
                        volume=float(row.get("volume", 0)),
                        amount=float(
                            row.get("turnover", 0)
                        ),  # bybit uses turnover for amount
                        change_pct=float(row.get("change_pct", 0)),
                    )
                    session.add(daily_data)
                    total_saved += 1

        session.commit()

    logger.info(f"Saved {total_saved} daily market data records")
    return total_saved


def save_crypto_symbol_info(symbols_data: pd.DataFrame):
    """保存加密货币交易对基本信息"""
    total_saved = 0

    logger.info(f"Starting to save symbol info for {len(symbols_data)} symbols")

    try:
        with Session(engine) as session:
            for _, row in symbols_data.iterrows():
                symbol = row["symbol"]
                name = row.get("name", symbol)

                logger.debug(f"Processing symbol: {symbol}, name: {name}")

                # 检查是否已存在
                existing = session.exec(
                    select(CryptoSymbol).where(CryptoSymbol.symbol == symbol)
                ).first()

                if existing is None:
                    symbol_info = CryptoSymbol(
                        symbol=symbol,
                        name=name,
                    )
                    session.add(symbol_info)
                    total_saved += 1
                    logger.debug(f"Added new symbol: {symbol}")
                elif existing.name != name:
                    # 更新名称
                    existing.name = name
                    existing.updated_at = datetime.now()
                    logger.debug(f"Updated symbol: {symbol}")
                else:
                    logger.debug(f"Symbol {symbol} already exists with same name")

            session.commit()
            logger.info(
                f"Successfully committed {total_saved} symbol records to database"
            )

    except Exception as e:
        logger.error(f"Error in save_crypto_symbol_info: {e}")
        raise

    logger.info(f"Saved/updated {total_saved} crypto symbol info records")
    return total_saved


def load_daily_data_for_analysis(
    symbols: List[str], limit: int = 60
) -> Dict[str, pd.DataFrame]:
    """从数据库加载日K数据用于因子分析"""
    from factors.config import MIN_DATA_POINTS
    
    history_data = {}
    skipped_symbols = []

    with Session(engine) as session:
        for symbol in symbols:
            stmt = (
                select(DailyMarketData)
                .where(DailyMarketData.symbol == symbol)
                .order_by(DailyMarketData.date.desc())
                .limit(limit)
            )

            daily_records = session.exec(stmt).all()
            if daily_records:
                # Check if we have enough data points
                if len(daily_records) < MIN_DATA_POINTS:
                    skipped_symbols.append(symbol)
                    logger.info(f"Skipping {symbol}: only {len(daily_records)} data points, need at least {MIN_DATA_POINTS}")
                    continue
                    
                df = pd.DataFrame([r.dict() for r in daily_records])
                df["date"] = pd.to_datetime(df["date"])
                df = df.rename(
                    columns={
                        "date": "日期",
                        "open_price": "开盘",
                        "high_price": "最高",
                        "low_price": "最低",
                        "close_price": "收盘",
                        "volume": "成交量",
                        "amount": "成交额",
                        "change_pct": "涨跌幅",
                    }
                )
                df = df.sort_values("日期")
                history_data[symbol] = df
            else:
                skipped_symbols.append(symbol)
                logger.info(f"Skipping {symbol}: no data found in database")

    if skipped_symbols:
        logger.info(f"Skipped {len(skipped_symbols)} symbols due to insufficient data: {skipped_symbols[:10]}{'...' if len(skipped_symbols) > 10 else ''}")
    
    logger.info(f"Loaded daily data for {len(history_data)} symbols from database (skipped {len(skipped_symbols)} symbols)")
    return history_data
