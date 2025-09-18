import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import date
from market_data.bybit_api import get_kline

# 获取BTCUSDT的K线数据
df = get_kline("BTCUSDT", date(2025, 9, 1), date(2025, 9, 8))
print("K线数据:")
print(df)
print()
print("数据列:")
print(df.columns.tolist())
print()
print("涨跌幅列:")
print(df["change_pct"])
