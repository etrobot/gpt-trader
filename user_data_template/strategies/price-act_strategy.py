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
    # 固定参数（可被配置覆盖）
    trend_analysis_period: int = 25


    # ======================= 可优化参数 - 用于hyperopt =======================
    # 2) 后半段最长K线因子 - 调整条件2的严格程度（百分比，1.0表示不变化）
    second_half_max_candle_percentage = DecimalParameter(0.3, 1.5, default=0.63, decimals=2, space="buy")
    # 3) 前后分界点比例（0.5为平分），用于划分前/后半段
    # split_ratio = DecimalParameter(0.3, 0.7, default=0.50, decimals=2, space="buy")
    # 4) 条件2阈值放宽倍率，>1.0 表示放宽
    mean_multiplier = DecimalParameter(0.8, 2.0, default=1.64, decimals=2, space="buy")

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
                if "trend_analysis_period" in sp:
                    self.trend_analysis_period = int(sp["trend_analysis_period"])  # type: ignore[assignment]
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
        dataframe['is_bullish'] = dataframe['close'] > dataframe['open']  # 阳线标记
        dataframe['body_length'] = abs(dataframe['close'] - dataframe['open'])  # 实体长度
        # 新增：与前一根收盘比涨幅>0（用于条件3）
        dataframe['is_up'] = dataframe['close'] > dataframe['close'].shift(1)

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
        """
        策略逻辑：
        1. 最低价在前半段
        2. 后半段最长K线 * 因子(百分比) < 前半段K线平均长度
        3. 最后一根是阳线
        """
        result = pd.Series(False, index=dataframe.index)

        if len(dataframe) < self.trend_analysis_period:
            return result

        for i in range(self.trend_analysis_period, len(dataframe)):
            # 获取分析周期内的数据
            start_idx = i - self.trend_analysis_period
            period_data = dataframe.iloc[start_idx:i]

            # 分成前后两段
            # 使用可调分界比例将周期切分为前段/后段
            # split_ratio = float(self.split_ratio.value)
            split_ratio = 0.32
            mid_point = int(len(period_data) * split_ratio)
            # 约束分界点，避免任一段为空
            mid_point = max(1, min(len(period_data) - 1, mid_point))
            first_half = period_data.iloc[:mid_point]
            second_half = period_data.iloc[mid_point:]

            # 条件1：最低价在前半段
            period_low = period_data['low'].min()
            half_min_low = first_half['low'].min()
            condition1 = period_low == half_min_low

            # 条件2：后半段最长K线 * 因子(百分比) < K线长度平均值
            second_half_max_candle = second_half['body_length'].max()
            period_mean_candle = period_data['body_length'].mean()
            factor2 = float(self.second_half_max_candle_percentage.value)
            threshold = period_mean_candle * float(self.mean_multiplier.value)
            condition2 = (second_half_max_candle * factor2) < threshold

            # 条件3：最后一根涨幅 > 0（相对上一根收盘）
            condition3 = bool(dataframe['is_bullish'].iloc[i - 1])

            # 条件4:
            condition4 = period_data['body_length'].max() == first_half['body_length'].max()

            # 所有条件都满足
            if condition1 and condition2 and condition3 and condition4:
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
        """
        退出信号：主要由 custom_exit 控制，这里保留以便可扩展。
        当前不基于 DataFrame 的静态条件生成退出信号。
        """
        return dataframe
