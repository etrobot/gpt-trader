"""
K线交易策略
基于成交额排名和连续阳线/阴线模式的交易策略
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import requests
import os

from market_data.data_fetcher import fetch_top_symbols_by_turnover
from utils import update_task_progress

logger = logging.getLogger(__name__)

# Proxy configuration
proxy_url = os.getenv('PROXY_URL')
proxies = {'http': proxy_url, 'https': proxy_url} if proxy_url else None

BASE_URL = "https://api.bybit.com/v5"

class CandlestickStrategy:
    def __init__(self):
        self.timeframes = ["3", "5", "10", "15", "30", "60"]  # 分钟级别
        self.position_size = 0.2  # 1/5仓位
        self.active_positions = {}  # 记录活跃头寸
        
    def get_kline_data(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        """获取指定时间周期的K线数据"""
        try:
            url = f"{BASE_URL}/market/kline"
            params = {
                "category": "spot",
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            response = requests.get(url, params=params, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("retCode") == 0 and result["result"]["list"]:
                klines = result["result"]["list"]
                
                df = pd.DataFrame(
                    klines,
                    columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
                )
                
                # 批量转换数据类型
                numeric_cols = ["timestamp", "open", "high", "low", "close", "volume"]
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)
                df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
                
                # 按时间排序(最新的在前面)
                df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
                
                # 计算K线类型
                df["is_bullish"] = df["close"] > df["open"]  # 阳线/多头K线
                df["is_bearish"] = df["close"] < df["open"]  # 阴线/空头K线
                
                return df
            else:
                logger.warning(f"No K-line data for {symbol} interval {interval}")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"Error fetching K-line data for {symbol} interval {interval}: {e}")
            return pd.DataFrame()
    
    def count_consecutive_candles(self, df: pd.DataFrame, candle_type: str) -> int:
        """计算连续的阳线或阴线数量"""
        if df.empty:
            return 0
        
        count = 0
        column = "is_bullish" if candle_type == "bullish" else "is_bearish"
        
        # 从最新K线开始计算连续数量
        for i in range(len(df)):
            if df.iloc[i][column]:
                count += 1
            else:
                break
                
        return count
    
    def load_selected_timeframes(self) -> List[str]:
        """从每日分析结果中加载预选的时间周期"""
        import json
        import os
        
        try:
            analysis_file = "debug_output/timeframe_analysis.json"
            if os.path.exists(analysis_file):
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                
                selected_timeframes = analysis_data.get("selected_timeframes", [])
                if selected_timeframes:
                    # 移除 'm' 后缀，因为内部逻辑使用纯数字
                    timeframes = [tf.replace('m', '') for tf in selected_timeframes]
                    logger.info(f"Loaded selected timeframes: {timeframes}")
                    return timeframes
            
            logger.warning("No timeframe analysis found, using default timeframes")
            return ["3", "5", "10", "15"]  # 默认时间周期
            
        except Exception as e:
            logger.error(f"Failed to load timeframe analysis: {e}")
            return ["3", "5", "10", "15"]  # 出错时使用默认值
    
    def load_trading_symbols(self) -> List[str]:
        """从每日分析结果中加载预选的交易币种"""
        import json
        import os
        
        try:
            analysis_file = "debug_output/timeframe_analysis.json"
            if os.path.exists(analysis_file):
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                
                trading_symbols = analysis_data.get("trading_symbols", [])
                if trading_symbols:
                    logger.info(f"Loaded trading symbols: {trading_symbols}")
                    return trading_symbols
            
            logger.warning("No trading symbols found in analysis, fetching current top symbols")
            return []
            
        except Exception as e:
            logger.error(f"Failed to load trading symbols: {e}")
            return []
    
    def calculate_candle_length(self, open_price: float, close_price: float) -> float:
        """计算K线长度(绝对值)"""
        return abs(close_price - open_price)
    
    def is_sideways_movement(self, df: pd.DataFrame, start_idx: int, end_idx: int, reference_length: float) -> bool:
        """检查指定区间是否为震荡走势(最长的K线短于参考长度)"""
        if start_idx < 0 or end_idx >= len(df) or start_idx > end_idx:
            return False
        
        # 找到该区间内最长的K线
        max_length = 0.0
        for i in range(start_idx, end_idx + 1):
            candle_length = self.calculate_candle_length(df.iloc[i]["open"], df.iloc[i]["close"])
            if candle_length > max_length:
                max_length = candle_length
        
        # 如果最长的K线短于参考长度，则为震荡走势
        return max_length < reference_length
    
    def check_pattern_three_bullish_then_sideways(self, df: pd.DataFrame) -> bool:
        """检查是否有连续3阳线后震荡10根K线的模式"""
        if len(df) < 13:  # 需要至少13根K线
            return False
        
        # 检查第11-13根K线是否为连续3阳线
        if not (df.iloc[10]["is_bullish"] and 
                df.iloc[11]["is_bullish"] and 
                df.iloc[12]["is_bullish"]):
            return False
        
        # 计算三连阳中最短的K线长度作为参考
        min_length = float('inf')
        for i in range(10, 13):
            candle_length = self.calculate_candle_length(df.iloc[i]["open"], df.iloc[i]["close"])
            if candle_length < min_length:
                min_length = candle_length
        reference_length = min_length
        
        # 检查最新的10根K线是否为震荡走势(最长的K线短于三连阳中最短的K线)
        is_sideways = self.is_sideways_movement(df, 0, 9, reference_length)
        
        if is_sideways:
            logger.info("Pattern found: 3 bullish candles followed by 10 sideways candles")
            return True
        
        return False
    
    def check_pattern_sideways_then_three_bearish(self, df: pd.DataFrame) -> bool:
        """检查是否有震荡10根K线后连续3阴线的模式（用于做空/减仓提示，当前策略仍仅做多）。"""
        if len(df) < 13:
            return False
        
        # 检查最新的3根K线是否为连续3阴线
        if not (df.iloc[0]["is_bearish"] and 
                df.iloc[1]["is_bearish"] and 
                df.iloc[2]["is_bearish"]):
            return False
        
        # 计算三连阴中最短的K线长度作为参考
        min_length = float('inf')
        for i in range(0, 3):
            candle_length = self.calculate_candle_length(df.iloc[i]["open"], df.iloc[i]["close"])
            if candle_length < min_length:
                min_length = candle_length
        reference_length = min_length
        
        # 检查第4-13根K线是否为震荡走势(最长的K线短于三连阴中最短的K线)
        is_sideways = self.is_sideways_movement(df, 3, 12, reference_length)
        
        if is_sideways:
            logger.info("Pattern found: 10 sideways candles followed by 3 bearish candles")
            return True
        
        return False
    
    def send_trade_signal(self, symbol: str, action: str, price: float, timeframe: str) -> bool:
        """发送交易信号到Freqtrade"""
        try:
            from freqtrade_client import forceentry, forceexit_by_pair, health
            
            # 检查FreqTrade API连接
            if not health():
                logger.error("FreqTrade API is not healthy, cannot send signal")
                return False
            
            # 转换币种格式 (BTCUSDT -> BTC/USDT)
            if "/" not in symbol:
                if symbol.endswith("USDT"):
                    pair = f"{symbol[:-4]}/USDT"
                else:
                    pair = symbol  # 如果格式不明确，保持原样
            else:
                pair = symbol
            
            signal = {
                "symbol": symbol,
                "pair": pair,
                "action": action,
                "price": price,
                "timeframe": timeframe,
                "position_size": self.position_size,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Sending trade signal to FreqTrade: {signal}")
            
            # 发送信号到FreqTrade (FreqTrade自己配置了dry_run模式)
            success = False
            if action == "buy":
                # 计算下单金额 (假设总资金的1/5)
                stake_amount = None  # 让FreqTrade使用默认金额
                success = forceentry(pair, stake_amount=stake_amount)
                
                if success:
                    # 记录活跃头寸
                    position_key = f"{symbol}_{timeframe}"
                    self.active_positions[position_key] = {
                        "entry_price": price,
                        "entry_time": datetime.now(),
                        "timeframe": timeframe,
                        "candles_count": 0
                    }
                    logger.info(f"✅ BUY signal sent successfully for {pair}")
                else:
                    logger.error(f"❌ Failed to send BUY signal for {pair}")
                    
            elif action == "sell":
                # 强制平仓该交易对的所有持仓
                closed_count = forceexit_by_pair(pair)
                success = closed_count > 0
                
                if success:
                    # 清理本地记录的头寸
                    position_key = f"{symbol}_{timeframe}"
                    if position_key in self.active_positions:
                        del self.active_positions[position_key]
                    logger.info(f"✅ SELL signal sent successfully for {pair}, closed {closed_count} positions")
                else:
                    logger.warning(f"⚠️ No open positions to close for {pair}")
                    success = True  # 没有持仓也算成功
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send trade signal for {symbol}: {e}")
            return False
    
    def check_exit_conditions(self, position_key: str, current_price: float) -> bool:
        """检查是否满足退出条件(7根K线后)"""
        if position_key not in self.active_positions:
            return False
        
        position = self.active_positions[position_key]
        timeframe = position["timeframe"]
        symbol = position_key.split('_')[0]  # 从 "BTCUSDT_5" 中提取 "BTCUSDT"
        
        # 获取最新数据更新K线计数
        df = self.get_kline_data(symbol, timeframe, limit=10)
        if df.empty:
            return False
        
        # 计算从入场以来的K线数量
        entry_time = position["entry_time"]
        timeframe_minutes = int(timeframe)
        elapsed_minutes = (datetime.now() - entry_time).total_seconds() / 60
        candles_elapsed = int(elapsed_minutes / timeframe_minutes)
        
        if candles_elapsed >= 7:
            logger.info(f"Exit condition met for {position_key}: {candles_elapsed} candles elapsed")
            return True
        
        return False
    
    def monitor_and_trade(self, symbols: List[str], selected_timeframes: List[str], task_id: Optional[str] = None) -> Dict:
        """监控交易对并执行交易策略，使用预选的时间周期"""
        results = {
            "analyzed_symbols": len(symbols),
            "selected_timeframes": selected_timeframes,
            "signals_sent": [],
            "positions_closed": [],
            "timeframe_analysis": {}
        }
        
        
        for i, symbol in enumerate(symbols):
            if task_id:
                progress = 0.3 + (0.6 * i / len(symbols))
                update_task_progress(task_id, progress, f"监控交易对 {i+1}/{len(symbols)}: {symbol}")
            
            try:
                symbol_results = {}
                
                # 遍历所有预选的时间周期
                for timeframe in selected_timeframes:
                    # 获取该时间周期的数据
                    df = self.get_kline_data(symbol, timeframe, limit=50)
                    if df.empty:
                        continue
                    
                    current_price = float(df.iloc[0]["close"])
                    
                    # 检查是否已有持仓需要平仓
                    position_key = f"{symbol}_{timeframe}"
                    base_position_key = f"{symbol}_{timeframe}_base"
                    
                    # 检查策略持仓平仓条件
                    if self.check_exit_conditions(position_key, current_price):
                        if self.send_trade_signal(symbol, "sell", current_price, timeframe):
                            results["positions_closed"].append({
                                "symbol": symbol,
                                "price": current_price,
                                "timeframe": timeframe,
                                "type": "strategy_position"
                            })
                            if position_key in self.active_positions:
                                del self.active_positions[position_key]
                    
                    
                    # 检查入场信号(如果该时间周期没有持仓)
                    if position_key not in self.active_positions:
                        pattern1 = self.check_pattern_three_bullish_then_sideways(df)
                        pattern2 = self.check_pattern_sideways_then_three_bearish(df)
                        simple_bull = False
                        
                        # 如果严格形态未触发，尝试宽松的入场条件
                        if not (pattern1 or pattern2):
                            simple_bull = len(df) >= 2 and df.iloc[0]["is_bullish"] and df.iloc[1]["is_bullish"]
                        
                        if pattern1 or simple_bull:
                            if self.send_trade_signal(symbol, "buy", current_price, timeframe):
                                results["signals_sent"].append({
                                    "symbol": symbol,
                                    "pattern": "3bullish+10sideways" if pattern1 else "2bullish_recent",
                                    "price": current_price,
                                    "timeframe": timeframe,
                                    "type": "strategy_position"
                                })
                                # 使用组合键记录持仓
                                self.active_positions[position_key] = {
                                    "entry_price": current_price,
                                    "entry_time": datetime.now(),
                                    "timeframe": timeframe,
                                    "position_type": "strategy",
                                    "candles_count": 0
                                }
                    
                    # 记录该时间周期的分析结果
                    has_strategy_position = position_key in self.active_positions
                    pattern_detected = (pattern1 or simple_bull) if not has_strategy_position else False
                    
                    symbol_results[timeframe] = {
                        "has_strategy_position": has_strategy_position,
                        "has_position": has_strategy_position,
                        "pattern_detected": pattern_detected
                    }
                
                results["timeframe_analysis"][symbol] = symbol_results
                
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue
        
        return results

def run_candlestick_strategy(task_id: Optional[str] = None) -> Dict:
    """运行K线交易策略，使用每日预选的币种和时间周期"""
    logger.info("Starting candlestick trading strategy")
    
    try:
        if task_id:
            update_task_progress(task_id, 0.05, "初始化K线策略")
        
        # 1. 初始化策略
        strategy = CandlestickStrategy()
        
        # 2. 加载每日分析的预选币种和时间周期
        if task_id:
            update_task_progress(task_id, 0.1, "加载预选交易币种和时间周期")
        
        trading_symbols = strategy.load_trading_symbols()
        selected_timeframes = strategy.load_selected_timeframes()
        
        # 如果没有预选币种，获取当前成交额前5名作为备选
        if not trading_symbols:
            logger.info("No pre-selected symbols, fetching current top symbols")
            top_symbols_df = fetch_top_symbols_by_turnover(top_n=5)
            if top_symbols_df.empty:
                logger.error("No symbols found")
                return {"error": "No symbols found"}
            trading_symbols = top_symbols_df["symbol"].tolist()
        
        logger.info(f"Trading symbols: {trading_symbols}")
        logger.info(f"Selected timeframes: {selected_timeframes}")
        
        if task_id:
            update_task_progress(task_id, 0.2, f"开始监控 {len(trading_symbols)} 个交易对")
        
        # 3. 执行策略
        results = strategy.monitor_and_trade(trading_symbols, selected_timeframes, task_id)
        
        if task_id:
            update_task_progress(task_id, 1.0, "K线策略执行完成")
        
        logger.info(f"Candlestick strategy completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Candlestick strategy failed: {e}")
        if task_id:
            update_task_progress(task_id, 1.0, f"策略执行失败: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # 测试运行
    result = run_candlestick_strategy()
    print(f"Strategy result: {result}")