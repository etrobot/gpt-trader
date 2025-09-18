import logging
import os
import time
from datetime import datetime, date
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Check for proxy configuration  
proxy_url = os.getenv('PROXY_URL')
proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None
if proxy_url:
    logger.info(f"Using proxy: {proxy_url}")

BASE_URL = "https://api.bybit.com/v5"


def get_spot_tickers():
    """获取现货tickers，包含24h成交额等指标，用于按成交额排序"""
    try:
        url = f"{BASE_URL}/market/tickers"
        params = {"category": "spot"}
        response = requests.get(url, params=params, proxies=proxies, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("retCode") == 0:
            items = result["result"]["list"]
            df = pd.DataFrame(items)
            
            # 保留我们需要的字段
            cols = ["symbol", "lastPrice", "highPrice24h", "lowPrice24h", "volume24h", "turnover24h"]
            for c in cols:
                if c not in df.columns:
                    df[c] = None
            
            # 数值字段转成数值类型
            for c in ["lastPrice", "highPrice24h", "lowPrice24h", "volume24h", "turnover24h"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            
            return df[cols]
        else:
            logger.error(f"Failed to get spot tickers: {result.get('retMsg')}")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Exception in get_spot_tickers: {e}")
        return pd.DataFrame()


def get_symbols():
    """获取所有可用的交易对"""
    try:
        url = f"{BASE_URL}/market/instruments-info"
        params = {"category": "spot"}
        response = requests.get(url, params=params, proxies=proxies, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result["retCode"] == 0:
            symbols = result["result"]["list"]
            df = pd.DataFrame(symbols)
            df = df[df["status"] == "Trading"]
            df = df[df["quoteCoin"] == "USDT"]
            df = df[["symbol", "baseCoin", "quoteCoin"]]
            df["name"] = df["baseCoin"] + "/" + df["quoteCoin"]
            return df
        else:
            logger.error(f"Failed to get symbols from Bybit: {result['retMsg']}")
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Exception in get_symbols: {e}")
        return pd.DataFrame()


def get_kline(symbol: str, start_date: date, end_date: date, interval: str = "D") -> pd.DataFrame:
    """获取K线数据 - 简化版本使用直接HTTP请求"""
    try:
        url = f"{BASE_URL}/market/kline"
        params = {
            "category": "spot",
            "symbol": symbol,
            "interval": interval,
            "limit": 200  # 获取最近200条记录
        }
        
        response = requests.get(url, params=params, proxies=proxies, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        if result.get("retCode") == 0 and result["result"]["list"]:
            klines = result["result"]["list"]
            
            df = pd.DataFrame(
                klines,
                columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
            )
            
            # 转换数据类型
            df["date"] = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="ms")
            df["open"] = pd.to_numeric(df["open"])
            df["high"] = pd.to_numeric(df["high"])
            df["low"] = pd.to_numeric(df["low"])
            df["close"] = pd.to_numeric(df["close"])
            df["volume"] = pd.to_numeric(df["volume"])
            df["turnover"] = pd.to_numeric(df["turnover"])
            
            # 按日期排序
            df = df.sort_values("timestamp")
            
            # 计算涨跌幅
            df["change_pct"] = (df["close"].pct_change() * 100).fillna(0)
            
            # 过滤日期范围
            df = df[(df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)]
            
            logger.info(f"Successfully fetched {len(df)} records for {symbol}")
            return df[["date", "open", "high", "low", "close", "volume", "turnover", "change_pct"]]
        else:
            logger.warning(f"No data returned for {symbol}: {result.get('retMsg', 'Unknown error')}")
            return pd.DataFrame()
            
    except Exception as e:
        logger.error(f"Exception in get_kline for {symbol}: {e}")
        return pd.DataFrame()
