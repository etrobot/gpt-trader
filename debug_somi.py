#!/usr/bin/env python3
"""Debug script to check SOMIUSDT data issues"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import logging
from datetime import date, timedelta
import pandas as pd
from sqlmodel import Session, select
from models import engine, DailyMarketData
from market_data.bybit_api import get_kline, get_symbols
from data_management.crypto_data_manager import load_daily_data_for_analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_somi_in_database():
    """检查SOMIUSDT在数据库中的数据"""
    print("=== Checking SOMIUSDT in Database ===")
    
    with Session(engine) as session:
        # 查询SOMIUSDT的所有数据
        stmt = (
            select(DailyMarketData)
            .where(DailyMarketData.symbol == "SOMIUSDT")
            .order_by(DailyMarketData.date.desc())
        )
        
        records = session.exec(stmt).all()
        print(f"Found {len(records)} records for SOMIUSDT in database")
        
        if records:
            print("Latest 5 records:")
            for i, record in enumerate(records[:5]):
                print(f"  {i+1}. Date: {record.date}, Close: {record.close_price}, Volume: {record.volume}")
        else:
            print("No data found for SOMIUSDT in database")
    
    return records

def check_somi_api():
    """检查SOMIUSDT的API数据"""
    print("\n=== Checking SOMIUSDT API ===")
    
    # 检查SOMI是否在可用symbols中
    symbols_df = get_symbols()
    somi_symbols = symbols_df[symbols_df['symbol'].str.contains('SOMI', case=False, na=False)]
    print(f"SOMI-related symbols: {somi_symbols['symbol'].tolist() if not somi_symbols.empty else 'None found'}")
    
    # 尝试获取SOMIUSDT的K线数据
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    print(f"Trying to fetch SOMIUSDT data from {start_date} to {end_date}")
    kline_data = get_kline("SOMIUSDT", start_date, end_date)
    
    print(f"API returned {len(kline_data)} records")
    if not kline_data.empty:
        print("Sample data:")
        print(kline_data.head().to_string())
    else:
        print("No data returned from API")
    
    return kline_data

def check_loaded_data():
    """检查通过load_daily_data_for_analysis加载的数据"""
    print("\n=== Checking Loaded Data for Analysis ===")
    
    history_data = load_daily_data_for_analysis(["SOMIUSDT"], limit=60)
    
    if "SOMIUSDT" in history_data:
        df = history_data["SOMIUSDT"]
        print(f"Loaded {len(df)} records for SOMIUSDT")
        print("Columns:", df.columns.tolist())
        print("Sample data:")
        print(df.head().to_string())
        
        # 检查数据质量
        print("\nData Quality Check:")
        print(f"Date range: {df['日期'].min()} to {df['日期'].max()}")
        print(f"Null values: {df.isnull().sum().to_dict()}")
        print(f"Zero values in price columns:")
        for col in ['开盘', '收盘', '最高', '最低']:
            if col in df.columns:
                zero_count = (df[col] == 0).sum()
                print(f"  {col}: {zero_count} zeros")
    else:
        print("SOMIUSDT not found in loaded data")
    
    return history_data.get("SOMIUSDT")

def analyze_support_factor_requirements():
    """分析支撑因子的计算要求"""
    print("\n=== Analyzing Support Factor Requirements ===")
    
    df = check_loaded_data()
    if df is None or df.empty:
        print("No data available for analysis")
        return
    
    # 检查支撑因子计算的要求
    window_size = 30  # 默认窗口大小
    required_records = window_size + 1
    
    print(f"Support factor requires {required_records} records (window_size={window_size} + 1)")
    print(f"Available records: {len(df)}")
    
    if len(df) < required_records:
        print(f"❌ Insufficient data: need {required_records}, have {len(df)}")
    else:
        print(f"✅ Sufficient data available")
        
        # 检查必要列
        required_columns = ["日期", "开盘", "收盘", "最高", "最低"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ Missing required columns: {missing_columns}")
        else:
            print(f"✅ All required columns present")
            
            # 检查数据质量
            for col in required_columns[1:]:  # 跳过日期列
                null_count = df[col].isnull().sum()
                zero_count = (df[col] == 0).sum()
                if null_count > 0:
                    print(f"⚠️  {col} has {null_count} null values")
                if zero_count > 0:
                    print(f"⚠️  {col} has {zero_count} zero values")

if __name__ == "__main__":
    try:
        # 检查数据库中的数据
        db_records = check_somi_in_database()
        
        # 检查API数据
        api_data = check_somi_api()
        
        # 检查加载的数据
        loaded_data = check_loaded_data()
        
        # 分析支撑因子要求
        analyze_support_factor_requirements()
        
    except Exception as e:
        logger.error(f"Error in debug script: {e}")
        import traceback
        traceback.print_exc()