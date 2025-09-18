from __future__ import annotations

from typing import Dict, Optional, List
import pandas as pd
import numpy as np

from models import Factor
from .config import DEFAULT_WINDOW_SIZE, MIN_DATA_POINTS


def find_longest_candle(candles, window_size):
    """找到窗口内实体最长的K线及其长度"""
    # 取最后 window_size+1 根K线，这样窗口内的每根K线都有昨收数据
    # 实际分析的是最后 window_size 根K线
    extended_window = candles[-(window_size + 1) :]

    # 找到最大实体的索引（使用相对昨收的幅度）
    # 从索引1开始，因为索引0是用来提供昨收数据的
    # 从后往前遍历，这样相同长度时会选择最近的K线
    max_body_length = 0
    max_body_idx = 1  # 默认第一个可用索引

    for i in range(len(extended_window) - 1, 0, -1):  # 从后往前遍历
        body_length = calculate_relative_body_length(extended_window, i)
        if (
            body_length > max_body_length
        ):  # > 确保找到真正的最大值，从后往前所以最近的会被选中
            max_body_length = body_length
            max_body_idx = i

    # 返回最大实体长度和其索引
    return max_body_length, max_body_idx


def calculate_relative_body_length(window, idx):
    """计算K线实体相对昨收的幅度"""
    candle = window[idx]

    # 计算实体长度
    body_length_ratio = int(
        abs(candle["close"] - candle["open"]) * 100 / window[-1]["close"]
    )
    return body_length_ratio


def compute_support(
    history: Dict[str, pd.DataFrame],
    top_spot: Optional[pd.DataFrame] = None,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> pd.DataFrame:
    """Calculate support factor using the new formula: (后半部分最低价 - 前半部分最低价) / abs(最大长度K线长度)

    Args:
        history: Historical price data
        top_spot: Optional spot data (unused)
        window_size: Number of days to look back for analysis (default: 60)
    """
    rows: List[dict] = []

    for symbol, df in history.items():
        # Require at least MIN_DATA_POINTS days for meaningful analysis (extra day for previous close)
        if df is None or df.empty or len(df) < MIN_DATA_POINTS:
            continue

        # 确保DataFrame有正确的列名
        df_copy = df.copy()
        if "date" in df_copy.columns:
            df_copy = df_copy.rename(columns={"date": "日期"})
        if "open" in df_copy.columns:
            df_copy = df_copy.rename(columns={"open": "开盘"})
        if "close" in df_copy.columns:
            df_copy = df_copy.rename(columns={"close": "收盘"})
        if "high" in df_copy.columns:
            df_copy = df_copy.rename(columns={"high": "最高"})
        if "low" in df_copy.columns:
            df_copy = df_copy.rename(columns={"low": "最低"})

        # 检查必要的列是否存在
        required_columns = ["日期", "开盘", "收盘", "最高", "最低"]
        if not all(col in df_copy.columns for col in required_columns):
            continue

        # Convert date column to datetime for proper sorting if needed
        if not pd.api.types.is_datetime64_any_dtype(df_copy["日期"]):
            df_copy["日期"] = pd.to_datetime(df_copy["日期"])

        df_sorted = df_copy.sort_values("日期", ascending=True)

        # Convert DataFrame to list of candle dictionaries
        candles = []
        for _, row in df_sorted.iterrows():
            candles.append(
                {
                    "open": row["开盘"],
                    "close": row["收盘"],
                    "high": row["最高"],
                    "low": row["最低"],
                }
            )

        # We need window_size + 1 candles to have proper previous close for all window candles
        actual_window = min(window_size, len(candles) - 1)

        # 获取窗口内的K线数据
        window_candles = candles[-actual_window:]

        # 如果窗口数据不足，跳过
        if len(window_candles) < 2:
            continue

        # 找到窗口内实体最长的K线
        max_body_length, max_body_idx = find_longest_candle(candles, actual_window)

        # 如果没有找到有效的最长K线，跳过
        if max_body_length == 0:
            continue

        # 将窗口分为前后两部分
        half_window = len(window_candles) // 2
        first_half = window_candles[:half_window]
        second_half = window_candles[half_window:]

        # 计算前半部分和后半部分的最低价
        first_half_low = (
            min(candle["low"] for candle in first_half) if first_half else float("inf")
        )
        second_half_low = (
            min(candle["low"] for candle in second_half)
            if second_half
            else float("inf")
        )

        # 计算支持因子：(后半部分最低价 - 前半部分最低价) / abs(最大长度K线长度)
        # 值越大越好
        support_factor = (
            (second_half_low - first_half_low) / abs(max_body_length)
            if max_body_length != 0
            else 0
        )

        # 计算最长K线天数（从最新K线到最长K线的天数）
        days_from_longest = len(candles) - max_body_idx - 1  # 调整索引计算

        rows.append(
            {
                "symbol": symbol,
                "支撑因子": support_factor,
                f"最长K线天数_{window_size}日": days_from_longest,
            }
        )

    return pd.DataFrame(rows)


# Configuration is now imported from config.py


def compute_support_with_default_window(
    history: Dict[str, pd.DataFrame], top_spot: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """Wrapper function that uses the default window size"""
    result = compute_support(history, top_spot, DEFAULT_WINDOW_SIZE)

    # Rename the dynamic column to a fixed name for the factor definition
    dynamic_col = f"最长K线天数_{DEFAULT_WINDOW_SIZE}日"
    if dynamic_col in result.columns:
        result = result.rename(columns={dynamic_col: "最长K线天数"})

    return result


SUPPORT_FACTOR = Factor(
    id="support",
    name="支撑因子",
    description=f"基于价格变化的支持强度：计算{DEFAULT_WINDOW_SIZE}日窗口内(后半部分最低价 - 前半部分最低价) / abs(最大长度K线长度)，值越大越好",
    columns=[
        {"key": "支撑因子", "label": "支撑因子", "type": "number", "sortable": True},
        {"key": "支撑评分", "label": "支撑评分", "type": "score", "sortable": True},
        {
            "key": "最长K线天数",
            "label": f"最长K线天数({DEFAULT_WINDOW_SIZE}日)",
            "type": "number",
            "sortable": True,
        },
    ],
    compute=lambda history, top_spot=None: compute_support_with_default_window(
        history, top_spot
    ),
)

MODULE_FACTORS = [SUPPORT_FACTOR]
