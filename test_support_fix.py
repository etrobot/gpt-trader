#!/usr/bin/env python3
"""Test the fixed support factor calculation for SOMIUSDT"""

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import logging
from data_management.crypto_data_manager import load_daily_data_for_analysis
from factors.support import compute_support_with_default_window

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_support_factor():
    """测试修复后的支撑因子计算"""
    print("=== Testing Fixed Support Factor for SOMIUSDT ===")
    
    # 加载SOMIUSDT数据
    history_data = load_daily_data_for_analysis(["SOMIUSDT"], limit=60)
    
    if "SOMIUSDT" not in history_data:
        print("❌ No data for SOMIUSDT")
        return
    
    df = history_data["SOMIUSDT"]
    print(f"Loaded {len(df)} records for SOMIUSDT")
    
    # 计算支撑因子
    try:
        result = compute_support_with_default_window(history_data)
        print(f"✅ Support factor calculation completed")
        print(f"Result shape: {result.shape}")
        
        if not result.empty:
            print("Result:")
            print(result.to_string())
            
            # 检查是否还有NaN值
            if result['支撑因子'].isna().any():
                print("⚠️  Still has NaN values in 支撑因子")
            else:
                print("✅ No NaN values in 支撑因子")
                
            if result['最长K线天数'].isna().any():
                print("⚠️  Still has NaN values in 最长K线天数")
            else:
                print("✅ No NaN values in 最长K线天数")
        else:
            print("❌ Empty result")
            
    except Exception as e:
        print(f"❌ Error calculating support factor: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_support_factor()