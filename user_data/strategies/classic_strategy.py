# K线形态交易策略 - 基于连续阳线/阴线模式
# 转换自 App/candlestick_strategy.py 的核心逻辑

from freqtrade.strategy import IStrategy
import pandas as pd
import numpy as np
import talib.abstract as ta
from typing import Optional


class ClassicStrategy(IStrategy):
    """
    K线形态策略：
    1. 连续3阳线后震荡10根K线 -> 买入信号
    2. 连续2阳线（宽松条件）-> 买入信号
    3. 持仓7根K线后 -> 卖出信号
    """

    # 策略基本参数
    INTERFACE_VERSION = 3
    timeframe = "5m"

    def __init__(self, config: dict):
        super().__init__(config)
        if 'timeframe' in config:
            self.timeframe = config['timeframe']

    # ROI表 - 7根K线后退出约35分钟
    minimal_roi = {
        "0": 0.02,      # 2%盈利目标
        "35": 0.01,     # 35分钟后1%
        "70": 0.005,    # 70分钟后0.5%
        "140": 0        # 140分钟后保本
    }

    # 止损
    stoploss = -0.05  # 5%止损

    # 交易参数
    startup_candle_count: int = 50
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """添加K线形态指标"""
        # 基础K线类型
        dataframe['is_bullish'] = dataframe['close'] > dataframe['open']
        dataframe['is_bearish'] = dataframe['close'] < dataframe['open']

        # K线实体大小
        dataframe['candle_body'] = abs(dataframe['close'] - dataframe['open'])
        dataframe['candle_body_pct'] = dataframe['candle_body'] / dataframe['open'] * 100

        # 连续阳线/阴线计数
        dataframe['consecutive_bullish'] = self._count_consecutive_candles(dataframe, 'is_bullish')
        dataframe['consecutive_bearish'] = self._count_consecutive_candles(dataframe, 'is_bearish')

        # 震荡走势检测
        dataframe['is_sideways'] = self._detect_sideways_movement(dataframe)

        # 核心形态信号
        dataframe['pattern_3bull_sideways'] = self._check_pattern_three_bullish_then_sideways(dataframe)
        dataframe['pattern_simple_bull'] = self._check_simple_bullish_pattern(dataframe)

        # 辅助技术指标
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ema_20'] = ta.EMA(dataframe, timeperiod=20)

        return dataframe

    def _count_consecutive_candles(self, dataframe: pd.DataFrame, column: str) -> pd.Series:
        """计算连续K线数量"""
        result = pd.Series(0, index=dataframe.index)
        for i in range(len(dataframe)):
            if i == 0:
                result.iloc[i] = 1 if dataframe[column].iloc[i] else 0
            else:
                if dataframe[column].iloc[i]:
                    result.iloc[i] = result.iloc[i-1] + 1 if dataframe[column].iloc[i-1] else 1
                else:
                    result.iloc[i] = 0
        return result

    def _detect_sideways_movement(self, dataframe: pd.DataFrame, lookback: int = 10) -> pd.Series:
        """检测震荡走势"""
        result = pd.Series(False, index=dataframe.index)
        for i in range(lookback + 3, len(dataframe)):
            # 最近10根K线的最大实体
            recent_bodies = dataframe['candle_body'].iloc[i-lookback:i]
            max_recent_body = recent_bodies.max()

            # 参考期实体大小（第11-13根K线）
            reference_bodies = dataframe['candle_body'].iloc[i-lookback-3:i-lookback]
            min_reference_body = reference_bodies.min()

            # 震荡判断：最近最大实体 < 参考最小实体
            result.iloc[i] = max_recent_body < min_reference_body
        return result

    def _check_pattern_three_bullish_then_sideways(self, dataframe: pd.DataFrame) -> pd.Series:
        """检查3阳线+10震荡形态"""
        result = pd.Series(False, index=dataframe.index)
        for i in range(13, len(dataframe)):
            # 检查第i-12到i-10位置的连续3阳线
            three_bull_start = i - 12
            three_bull_end = i - 10
            has_three_bullish = dataframe['is_bullish'].iloc[three_bull_start:three_bull_end+1].all()

            # 检查最近10根K线是否震荡
            is_recent_sideways = dataframe['is_sideways'].iloc[i]

            result.iloc[i] = has_three_bullish and is_recent_sideways
        return result

    def _check_simple_bullish_pattern(self, dataframe: pd.DataFrame) -> pd.Series:
        """检查简单连续阳线形态"""
        result = pd.Series(False, index=dataframe.index)
        for i in range(2, len(dataframe)):
            # 最近2根K线都是阳线
            recent_bullish = (
                dataframe['is_bullish'].iloc[i] and
                dataframe['is_bullish'].iloc[i-1]
            )
            result.iloc[i] = recent_bullish
        return result

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """买入信号逻辑"""
        # 基础过滤条件
        basic_conditions = (
            (dataframe['volume'] > 0) &
            (dataframe['rsi'] < 80)  # 避免超买
        )

        # 主要入场信号
        entry_signal = (
            dataframe['pattern_3bull_sideways'] |  # 3阳线+震荡形态
            (
                dataframe['pattern_simple_bull'] &  # 简单2阳线形态
                (dataframe['close'] > dataframe['ema_20'])  # 价格在EMA之上
            )
        )

        dataframe.loc[basic_conditions & entry_signal, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """卖出信号逻辑"""
        # 退出信号
        exit_signal = (
            (dataframe['consecutive_bearish'] >= 3) |  # 连续3阴线
            (dataframe['rsi'] > 85)  # 极度超买
        )

        dataframe.loc[exit_signal, 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs) -> Optional[str]:
        """自定义退出：7根K线后强制退出"""
        entry_time = trade.open_date_utc
        time_diff = current_time - entry_time

        # 转换为K线数量（5分钟K线）
        timeframe_minutes = 5
        candles_held = int(time_diff.total_seconds() / 60 / timeframe_minutes)

        if candles_held >= 7:
            return "7_candles_exit"
        return None
