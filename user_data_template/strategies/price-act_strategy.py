# 升级版裸K线策略 - 分层结构：基础工具方法 + 组合策略

from freqtrade.strategy import IStrategy, DecimalParameter, CategoricalParameter
import pandas as pd
from datetime import datetime
from typing import Optional, Union, Dict


class PriceActionStrategy(IStrategy):
    """
    裸K线策略 - 拒绝一切技术指标分析和量能
    """

    # FreqTrade固定参数
    INTERFACE_VERSION = 3
    timeframe = "5m"  # freqtrade固定使用5分钟
    startup_candle_count: int = 120
    process_only_new_candles = True
    # 启用退出信号，以支持更快出场
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False
    use_custom_stoploss = False
    trailing_stop = False


    # ======================= 可优化参数 - 用于hyperopt =======================
    # 添加买入空间的可优化参数
    trend_period = DecimalParameter(10, 50, default=30, space="buy", optimize=True)
    # 前期下跌比例：确保前面有明显下跌
    decline_ratio = DecimalParameter(0.01, 0.06, default=0.02, space="buy", optimize=True)
    # ROI/止损默认值（可被 hyperopt 在 --spaces roi stoploss 下优化）
    minimal_roi = {
        "0": 0.102,
        "22": 0.025,
        "60": 0.023,
        "155": 0
    }
    stoploss = -0.35  # 默认止损，hyperopt可优化
    

    def __init__(self, config: dict) -> None:
        """初始化策略：允许从配置覆盖一些策略参数"""
        super().__init__(config)
        try:
            sp = (config or {}).get("strategy_params", {})
            if isinstance(sp, dict):
                if "trend_period" in sp:
                    self.trend_period = int(sp["trend_period"])  # type: ignore[assignment]
        except Exception:
            # 保底：如果配置解析失败，继续使用默认值
            pass

    # ======================= 初始化：K线预处理类方法 =======================

    def _k_line_preprocessing(self, dataframe: pd.DataFrame) -> None:
        """
        K线预处理类方法
        包含基础K线属性计算
        """
        # 基础K线属性
        dataframe['body_length'] = abs(dataframe['close'] - dataframe['open'])  # 实体长度


    # ======================= 策略构建流程主入口 =======================

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        策略构建流程主入口 - 仅使用开高低收价格数据，拒绝技术指标和量能

        流程：K线预处理 -> 新策略判断
        """
        # K线预处理类方法
        self._k_line_preprocessing(dataframe)

        # 策略
        dataframe['entry_signal'] = self._strategy(dataframe)

        return dataframe

    # ======================= 策略方法 =======================

    def _strategy(self, dataframe: pd.DataFrame) -> pd.Series:

        result = pd.Series(False, index=dataframe.index)

        trend_period_value = int(self.trend_period.value)
        decline_ratio_value = float(self.decline_ratio.value)
        
        if len(dataframe) < trend_period_value:
            return result

        for i in range(trend_period_value, len(dataframe)):
            # 获取分析周期内的数据
            start_idx = i - trend_period_value
            period_data = dataframe.iloc[start_idx:i]
            
            # 当前K线数据
            current_candle = dataframe.iloc[i]

            # 原始条件：最小实体K线
            min_body_condition = bool(period_data['body_length'].iloc[-1] == period_data['body_length'].min())
            
            # 新增条件：前期有明显下跌
            # 计算分析周期内的价格下跌幅度
            period_high_price = period_data['high'].max()
            current_low_price = current_candle['low']
            
            # 下跌幅度：从最高点到当前低点的跌幅
            decline_pct = (period_high_price - current_low_price) / period_high_price if period_high_price > 0 else 0
            
            # 下跌条件：确保有足够的下跌幅度
            decline_condition = bool(decline_pct >= decline_ratio_value)

            # 组合条件：原始条件 + 下跌条件
            condition = min_body_condition and decline_condition

            if condition:
                result.iloc[i] = True

        return result

    # ======================= FreqTrade接口实现 =======================

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        入场信号：新策略
        满足所有条件即可入场
        """
        # 基础条件：确保价格数据有效
        basic_conditions = (
            (dataframe['high'] > dataframe['low']) &
            (dataframe['close'] > 0) &
            (dataframe['open'] > 0)
        )

        # 新策略入场条件
        entry_conditions = basic_conditions & dataframe['entry_signal']

        # 设置入场信号
        dataframe.loc[entry_conditions, 'enter_long'] = 1
        dataframe.loc[entry_conditions, 'enter_tag'] = 'new_strategy'

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        return dataframe
