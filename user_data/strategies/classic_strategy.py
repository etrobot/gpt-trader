# 精简版 K线形态交易策略 - 仅保留 震荡 + 3 阳线 入场，10 根 K 线出场

from freqtrade.strategy import IStrategy
import pandas as pd
from typing import Optional


class ClassicStrategy(IStrategy):
    """
    仅保留单一入场逻辑（OKX / 3m / 十根K线）：
    - 先出现一段震荡（10 根 K 线），随后连续 3 根阳线；
      震荡定义（更易触发）：
        1) 前10根K线的最高-最低区间占比 < 1%（相对 i-3 的收盘价）
        2) 最近3根阳线的最小实体 > 侧向段实体均值 × 1.2

    出场：持仓满 10 根 K 线后强制退出（custom_exit）
    """

    # 基本设置
    INTERFACE_VERSION = 3
    # 使用配置文件中的时间框架
    timeframe = "5m"

    # 设定 ROI 实现5根K线强制退出
    minimal_roi = {
        "0": 0.10,    # 初始目标收益 10%
        "25": -1      # 第5根K线强制退出（5根K线 × 5分钟 = 25分钟）
    }

    # 止损（可按需调整）
    stoploss = -0.05

    # 交易参数
    startup_candle_count: int = 30  # 适应20根K线平衡条件 + 8震荡+2阴线 + 缓冲
    process_only_new_candles = True
    use_exit_signal = False         # 不使用 populate_exit_trend 的退出
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False

    # 可调参数（确保 OKX / 3m 下更容易触发）
    sideways_range_ratio: float = 0.02      # 侧向段区间占比阈值，默认 2%
    body_vs_side_mean_mult: float = 1.0     # 3阳线最小实体相对侧向均值的倍数阈值

    # ---------------------- 指标与形态检测 ----------------------
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # K 线多空
        dataframe["is_bullish"] = dataframe["close"] > dataframe["open"]

        # K 线实体大小
        dataframe["candle_body"] = (dataframe["close"] - dataframe["open"]).abs()

        # 核心形态：10 根震荡后向上突破（更易触发，专注“十根K线”）
        dataframe["pattern_sideways_breakout_10"] = self._check_sideways_breakout(
            dataframe, sideways_len=10
        )

        return dataframe

    def _check_sideways_breakout(self, dataframe: pd.DataFrame, sideways_len: int = 10) -> pd.Series:
        """
        10 根震荡 + 向上突破：
        - i 为当前K线：
          1) 前 `sideways_len` 根（i-sideways_len 到 i-1）的高低区间占比 < self.sideways_range_ratio
          2) 当前收盘价 close[i] > 侧向段最高价（向上突破）
        """
        result = pd.Series(False, index=dataframe.index)
        if len(dataframe) < sideways_len + 1:
            return result

        highs = dataframe.get("high")
        lows = dataframe.get("low")
        close = dataframe.get("close")
        if highs is None or lows is None or close is None:
            return result

        for i in range(sideways_len, len(dataframe)):
            side_start = i - sideways_len
            side_end = i - 1
            side_high = float(highs.iloc[side_start: side_end + 1].max())
            side_low = float(lows.iloc[side_start: side_end + 1].min())
            base_close = float(close.iloc[side_end])
            if base_close <= 0:
                continue
            range_ratio = (side_high - side_low) / base_close
            cond_range = range_ratio < float(getattr(self, "sideways_range_ratio", 0.02))
            cond_breakout = float(close.iloc[i]) > side_high

            result.iloc[i] = bool(cond_range and cond_breakout)
        return result

    def _check_8sideways_2bulls_pattern(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        8震荡+2连阳增强模式：
        - i 为当前K线，i-1 和 i 必须为连续2根阳线
        - i-9 到 i-2 为8根震荡段
        - 条件1：8震荡中最长实体 < 2连阳中最短实体
        - 条件2：第2根阳线长度(i) > 第1根阳线长度(i-1) （递增）
        """
        result = pd.Series(False, index=dataframe.index)
        if len(dataframe) < 10:  # 需要至少10根K线
            return result

        bulls = dataframe["is_bullish"]
        bodies = dataframe["candle_body"]

        for i in range(9, len(dataframe)):  # 从第10根开始检查
            # 检查最近2根是否为阳线
            if not (bulls.iloc[i] and bulls.iloc[i - 1]):
                continue

            # 8震荡段：i-9 到 i-2
            side_start = i - 9
            side_end = i - 2
            side_bodies = bodies.iloc[side_start : side_end + 1]
            
            # 2连阳段：i-1 和 i
            bull1_body = bodies.iloc[i - 1]  # 第1根阳线
            bull2_body = bodies.iloc[i]      # 第2根阳线
            
            if len(side_bodies) != 8:
                continue

            # 条件1：8震荡中最长实体 < 2连阳中最短实体
            max_side_body = float(side_bodies.max())
            min_bull_body = float(min(bull1_body, bull2_body))
            cond1 = max_side_body < min_bull_body

            # 条件2：第2根阳线长度 > 第1根阳线长度（递增）
            cond2 = float(bull2_body) > float(bull1_body)

            result.iloc[i] = bool(cond1 and cond2)
        
        return result

    def _check_8sideways_2bears_pattern(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        8震荡+2连阴模式：
        - i 为当前K线，i-1 和 i 必须为连续2根阴线
        - i-9 到 i-2 为8根震荡段
        - 条件1：8震荡中最长实体 < 2连阴中最短实体
        - 条件2：第2根阴线长度(i) > 第1根阴线长度(i-1) （递增）
        """
        result = pd.Series(False, index=dataframe.index)
        if len(dataframe) < 10:  # 需要至少10根K线
            return result

        bears = ~dataframe["is_bullish"]  # 阴线标记
        bodies = dataframe["candle_body"]

        for i in range(9, len(dataframe)):  # 从第10根开始检查
            # 检查最近2根是否为阴线
            if not (bears.iloc[i] and bears.iloc[i - 1]):
                continue

            # 8震荡段：i-9 到 i-2
            side_start = i - 9
            side_end = i - 2
            side_bodies = bodies.iloc[side_start : side_end + 1]
            
            # 2连阴段：i-1 和 i
            bear1_body = bodies.iloc[i - 1]  # 第1根阴线
            bear2_body = bodies.iloc[i]      # 第2根阴线
            
            if len(side_bodies) != 8:
                continue

            # 条件1：8震荡中最长实体 < 2连阴中最短实体
            max_side_body = float(side_bodies.max())
            min_bear_body = float(min(bear1_body, bear2_body))
            cond1 = max_side_body < min_bear_body

            # 条件2：第2根阴线长度 > 第1根阴线长度（递增）
            cond2 = float(bear2_body) > float(bear1_body)

            result.iloc[i] = bool(cond1 and cond2)
        
        return result

    def _check_20k_balanced_pattern(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        近20根K线10阳10阴平衡条件：
        - 近20根K线中正好有10根阳线和10根阴线
        """
        result = pd.Series(False, index=dataframe.index)
        if len(dataframe) < 20:  # 需要至少20根K线
            return result

        bulls = dataframe["is_bullish"]   # 阳线标记

        for i in range(19, len(dataframe)):  # 从第20根开始检查
            # 近20根K线：i-19 到 i
            recent_20_start = i - 19
            recent_20_bulls = bulls.iloc[recent_20_start : i + 1]
            bull_count = int(recent_20_bulls.sum())
            bear_count = 20 - bull_count
            
            # 条件：正好10阳10阴
            result.iloc[i] = (bull_count == 10 and bear_count == 10)
        
        return result

    # ---------------------- 入场/出场 ----------------------
    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 基础过滤：仅确保有成交量
        basic_conditions = dataframe["volume"].fillna(0) > 0

        # 条件A：8震荡+2连阴模式
        pattern_signal_A = self._check_8sideways_2bears_pattern(dataframe)
        
        # 条件B：近20根K线10阳10阴平衡条件
        pattern_signal_B = self._check_20k_balanced_pattern(dataframe)

        # 两个条件任一满足即可入场（OR关系）
        entry_A = basic_conditions & pattern_signal_A
        entry_B = basic_conditions & pattern_signal_B

        # 使用接口v3标准信号：enter_long（适用于现货/合约的多头进入）
        dataframe.loc[entry_A, "enter_long"] = 1
        dataframe.loc[entry_A, "enter_tag"] = "8sideways_2bears"
        
        dataframe.loc[entry_B, "enter_long"] = 1  
        dataframe.loc[entry_B, "enter_tag"] = "20k_balanced"
        
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 不使用基于信号的退出（use_exit_signal=False），这里留空
        return dataframe

    # ---------------------- 技术指标：RSI（简单实现）----
    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        series = series.astype(float)
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        # 使用 RMA/EMA 实现更平滑的 RSI
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi

