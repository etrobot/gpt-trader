#!/usr/bin/env python3
"""Test the complete factor calculation including SOMIUSDT"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import logging
import pandas as pd
from data_management.crypto_data_manager import load_daily_data_for_analysis
from factor import compute_factors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_factor_calculation():
    """测试完整的因子计算流程"""
    print("=== Testing Complete Factor Calculation ===")
    
    # 创建一些测试symbols，包括SOMIUSDT
    test_symbols = ["BTCUSDT", "ETHUSDT", "SOMIUSDT"]
    
    # 创建top_symbols DataFrame
    top_symbols = pd.DataFrame({
        "symbol": test_symbols,
        "name": [f"{s.replace('USDT', '')}/USDT" for s in test_symbols]
    })
    
    print(f"Testing with symbols: {test_symbols}")
    
    # 加载历史数据
    history_data = load_daily_data_for_analysis(test_symbols, limit=60)
    print(f"Loaded data for {len(history_data)} symbols")
    
    for symbol, df in history_data.items():
        print(f"  {symbol}: {len(df)} records")
    
    # 计算因子
    try:
        result = compute_factors(top_symbols, history_data)
        print(f"✅ Factor calculation completed")
        print(f"Result shape: {result.shape}")
        
        if not result.empty:
            print("\nResult columns:", result.columns.tolist())
            print("\nResult:")
            print(result.to_string())
            
            # 检查SOMIUSDT的结果
            somi_row = result[result['symbol'] == 'SOMIUSDT']
            if not somi_row.empty:
                print(f"\n=== SOMIUSDT Results ===")
                for col in result.columns:
                    if col != 'symbol':
                        value = somi_row[col].iloc[0]
                        status = "✅" if pd.notna(value) else "❌ NaN"
                        print(f"  {col}: {value} {status}")
            else:
                print("❌ SOMIUSDT not found in results")
                
        else:
            print("❌ Empty result")
            
    except Exception as e:
        print(f"❌ Error in factor calculation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_factor_calculation()