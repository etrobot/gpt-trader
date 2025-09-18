"""
定时任务调度器
每天UTC 0点运行分析和新闻评估任务
每天UTC 1点运行交易周期梳理任务
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from data_management.services import create_analysis_task, create_news_evaluation_task
from trade_signal_executor import execute_signals
from candlestick_strategy import run_candlestick_strategy

logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)
        self.is_running = False
        self.enabled = True
        self.last_run: Optional[str] = None
        self.current_analysis_task_id: Optional[str] = None
        self.current_news_task_id: Optional[str] = None
        self.current_candlestick_task_id: Optional[str] = None
        self.current_timeframe_review_task_id: Optional[str] = None

    def start(self):
        """启动调度器"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            # 添加每日UTC 0点的定时任务
            self.scheduler.add_job(
                func=self._run_daily_tasks,
                trigger=CronTrigger(hour=0, minute=0, timezone=timezone.utc),
                id="daily_crypto_analysis",
                name="Daily Crypto Analysis and News Evaluation",
                replace_existing=True
            )
            
            # 添加K线策略任务，每10分钟执行一次
            self.scheduler.add_job(
                func=self._run_candlestick_strategy,
                trigger=CronTrigger(minute="*/10", timezone=timezone.utc),
                id="candlestick_strategy",
                name="Candlestick Pattern Trading Strategy",
                replace_existing=True
            )
            
            # 添加每日交易周期梳理任务，每天UTC 1点执行
            self.scheduler.add_job(
                func=self._run_timeframe_review,
                trigger=CronTrigger(hour=1, minute=0, timezone=timezone.utc),
                id="daily_timeframe_review",
                name="Daily Trading Timeframe Review",
                replace_existing=True
            )
            
            # Bootstrap startup run removed - use manual trigger instead
            
            self.scheduler.start()
            
            # 启动后立即测试一次最小底仓下单（仅启动时执行一次）
            logger.info("Scheduling startup test position to run in 3 seconds...")
            self.scheduler.add_job(
                func=self._startup_test_position,
                trigger=DateTrigger(run_date=datetime.now(timezone.utc) + timedelta(seconds=3)),
                id="startup_test_position",
                name="Startup Test Position",
                replace_existing=True
            )
            logger.info("Startup test position job scheduled successfully")
            self.is_running = True
            logger.info("Task scheduler started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """停止调度器"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            logger.info("Task scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")

    def stop_current_tasks(self) -> bool:
        """停止当前运行的定时任务"""
        stopped_any = False
        
        try:
            from utils import TASK_STOP_EVENTS
            
            # 停止分析任务
            if self.current_analysis_task_id:
                stop_event = TASK_STOP_EVENTS.get(self.current_analysis_task_id)
                if stop_event:
                    stop_event.set()
                    stopped_any = True
                    logger.info(f"Requested stop for analysis task: {self.current_analysis_task_id}")
            
            # 停止新闻任务
            if self.current_news_task_id:
                stop_event = TASK_STOP_EVENTS.get(self.current_news_task_id)
                if stop_event:
                    stop_event.set()
                    stopped_any = True
                    logger.info(f"Requested stop for news task: {self.current_news_task_id}")
            
            # 停止K线策略任务
            if self.current_candlestick_task_id:
                stop_event = TASK_STOP_EVENTS.get(self.current_candlestick_task_id)
                if stop_event:
                    stop_event.set()
                    stopped_any = True
                    logger.info(f"Requested stop for candlestick task: {self.current_candlestick_task_id}")
            
            # 停止时间周期梳理任务
            if self.current_timeframe_review_task_id:
                stop_event = TASK_STOP_EVENTS.get(self.current_timeframe_review_task_id)
                if stop_event:
                    stop_event.set()
                    stopped_any = True
                    logger.info(f"Requested stop for timeframe review task: {self.current_timeframe_review_task_id}")
            
            return stopped_any
        except Exception as e:
            logger.error(f"Failed to stop current tasks: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        from utils import get_task
        
        # 获取下次运行时间
        next_run = None
        if self.is_running:
            try:
                job = self.scheduler.get_job("daily_crypto_analysis")
                if job and job.next_run_time:
                    next_run = job.next_run_time.isoformat()
            except Exception as e:
                logger.error(f"Failed to get next run time: {e}")
        
        # 检查当前任务状态
        analysis_task = None
        news_task = None
        candlestick_task = None
        timeframe_review_task = None
        
        if self.current_analysis_task_id:
            analysis_task = get_task(self.current_analysis_task_id)
        if self.current_news_task_id:
            news_task = get_task(self.current_news_task_id)
        if self.current_candlestick_task_id:
            candlestick_task = get_task(self.current_candlestick_task_id)
        if self.current_timeframe_review_task_id:
            timeframe_review_task = get_task(self.current_timeframe_review_task_id)
        
        return {
            "scheduler_running": self.is_running,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": next_run,
            "current_analysis_task": {
                "task_id": self.current_analysis_task_id,
                "status": analysis_task.status if analysis_task else None,
                "progress": analysis_task.progress if analysis_task else None,
                "message": analysis_task.message if analysis_task else None
            } if self.current_analysis_task_id else None,
            "current_news_task": {
                "task_id": self.current_news_task_id,
                "status": news_task.status if news_task else None,
                "progress": news_task.progress if news_task else None,
                "message": news_task.message if news_task else None
            } if self.current_news_task_id else None,
            "current_candlestick_task": {
                "task_id": self.current_candlestick_task_id,
                "status": candlestick_task.status if candlestick_task else None,
                "progress": candlestick_task.progress if candlestick_task else None,
                "message": candlestick_task.message if candlestick_task else None
            } if self.current_candlestick_task_id else None,
            "current_timeframe_review_task": {
                "task_id": self.current_timeframe_review_task_id,
                "status": timeframe_review_task.status if timeframe_review_task else None,
                "progress": timeframe_review_task.progress if timeframe_review_task else None,
                "message": timeframe_review_task.message if timeframe_review_task else None
            } if self.current_timeframe_review_task_id else None
        }

    def enable_scheduled_tasks(self, enabled: bool):
        """启用或禁用定时任务"""
        self.enabled = enabled
        logger.info(f"Scheduled tasks {'enabled' if enabled else 'disabled'}")

    def _run_daily_tasks(self):
        """运行每日任务序列"""
        if not self.enabled:
            logger.info("Scheduled tasks are disabled, skipping")
            return

        self.last_run = datetime.now(timezone.utc).isoformat()
        logger.info("Starting daily scheduled tasks")
        
        try:
            # 第一阶段：运行分析任务
            logger.info("Starting analysis phase")
            analysis_task_id = create_analysis_task(
                top_n=20,  # 分析前20个币种
                selected_factors=None,  # 所有因子
                collect_latest_data=True  # 收集最新数据
            )
            self.current_analysis_task_id = analysis_task_id
            logger.info(f"Created analysis task: {analysis_task_id}")
            
            # 等待分析任务完成
            self._wait_for_task_completion(analysis_task_id, "Analysis")
            
            # 第二阶段：运行新闻评估任务
            logger.info("Starting news evaluation phase")
            news_task_id = create_news_evaluation_task(
                top_n=10,  # 评估前10个币种
                news_per_symbol=3,  # 每个币种3条新闻
                openai_model="gpt-oss-120b"  # 默认模型
            )
            self.current_news_task_id = news_task_id
            logger.info(f"Created news evaluation task: {news_task_id}")
            
            # 等待新闻任务完成
            self._wait_for_task_completion(news_task_id, "News evaluation")
            
            # 第三阶段：根据分析结果生成交易信号并发送至 Freqtrade（模拟交易）
            try:
                from freqtrade_client import list_open_trades
                from signal_generator import generate_buy_sell_signals_from_latest

                token = None  # obtain_token() 会在 executor 内部调用，这里只读 open_trades
                open_trades = list_open_trades(token)
                held_pairs = sorted({t.get("pair") for t in open_trades if t.get("pair")})

                signals = generate_buy_sell_signals_from_latest(top_n=5, current_open_positions=held_pairs)
                batch = signals.get("sell", []) + signals.get("buy", [])
                # 发送信号到 Freqtrade（FreqTrade自己配置了dry_run模式）
                result = execute_signals(batch)
                logger.info(f"Trade signals executed (sent to Freqtrade): {result}")
            except Exception as e:
                logger.error(f"Trade signal execution failed: {e}")

            logger.info("Daily scheduled tasks completed successfully")
            
        except Exception as e:
            logger.error(f"Daily scheduled tasks failed: {e}")
        finally:
            # 清理任务ID
            self.current_analysis_task_id = None
            self.current_news_task_id = None

    def _run_candlestick_strategy(self):
        """运行K线策略任务"""
        if not self.enabled:
            logger.info("Scheduled tasks are disabled, skipping candlestick strategy")
            return

        logger.info("Starting candlestick strategy task")
        
        try:
            # 创建一个虚拟任务ID用于进度跟踪
            import uuid
            task_id = str(uuid.uuid4())
            self.current_candlestick_task_id = task_id
            
            # 运行K线策略
            result = run_candlestick_strategy(task_id)
            
        except Exception as e:
            logger.error(f"Candlestick strategy failed: {e}")
        finally:
            # 清理任务ID
            self.current_candlestick_task_id = None

    def _wait_for_task_completion(self, task_id: str, task_name: str, max_wait_seconds: int = 3600):
        """等待任务完成，最多等待1小时"""
        import time
        from utils import get_task
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            task = get_task(task_id)
            if not task:
                logger.error(f"{task_name} task {task_id} not found")
                return
            
            if task.status in ["completed", "failed", "cancelled"]:
                logger.info(f"{task_name} task {task_id} finished with status: {task.status}")
                return
            
            # 每10秒检查一次
            time.sleep(10)
        
        logger.warning(f"{task_name} task {task_id} timed out after {max_wait_seconds} seconds")

    def _run_timeframe_review(self):
        """运行每日交易周期梳理任务，分析上一天各分钟周期的交易适用性"""
        if not self.enabled:
            logger.info("Scheduled tasks are disabled, skipping timeframe review")
            return

        logger.info("Starting daily timeframe review task")
        
        try:
            # 创建一个虚拟任务ID用于进度跟踪
            import uuid
            task_id = str(uuid.uuid4())
            self.current_timeframe_review_task_id = task_id
            
            # 运行时间周期梳理分析
            result = self._analyze_timeframe_performance()
            
            logger.info(f"Timeframe review completed: {result}")
            
        except Exception as e:
            logger.error(f"Timeframe review failed: {e}")
        finally:
            # 清理任务ID
            self.current_timeframe_review_task_id = None

    def _analyze_timeframe_performance(self) -> Dict[str, Any]:
        """分析各时间周期在上一天的交易表现，使用candlestick_strategy的逻辑"""
        from market_data.data_fetcher import fetch_top_symbols_by_turnover
        from candlestick_strategy import CandlestickStrategy
        from datetime import datetime, timedelta
        
        # 获取昨天的日期
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        logger.info(f"Analyzing timeframe performance for {yesterday.date()}")
        
        try:
            # 获取全场成交额最高的10个币种
            top_symbols_df = fetch_top_symbols_by_turnover(top_n=10)
            if top_symbols_df.empty:
                logger.error("No symbols found for timeframe analysis")
                return {"error": "No symbols found"}
            
            symbols = top_symbols_df["symbol"].tolist()  # 分析前10个币种
            
            # 初始化K线策略实例
            strategy = CandlestickStrategy()
            
            # 分析每个币种在各个时间周期的表现
            timeframe_results = {}
            timeframes = strategy.timeframes  # ["3", "5", "10", "15", "30", "60"]
            
            for timeframe in timeframes:
                logger.info(f"Analyzing {timeframe}-minute timeframe")
                
                timeframe_stats = {
                    "consecutive_patterns": [],
                    "avg_consecutive": 0,
                    "max_consecutive": 0,
                    "symbols_analyzed": []
                }
                
                total_consecutive = 0
                max_overall = 0
                valid_symbols = 0
                
                for symbol in symbols:
                    try:
                        # 获取该时间周期的K线数据
                        df = strategy.get_kline_data(symbol, timeframe, limit=200)
                        if df.empty:
                            continue
                        
                        # 计算连续阳线和阴线的最大值 (使用candlestick_strategy的逻辑)
                        bullish_count = strategy.count_consecutive_candles(df, "bullish")
                        bearish_count = strategy.count_consecutive_candles(df, "bearish")
                        max_consecutive = max(bullish_count, bearish_count)
                        
                        total_consecutive += max_consecutive
                        max_overall = max(max_overall, max_consecutive)
                        valid_symbols += 1
                        
                        timeframe_stats["symbols_analyzed"].append({
                            "symbol": symbol,
                            "bullish_consecutive": bullish_count,
                            "bearish_consecutive": bearish_count,
                            "max_consecutive": max_consecutive
                        })
                        
                        timeframe_stats["consecutive_patterns"].append(max_consecutive)
                        
                        logger.debug(f"{symbol} {timeframe}min: {bullish_count} bullish, {bearish_count} bearish, max: {max_consecutive}")
                    
                    except Exception as e:
                        logger.warning(f"Failed to analyze {symbol} for {timeframe}m: {e}")
                        continue
                
                # 计算该时间周期的统计数据
                if valid_symbols > 0:
                    timeframe_stats["avg_consecutive"] = total_consecutive / valid_symbols
                    timeframe_stats["max_consecutive"] = max_overall
                    timeframe_stats["symbols_count"] = valid_symbols
                    
                    # 计算适合交易的评分 (连续性越高越适合趋势交易)
                    score = timeframe_stats["avg_consecutive"] * 0.7 + timeframe_stats["max_consecutive"] * 0.3
                    timeframe_stats["trading_score"] = score
                else:
                    timeframe_stats["avg_consecutive"] = 0
                    timeframe_stats["max_consecutive"] = 0
                    timeframe_stats["symbols_count"] = 0
                    timeframe_stats["trading_score"] = 0
                
                timeframe_results[f"{timeframe}m"] = timeframe_stats
                
                logger.info(f"{timeframe}m analysis: avg={timeframe_stats['avg_consecutive']:.1f}, "
                           f"max={timeframe_stats['max_consecutive']}, score={timeframe_stats['trading_score']:.2f}")
            
            # 找出最佳时间周期并选择最短的4个用于交易
            best_timeframes = self._select_best_timeframes_for_trading(timeframe_results)
            overall_best = best_timeframes[0] if best_timeframes else "15m"
            
            result = {
                "analysis_date": yesterday.date().isoformat(),
                "timeframe_analysis": timeframe_results,
                "best_timeframe": overall_best,
                "selected_timeframes": best_timeframes,
                "trading_symbols": symbols,
                "recommendation": self._generate_timeframe_recommendation_from_consecutive(timeframe_results, overall_best),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "method": "consecutive_candles_analysis"
            }
            
            # 保存结果到文件用于前端展示
            self._save_timeframe_analysis(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Timeframe analysis failed: {e}")
            return {
                "error": str(e),
                "analysis_date": yesterday.date().isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }

    def _select_best_timeframes_for_trading(self, timeframe_results: Dict) -> List[str]:
        """选择过去100根K线中阳线和阴线数量最接近的4个时间周期"""
        from candlestick_strategy import CandlestickStrategy
        import pandas as pd
        
        # 获取一个交易对用于分析（这里使用BTCUSDT作为基准）
        symbol = "BTCUSDT"
        strategy = CandlestickStrategy()
        
        # 存储每个时间周期的阳线和阴线数量差异
        timeframe_diffs = []
        
        for timeframe in timeframe_results.keys():
            # 获取过去100根K线数据
            df = strategy.get_kline_data(symbol, timeframe, limit=100)
            
            if not df.empty:
                # 计算阳线和阴线数量
                bullish_count = df['is_bullish'].sum()
                bearish_count = df['is_bearish'].sum()
                
                # 计算阳线和阴线数量的绝对差异
                diff = abs(bullish_count - bearish_count)
                
                # 存储差异和时间周期
                timeframe_diffs.append((timeframe, diff, bullish_count, bearish_count))
        
        if not timeframe_diffs:
            # 如果没有获取到数据，返回默认时间周期
            return ["5m", "15m", "30m", "1h"]
        
        # 按差异从小到大排序（差异越小，阳线和阴线数量越接近）
        timeframe_diffs.sort(key=lambda x: x[1])
        
        # 选择差异最小的4个时间周期
        selected_timeframes = [item[0] for item in timeframe_diffs[:4]]
        
        # 记录日志
        logger.info(f"Selected timeframes based on balanced candle counts: {selected_timeframes}")
        for tf, diff, bull, bear in timeframe_diffs[:4]:
            logger.info(f"{tf}: {bull} bullish, {bear} bearish, diff={diff}")
        
        # 时间周期分析完成，不再自动下单
            
        return selected_timeframes

    def _generate_timeframe_recommendation_from_consecutive(self, timeframe_results: Dict, best_timeframe: str) -> str:
        """基于连续K线分析生成时间周期推荐说明"""
        if not best_timeframe or best_timeframe not in timeframe_results:
            return "数据不足，建议使用15分钟周期进行交易。"
        
        best_stats = timeframe_results[best_timeframe]
        avg_consecutive = best_stats.get("avg_consecutive", 0)
        max_consecutive = best_stats.get("max_consecutive", 0)
        trading_score = best_stats.get("trading_score", 0)
        symbols_count = best_stats.get("symbols_count", 0)
        
        recommendation = f"推荐使用 {best_timeframe} 周期进行交易。"
        recommendation += f"该周期昨日平均连续K线数为 {avg_consecutive:.1f}，"
        recommendation += f"最大连续数为 {max_consecutive}，"
        recommendation += f"分析了 {symbols_count} 个币种。"
        
        if avg_consecutive >= 4:
            recommendation += " 连续性较强，适合趋势跟随交易。"
        elif avg_consecutive >= 2:
            recommendation += " 连续性中等，适合短期交易。"
        else:
            recommendation += " 连续性较弱，建议观望或使用更长时间周期。"
        
        if max_consecutive >= 6:
            recommendation += f" 出现了 {max_consecutive} 根连续K线，显示较强的趋势性。"
        
        return recommendation

    def _save_timeframe_analysis(self, result: Dict):
        """保存时间周期分析结果"""
        import json
        import os
        
        # 确保目录存在
        os.makedirs("debug_output", exist_ok=True)
        
        # 保存详细分析结果
        output_file = "debug_output/timeframe_analysis.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 保存简化摘要
        summary_file = "debug_output/timeframe_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(f"时间周期分析摘要 - {result.get('analysis_date', 'Unknown')}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"分析方法: {result.get('method', 'consecutive_candles_analysis')}\n\n")
            
            if "timeframe_analysis" in result:
                f.write("各时间周期表现:\n")
                for timeframe, stats in result["timeframe_analysis"].items():
                    f.write(f"\n{timeframe}:\n")
                    f.write(f"  平均连续K线数: {stats.get('avg_consecutive', 0):.1f}\n")
                    f.write(f"  最大连续K线数: {stats.get('max_consecutive', 0)}\n")
                    f.write(f"  交易评分: {stats.get('trading_score', 0):.2f}\n")
                    f.write(f"  分析币种数: {stats.get('symbols_count', 0)}\n")
                    
                    # 显示前几个币种的详细数据
                    symbols_analyzed = stats.get('symbols_analyzed', [])
                    if symbols_analyzed:
                        f.write(f"  币种详情:\n")
                        for symbol_data in symbols_analyzed[:3]:  # 只显示前3个
                            f.write(f"    {symbol_data.get('symbol', '')}: "
                                   f"多头{symbol_data.get('bullish_consecutive', 0)} "
                                   f"空头{symbol_data.get('bearish_consecutive', 0)} "
                                   f"最大{symbol_data.get('max_consecutive', 0)}\n")
                        if len(symbols_analyzed) > 3:
                            f.write(f"    ... (还有{len(symbols_analyzed)-3}个币种)\n")
            
            f.write(f"\n推荐周期: {result.get('best_timeframe', 'Unknown')}\n")
            f.write(f"推荐说明: {result.get('recommendation', 'No recommendation')}\n")
        
        logger.info(f"Timeframe analysis saved to {output_file} and {summary_file}")

    def _place_minimal_test_position(self):
        """在时间周期分析后下一个最小底仓进行测试"""
        try:
            from freqtrade_client import health, list_open_trades, forceentry
            
            # 检查 Freqtrade API 是否可用
            if not health():
                logger.warning("Freqtrade API not available, skipping minimal test position")
                return
            
            # 获取当前持仓
            current_trades = list_open_trades()
            held_pairs = {t.get("pair") for t in current_trades if t.get("pair")}
            
            logger.info(f"Current positions: {len(current_trades)}, pairs: {list(held_pairs)}")
            
            # 定义测试用的交易对和最小金额
            test_pairs = ["SOL/USDT", "ADA/USDT", "DOT/USDT", "AVAX/USDT", "LINK/USDT"]
            minimal_stake = 5.0  # 最小测试金额 $5
            
            # 选择一个还没有持仓的交易对
            available_pairs = [pair for pair in test_pairs if pair not in held_pairs]
            
            if not available_pairs:
                logger.info("All test pairs already have positions, skipping minimal test position")
                return
            
            # 选择第一个可用的交易对
            selected_pair = available_pairs[0]
            
            logger.info(f"Placing minimal test position: {selected_pair} with ${minimal_stake}")
            
            # 下单
            success = forceentry(selected_pair, stake_amount=minimal_stake)
            
            if success:
                logger.info(f"✅ Minimal test position placed successfully: {selected_pair}")
            else:
                # 如果下单失败，可能是达到最大持仓限制，先平掉一个现有持仓再重试
                logger.warning(f"❌ Failed to place minimal test position: {selected_pair}")
                logger.info("Attempting to close an existing position and retry...")
                
                if current_trades:
                    from freqtrade_client import forceexit_by_pair
                    
                    # 选择一个现有持仓平掉（选择第一个非测试币种的持仓）
                    existing_pairs = list(held_pairs)
                    pair_to_close = None
                    
                    # 优先关闭非测试币种的持仓
                    for pair in existing_pairs:
                        if pair not in test_pairs:
                            pair_to_close = pair
                            break
                    
                    # 如果没有非测试币种，就关闭第一个
                    if not pair_to_close and existing_pairs:
                        pair_to_close = existing_pairs[0]
                    
                    if pair_to_close:
                        logger.info(f"Attempting to close position: {pair_to_close}")
                        try:
                            closed_count = forceexit_by_pair(pair_to_close)
                            logger.info(f"forceexit_by_pair returned: {closed_count} position(s) closed")
                            
                            if closed_count > 0:
                                logger.info(f"✅ Successfully closed {closed_count} position(s) for {pair_to_close}")
                                
                                # 等待一下让平仓完成
                                import time
                                wait_time = 5
                                logger.info(f"Waiting {wait_time} seconds for position closure to complete...")
                                time.sleep(wait_time)
                                
                                # 重试下测试单
                                logger.info(f"Retrying to place minimal test position: {selected_pair}")
                                try:
                                    retry_success = forceentry(selected_pair, stake_amount=minimal_stake)
                                    logger.info(f"forceentry returned: {retry_success}")
                                    
                                    if retry_success:
                                        logger.info(f"✅ Minimal test position placed successfully after retry: {selected_pair}")
                                    else:
                                        logger.warning(f"❌ Retry failed for minimal test position: {selected_pair} (forceentry returned False)")
                                except Exception as entry_error:
                                    logger.error(f"❌ Error in forceentry call: {str(entry_error)}", exc_info=True)
                                    raise
                            else:
                                logger.warning(f"❌ No positions were closed for {pair_to_close} (forceexit_by_pair returned 0)")
                        except Exception as exit_error:
                            logger.error(f"❌ Error in forceexit_by_pair call: {str(exit_error)}", exc_info=True)
                            raise
                        else:
                            logger.warning(f"Failed to close existing position: {pair_to_close}")
        except Exception as e:
            logger.error(f"Error placing minimal test position: {e}", exc_info=True)
            raise
        finally:
            logger.info("=== Completed startup test position placement ===")

    def _startup_test_position(self):
        """启动时测试一次最小底仓下单（仅启动时执行）"""
        logger.info("=== Starting startup test position placement ===")
        try:
            # 调用下单测试方法
            self._place_minimal_test_position()
            logger.info("=== Startup test completed ===")
        except Exception as e:
            logger.error(f"Startup test failed: {e}")

# 全局调度器实例
task_scheduler = TaskScheduler()

def start_scheduler():
    """启动全局调度器"""
    task_scheduler.start()

def stop_scheduler():
    """停止全局调度器"""
    task_scheduler.stop()

def get_scheduler_status():
    """获取调度器状态"""
    return task_scheduler.get_status()


def run_daily_tasks_now() -> bool:
    """手动立即触发一次每日任务（异步加入调度器队列）"""
    try:
        task_scheduler.scheduler.add_job(
            func=task_scheduler._run_daily_tasks,
            trigger=DateTrigger(run_date=datetime.now(timezone.utc) + timedelta(seconds=1)),
            id="manual_daily_run",
            name="Manual Daily Run",
            replace_existing=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to schedule manual daily run: {e}")
        return False

def stop_current_scheduled_task():
    """停止当前运行的定时任务"""
    return task_scheduler.stop_current_tasks()

def enable_scheduled_tasks(enabled: bool):
    """启用或禁用定时任务"""
    task_scheduler.enable_scheduled_tasks(enabled)