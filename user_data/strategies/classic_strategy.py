# 精简版 K线形态交易策略 - 仅保留 震荡 + 3 阳线 入场，10 根 K 线出场

from freqtrade.strategy import IStrategy
import pandas as pd
from typing import Optional


class ClassicStrategy(IStrategy):
    """
    仅保留：
    - 入场：先出现一段震荡（10 根 K 线），随后连续 3 根阳线；
            震荡定义：震荡段中最大实体 < 紧随其后的 3 根阳线段中最小实体
    - 出场：持仓满 10 根 K 线后强制退出
    """

    # 基本设置
    INTERFACE_VERSION = 3
    timeframe = "5m"

    def __init__(self, config: dict):
        super().__init__(config)
        if "timeframe" in config:
            self.timeframe = config["timeframe"]

    # 设定极高 ROI，避免 ROI 提前退出；关闭基于信号的退出，由 custom_exit 控制
    minimal_roi = {
        "0": 1000  # 形同禁用 ROI（要求 100000% 才离场）
    }

    # 止损（可按需调整）
    stoploss = -0.05

    # 交易参数
    startup_candle_count: int = 50
    process_only_new_candles = True
    use_exit_signal = False         # 不使用 populate_exit_trend 的退出
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False

    # ---------------------- 指标与形态检测 ----------------------
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # K 线多空
        dataframe["is_bullish"] = dataframe["close"] > dataframe["open"]

        # K 线实体大小
        dataframe["candle_body"] = (dataframe["close"] - dataframe["open"]).abs()

        # 核心形态：先震荡（10 根），再 3 阳线，且 max(sideways) < min(3 bulls)
        dataframe["pattern_sideways_then_3bull"] = self._check_pattern_sideways_then_three_bullish(
            dataframe, sideways_len=10
        )

        return dataframe

    def _check_pattern_sideways_then_three_bullish(self, dataframe: pd.DataFrame, sideways_len: int = 10) -> pd.Series:
        """
        检查：
        - 在某根 K 线 i，i-2 到 i 必须为连续 3 根阳线；
        - i-3 往前的连续 `sideways_len` 根为震荡段，且：
            max(body[sideways段]) < min(body[i-2..i])
        """
        result = pd.Series(False, index=dataframe.index)
        if len(dataframe) < sideways_len + 3:
            return result

        bodies = dataframe["candle_body"]
        bulls = dataframe["is_bullish"]

        for i in range(sideways_len + 2, len(dataframe)):
            # 最近 3 根是否为阳线
            if not (bulls.iloc[i] and bulls.iloc[i - 1] and bulls.iloc[i - 2]):
                continue

            # 侧向段：紧邻 3 阳线之前的 `sideways_len` 根
            side_start = i - sideways_len - 2
            side_end = i - 3
            if side_start < 0:
                continue

            side_bodies = bodies.iloc[side_start : side_end + 1]
            bull_bodies = bodies.iloc[i - 2 : i + 1]

            if len(side_bodies) != sideways_len:
                continue

            max_side = side_bodies.max()
            min_bull = bull_bodies.min()

            result.iloc[i] = bool(max_side < min_bull)
        return result

    # ---------------------- 入场/出场 ----------------------
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 基础过滤：仅确保有成交量
        basic_conditions = dataframe["volume"] > 0

        # 入场信号：震荡 + 3 阳线
        entry_signal = dataframe["pattern_sideways_then_3bull"]

        dataframe.loc[basic_conditions & entry_signal, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 不使用基于信号的退出（use_exit_signal=False），这里留空
        return dataframe

    # ---------------------- 自定义 10 根 K 线强制退出 ----------------------
    def custom_exit(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs) -> Optional[str]:
        entry_time = trade.open_date_utc
        candles_held = self._candles_held(entry_time, current_time)
        if candles_held >= 10:
            return "10_candles_exit"
        return None

    # ---------------------- 工具方法 ----------------------
    def _candles_held(self, entry_time, current_time) -> int:
        """根据策略 timeframe 计算已持有的 K 线数量。"""
        tf_seconds = self._timeframe_to_seconds(self.timeframe)
        held_seconds = (current_time - entry_time).total_seconds()
        if tf_seconds <= 0:
            return 0
        return int(held_seconds // tf_seconds)

    @staticmethod
    def _timeframe_to_seconds(tf: str) -> int:
        """将 '5m' / '1h' / '1d' 等转换为秒数。"""
        if not tf or not isinstance(tf, str):
            return 0
        tf = tf.strip().lower()
        unit = tf[-1]
        try:
            value = int(tf[:-1])
        except Exception:
            return 0
        if unit == "m":
            return value * 60
        if unit == "h":
            return value * 60 * 60
        if unit == "d":
            return value * 24 * 60 * 60
        # 未知单位
        return 0
