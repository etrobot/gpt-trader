#!/usr/bin/env python3
"""
Freqtrade 下单测试脚本
使用方法: python test_freqtrade_orders.py
"""
import sys
import os

# 设置环境变量指向本地 Freqtrade
os.environ['FREQTRADE_API_URL'] = 'http://localhost:6677'
os.environ['FREQTRADE_API_USERNAME'] = 'admin_sZMy4aD6'
os.environ['FREQTRADE_API_PASSWORD'] = 'zMMfUzubhWluBcUxhwk3SkLt'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from freqtrade_client import health, list_open_trades, forceentry
from trade_signal_executor import execute_signals

def quick_test():
    """快速测试 Freqtrade 连接和下单"""
    print("🔗 测试 Freqtrade 连接...")
    
    if not health():
        print("❌ Freqtrade API 连接失败")
        return False
    
    print("✅ 连接成功")
    
    # 显示当前持仓
    trades = list_open_trades()
    print(f"📊 当前持仓: {len(trades)} 个")
    
    # 测试一个买入信号
    print("📤 发送测试买入信号: BTC/USDT")
    result = forceentry("BTC/USDT", 5.0)
    
    if result:
        print("✅ 买入信号发送成功")
    else:
        print("❌ 买入信号发送失败")
    
    return result

if __name__ == "__main__":
    quick_test()