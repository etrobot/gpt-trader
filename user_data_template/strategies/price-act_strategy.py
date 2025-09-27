# 升级版裸K线策略 - 分层结构：基础工具方法 + 组合策略

from freqtrade.strategy import IStrategy
import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime, timedelta


class PriceActionStrategy(IStrategy):
    """
    升级版裸K线策略 - 拒绝一切技术指标分析和量能
    
    策略构建流程：
    K线预处理 -> 基础判断方法任选其一策略入场 -> 叠加简单出场条件形成策略
    
    分层架构：
    第零层：K线预处理类方法
    - 基础K线属性：阳线/阴线标记、长度、实体长度
    - K线长度值（带正负）：阳线为正，阴线为负，十字星按影线判断
    - 多周期封装：基于5分钟构建10/15/30/60分钟等效标记
    
    第一层：基础判断方法
    - 趋势判断方法：K线均分，后段最低收盘比前端平均价
    - 波幅增强判断：最后一根K线长度 > 80%K线长度
    
    第二层：任选其一策略入场
    - 突破入场策略：趋势为上升 + 波幅增强 + 最后N根阳线
    - 抢反弹策略：趋势为下降 + 波幅增强 + 最后M根阳线 + 阴线数量>60%
    - 入场逻辑：满足任意一种策略即可入场
    - N/M根数量由配置参数决定
    
    第三层：简单出场条件
    - 仅按入场后K线数量：配置的K线数量后出场，拒绝一切其他条件
    
    时间周期：使用配置的分析周期倍数，freqtrade固定使用5分钟
    """

    # 基本设置
    INTERFACE_VERSION = 3
    timeframe = "5m"  # freqtrade固定使用5分钟

    # ROI配置：基于配置的退出K线数量
    minimal_roi = {
        "0": 0.10,    # 初始目标收益10%
        "25": -1      # 默认25分钟后强制退出（5根K线 × 5分钟）
    }

    # 止损设置 - 简单固定止损
    stoploss = -0.15  # 15%止损，给足够空间

    # 交易参数
    startup_candle_count: int = 120  # 确保有足够历史数据进行多周期分析
    process_only_new_candles = True
    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False

    # 简化止损参数
    use_custom_stoploss = False
    trailing_stop = False

    # 基础工具方法参数
    trend_analysis_period: int = 20     # 趋势判断的K线周期数
    amplitude_lookback: int = 20        # 波幅增强判断的回望周期
    amplitude_percentile: float = 0.8   # 波幅增强阈值（80%分位数）
    
    # 策略参数
    bear_ratio_threshold: float = 0.6   # 抢反弹策略中阴线比例阈值（60%）
    
    # 时间周期配置
    analysis_timeframe_ratio: int = 1   # 分析用的时间周期倍数（1=5分钟）
    exit_candle_count: int = 5          # 强制退出的K线数量
    breakout_bull_candles: int = 2      # 突破策略需要的连续阳线数量
    rebound_bull_candles: int = 1       # 反弹策略需要的阳线数量

    def __init__(self, config: dict) -> None:
        """初始化策略，根据配置动态设置ROI"""
        super().__init__(config)
        # 动态设置ROI基于退出K线数量
        exit_minutes = self.exit_candle_count * 5  # K线数量 × 5分钟
        self.minimal_roi = {
            "0": 0.10,                 # 初始目标收益10%
            str(exit_minutes): -1      # 配置的K线数量后强制退出
        }

    # ======================= 初始化：K线预处理类方法 =======================
    
    def _k_line_preprocessing(self, dataframe: pd.DataFrame) -> None:
        """
        K线预处理类方法
        包含基础K线属性计算和多周期封装
        """
        # 基础K线属性
        dataframe['is_bullish'] = dataframe['close'] > dataframe['open']  # 阳线标记
        dataframe['is_bearish'] = dataframe['close'] < dataframe['open']  # 阴线标记
        dataframe['candle_length'] = dataframe['high'] - dataframe['low'] # K线总长度（无正负）
        dataframe['body_length'] = abs(dataframe['close'] - dataframe['open']) # 实体长度
        
        # K线长度值（带正负）- 阳线为正，阴线为负
        dataframe['signed_length'] = self._calculate_signed_length(dataframe)
        
        # 多周期封装 - 基于5分钟构建其他周期数据
        self._build_multi_timeframe_data(dataframe)

    def _calculate_signed_length(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        计算K线长度值（带正负）
        - 阳线：正数，取K线总长度 (high - low)
        - 阴线：负数，取K线总长度的负值 -(high - low)
        - 十字星：根据收盘价与开盘价关系判断正负
        """
        result = pd.Series(0.0, index=dataframe.index)
        
        # 基础长度（总是正数）
        base_length = dataframe['high'] - dataframe['low']
        
        # 根据K线性质添加正负号
        for i in range(len(dataframe)):
            if dataframe['is_bullish'].iloc[i]:
                # 阳线：正数
                result.iloc[i] = base_length.iloc[i]
            elif dataframe['is_bearish'].iloc[i]:
                # 阴线：负数
                result.iloc[i] = -base_length.iloc[i]
            else:
                # 十字星：收盘价等于开盘价，根据上下影线判断
                # 简化处理：上影线长则为正，下影线长则为负
                high_val = dataframe['high'].iloc[i]
                low_val = dataframe['low'].iloc[i]
                open_val = dataframe['open'].iloc[i]
                
                upper_shadow = high_val - open_val
                lower_shadow = open_val - low_val
                
                if upper_shadow >= lower_shadow:
                    result.iloc[i] = base_length.iloc[i]  # 上影线长，视为正
                else:
                    result.iloc[i] = -base_length.iloc[i] # 下影线长，视为负
        
        return result

    def _build_multi_timeframe_data(self, dataframe: pd.DataFrame) -> None:
        """
        时间周期数据构建 - K线预处理类方法
        基于5分钟数据和配置的时间周期倍数构建分析数据
        """
        # 使用配置的时间周期倍数
        interval = self.analysis_timeframe_ratio
        
        # 创建周期标记：标记哪些5分钟K线对应该周期的结束点
        tf_markers = pd.Series(False, index=dataframe.index)
        
        # 从足够的起始位置开始标记周期结束点
        start_idx = interval - 1
        for i in range(start_idx, len(dataframe), interval):
            tf_markers.iloc[i] = True
            
        dataframe['tf_analysis_marker'] = tf_markers
        
        # 为该周期创建有效K线标记（用于后续分析）
        dataframe['tf_analysis_valid'] = self._create_timeframe_valid_mask(
            dataframe, interval
        )

    def _create_timeframe_valid_mask(self, dataframe: pd.DataFrame, interval: int) -> pd.Series:
        """
        创建时间周期有效性掩码
        标记哪些位置有足够的历史数据进行该周期分析
        """
        result = pd.Series(False, index=dataframe.index)
        
        # 需要至少有 trend_analysis_period * interval 根K线才能进行分析
        min_required = self.trend_analysis_period * interval
        
        for i in range(min_required, len(dataframe)):
            result.iloc[i] = True
            
        return result

    # ======================= 策略构建流程主入口 =======================
    
    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        策略构建流程主入口 - 仅使用开高低收价格数据，拒绝技术指标和量能
        
        流程：K线预处理 -> 基础判断方法任选其一策略入场 -> 叠加简单出场条件形成策略
        """
        # 第零层：K线预处理类方法
        self._k_line_preprocessing(dataframe)
        
        # 第一层：基础判断方法 
        dataframe['trend_direction'] = self._trend_judgment_tool(dataframe)
        dataframe['amplitude_enhanced'] = self._amplitude_enhancement_tool(dataframe)
        
        # 第二层：任选其一策略入场
        dataframe['breakout_strategy'] = self._breakout_entry_strategy(dataframe)
        dataframe['rebound_strategy'] = self._rebound_entry_strategy(dataframe)
        
        return dataframe

    # ======================= 第一层：基础判断方法 =======================
    
    def _trend_judgment_tool(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        基础工具方法：趋势判断
        
        逻辑：一段K线均分，后段的最低收盘比前端的平均价
        - 后段最低收盘 > 前段平均价 → 上升趋势 (1)
        - 后段最低收盘 < 前段平均价 → 下降趋势 (-1)  
        - 其他情况 → 无明确趋势 (0)
        
        使用配置的时间周期进行分析
        """
        result = pd.Series(0, index=dataframe.index)
        
        if len(dataframe) < self.trend_analysis_period:
            return result
            
        # 使用配置的时间周期进行趋势判断
        tf_trend = self._calculate_trend_for_timeframe(dataframe, self.analysis_timeframe_ratio)
        dataframe['trend_analysis'] = tf_trend
        
        # 使用配置的分析周期趋势
        result = dataframe['trend_analysis']
        
        return result

    def _calculate_trend_for_timeframe(self, dataframe: pd.DataFrame, period_ratio: int) -> pd.Series:
        """
        计算指定时间周期的趋势
        period_ratio: 相对于5分钟的倍数 (如10分钟=2倍)
        """
        result = pd.Series(0, index=dataframe.index)
        analysis_length = self.trend_analysis_period * period_ratio
        
        if len(dataframe) < analysis_length:
            return result
            
        for i in range(analysis_length, len(dataframe)):
            # 获取分析周期内的收盘价
            start_idx = i - analysis_length
            closes = []
            
            # 按period_ratio间隔取收盘价，模拟更大时间周期
            for j in range(0, analysis_length, period_ratio):
                idx = start_idx + j + period_ratio - 1
                if idx < len(dataframe):
                    closes.append(dataframe['close'].iloc[idx])
            
            if len(closes) >= 4:  # 至少需要4个点才能均分判断
                trend = self._analyze_trend_direction(closes)
                result.iloc[i] = trend
                
        return result

    def _analyze_trend_direction(self, closes: list) -> int:
        """
        趋势方向分析核心算法
        K线均分，后段最低收盘比前端平均价
        """
        if len(closes) < 4:
            return 0
            
        # 均分为前后两段
        mid_point = len(closes) // 2
        front_segment = closes[:mid_point]
        back_segment = closes[mid_point:]
        
        # 前段平均价
        front_avg = np.mean(front_segment)
        
        # 后段最低收盘价
        back_min_close = np.min(back_segment)
        
        # 趋势判断
        if back_min_close > front_avg:
            return 1    # 上升趋势
        elif back_min_close < front_avg * 0.98:  # 2%缓冲区避免频繁切换
            return -1   # 下降趋势
        else:
            return 0    # 无明确趋势

    def _amplitude_enhancement_tool(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        基础工具方法：波幅增强判断
        
        逻辑：最后一根K线长度 > 80%K线长度
        使用滚动窗口计算历史K线长度的80%分位数作为基准
        """
        result = pd.Series(False, index=dataframe.index)
        
        if len(dataframe) < self.amplitude_lookback:
            return result
            
        # 计算滚动窗口的K线长度80%分位数
        rolling_80pct = dataframe['candle_length'].rolling(
            window=self.amplitude_lookback, 
            min_periods=self.amplitude_lookback
        ).quantile(self.amplitude_percentile)
        
        # 当前K线长度是否超过80%分位数
        result = dataframe['candle_length'] > rolling_80pct
        
        return result

    # ======================= 第二层：组合策略 =======================
    
    def _breakout_entry_strategy(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        突破入场策略
        
        组合条件：
        1. 趋势为上升 (trend_direction == 1)
        2. 波幅增强 (amplitude_enhanced == True)  
        3. 最后N根K线为阳线（N由breakout_bull_candles配置）
        """
        result = pd.Series(False, index=dataframe.index)
        
        if len(dataframe) < 2:
            return result
            
        # 条件1：上升趋势
        uptrend = dataframe['trend_direction'] == 1
        
        # 条件2：波幅增强
        amp_enhanced = dataframe['amplitude_enhanced']
        
        # 条件3：最后N根K线都是阳线（N由配置决定）
        bull_conditions = dataframe['is_bullish']
        for i in range(1, self.breakout_bull_candles):
            bull_conditions = bull_conditions & dataframe['is_bullish'].shift(i)
        last_n_bulls = bull_conditions
        
        # 组合策略条件
        result = uptrend & amp_enhanced & last_n_bulls
        
        return result

    def _rebound_entry_strategy(self, dataframe: pd.DataFrame) -> pd.Series:
        """
        抢反弹策略
        
        组合条件：
        1. 趋势为下降 (trend_direction == -1)
        2. 波幅增强 (amplitude_enhanced == True)
        3. 最后N根K线为阳线（N由rebound_bull_candles配置）
        4. 阴线数量 > 60%（近期K线统计）
        """
        result = pd.Series(False, index=dataframe.index)
        
        if len(dataframe) < self.trend_analysis_period:
            return result
            
        for i in range(self.trend_analysis_period, len(dataframe)):
            # 条件1：下降趋势
            if dataframe['trend_direction'].iloc[i] != -1:
                continue
                
            # 条件2：波幅增强
            if not dataframe['amplitude_enhanced'].iloc[i]:
                continue
                
            # 条件3：最后N根K线是阳线（N由配置决定）
            bull_check = True
            for j in range(self.rebound_bull_candles):
                if i - j < 0 or not dataframe['is_bullish'].iloc[i - j]:
                    bull_check = False
                    break
            if not bull_check:
                continue
                
            # 条件4：近期阴线数量 > 60%
            start_idx = i - self.trend_analysis_period
            recent_bears = dataframe['is_bearish'].iloc[start_idx:i]
            bear_ratio = recent_bears.sum() / len(recent_bears)
            
            if bear_ratio > self.bear_ratio_threshold:
                result.iloc[i] = True
                
        return result

    # ======================= FreqTrade接口实现 =======================

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        入场信号：任选其一策略
        满足突破入场策略 OR 抢反弹策略 任意一个即可入场
        """
        # 基础条件：确保价格数据有效
        basic_conditions = (
            (dataframe['high'] > dataframe['low']) & 
            (dataframe['close'] > 0) &
            (dataframe['open'] > 0)
        )
        
        # 突破入场策略条件
        breakout_entry = basic_conditions & dataframe['breakout_strategy']
        
        # 抢反弹策略条件
        rebound_entry = basic_conditions & dataframe['rebound_strategy']
        
        # 设置入场信号 - 任选其一策略逻辑
        # 满足突破策略即可入场，标记为'breakout'
        dataframe.loc[breakout_entry, 'enter_long'] = 1
        dataframe.loc[breakout_entry, 'enter_tag'] = 'breakout'
        
        # 满足反弹策略即可入场，标记为'rebound' 
        # 注意：如果同时满足两种策略，后执行的会覆盖enter_tag
        dataframe.loc[rebound_entry, 'enter_long'] = 1  
        dataframe.loc[rebound_entry, 'enter_tag'] = 'rebound'
        
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
        exit_minutes = self.exit_candle_count * 5
        if hold_minutes >= exit_minutes:
            return f"{self.exit_candle_count}_candles_exit"
            
        return None