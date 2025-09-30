# 升级版裸K线策略 - 分层结构：基础工具方法 + 组合策略

from freqtrade.strategy import IStrategy, IntParameter
import pandas as pd
from typing import Optional


class PriceActionStrategy(IStrategy):
    """
    裸K线策略 - 拒绝一切技术指标分析和量能
    
    策略逻辑：
    1. 前半段K线实体之和 * 0.6 < 前半段涨跌幅
    2. 后半段最长K线 < 前半段最短K线  
    3. 最后一根是阳线
    
    策略构建流程：
    K线预处理 -> 策略条件判断 -> 入场信号
    
    K线预处理：
    - 基础K线属性：阳线标记、K线长度、实体长度
    
    出场条件：
    - 仅按入场后K线数量：配置的K线数量后出场，拒绝一切其他条件
    
    时间周期：直接使用5分钟K线数据进行所有分析
    """

    # 基本设置
    INTERFACE_VERSION = 3
    timeframe = "5m"  # freqtrade固定使用5分钟


    # 止损设置 - 简单固定止损
    stoploss = -0.15  # 15%止损，给足够空间

    # FreqTrade固定参数
    startup_candle_count: int = 120
    process_only_new_candles = True
    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False
    use_custom_stoploss = False
    trailing_stop = False
    
    # 可优化参数 - 用于hyperopt
    trend_analysis_period = IntParameter(10, 40, default=20, space="buy")
    exit_candle_count = IntParameter(3, 10, default=5, space="sell")

    def __init__(self, config: dict) -> None:
        """初始化策略"""
        super().__init__(config)

    # ======================= 初始化：K线预处理类方法 =======================
    
    def _k_line_preprocessing(self, dataframe: pd.DataFrame) -> None:
        """
        K线预处理类方法
        包含基础K线属性计算
        """
        # 基础K线属性
        dataframe['is_bullish'] = dataframe['close'] > dataframe['open']  # 阳线标记
        dataframe['body_length'] = abs(dataframe['close'] - dataframe['open']) # 实体长度


    # ======================= 策略构建流程主入口 =======================
    
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        策略构建流程主入口 - 仅使用开高低收价格数据，拒绝技术指标和量能
        
        流程：K线预处理 -> 新策略判断
        """
        # K线预处理类方法
        self._k_line_preprocessing(dataframe)
        
        # 新策略
        dataframe['entry_signal'] = self._new_strategy(dataframe)
        
        return dataframe

    # ======================= 策略方法 =======================
    
    def _new_strategy(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        新策略逻辑：
        1. 前半段K线实体之和 * 0.6 < 前半段涨跌幅
        2. 后半段最长K线 < 前半段K线平均长度
        3. 最后一根是阳线
        """
        result = pd.Series(False, index=dataframe.index)
        
        if len(dataframe) < self.trend_analysis_period.value:
            return result
            
        for i in range(self.trend_analysis_period.value, len(dataframe)):
            # 获取分析周期内的数据
            start_idx = i - self.trend_analysis_period.value
            period_data = dataframe.iloc[start_idx:i]
            
            # 分成前后两段
            mid_point = len(period_data) // 2
            first_half = period_data.iloc[:mid_point]
            second_half = period_data.iloc[mid_point:]
            
            # 条件1：前半段K线实体之和 * 0.6 < 前半段涨跌幅
            first_half_body_sum = first_half['body_length'].sum()
            first_half_range = first_half['close'].iloc[-1] - first_half['close'].iloc[0]  # 涨跌幅
            condition1 = (first_half_body_sum * 0.6) < abs(first_half_range)
            
            # 条件2：后半段最长K线 < 平均K线长度
            second_half_max_candle = second_half['body_length'].max()
            period_mean_candle = period_data['body_length'].mean()
            condition2 = second_half_max_candle < period_mean_candle
            
            # 条件3：最后一根是阳线
            condition3 = dataframe['is_bullish'].iloc[i-1]
            
            # 所有条件都满足
            if condition1 and condition2 and condition3:
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
        不使用信号退出，仅依靠时间和ROI退出
        """
        return dataframe

    def custom_exit(self, pair: str, trade, current_time, current_rate, 
                   current_profit, **kwargs) -> Optional[str]:
        """
        第三层：出场机制
        仅按入场后K线数量：配置的K线数量后强制出场
        拒绝一切其他出场条件
        """
        # 计算持仓时间（分钟）
        hold_minutes = (current_time - trade.open_date_utc).total_seconds() / 60
        
        # N根5分钟K线后强制出场（N由配置决定）
        exit_minutes = self.exit_candle_count.value * 5
        if hold_minutes >= exit_minutes:
            return f"{self.exit_candle_count.value}_candles_exit"
            
        return None