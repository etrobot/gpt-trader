#!/usr/bin/env python3
"""
基于 Docker Freqtrade 的策略回测脚本
"""

import subprocess
import sys
import json
import os
from pathlib import Path
import argparse


def check_container_status():
    """检查容器运行状态"""
    try:
        result = subprocess.run(
            ["docker-compose", "ps", "-q", "freqtrade"], 
            capture_output=True, text=True
        )
        container_id = result.stdout.strip()
        
        if container_id:
            # 检查容器是否在运行
            status_result = subprocess.run(
                ["docker", "inspect", "--format={{.State.Status}}", container_id],
                capture_output=True, text=True
            )
            return status_result.stdout.strip() == "running", container_id
        return False, None
    except Exception:
        return False, None


def run_docker_freqtrade(action, strategy="ClassicStrategy", timeframe="5m", timerange="20240101-", epochs=100):
    """运行 Docker Freqtrade 命令"""
    
    # 检查容器状态
    is_running, container_id = check_container_status()
    
    if is_running:
        print(f"⚠️  检测到 Freqtrade 容器正在运行 (ID: {container_id[:12]})")
        print("选择操作:")
        print("1) 停止容器并执行新命令")
        print("2) 在运行的容器中执行命令")
        print("3) 取消操作")
        
        choice = input("请选择 (1-3): ").strip()
        
        if choice == "1":
            print("🛑 停止运行中的容器...")
            subprocess.run(["docker-compose", "stop", "freqtrade"])
            base_cmd = ["docker-compose", "run", "--rm", "freqtrade"]
        elif choice == "2":
            print("🔄 在运行容器中执行命令...")
            base_cmd = ["docker-compose", "exec", "freqtrade"]
        else:
            print("❌ 操作已取消")
            return False
    else:
        # 容器未运行，使用 run 命令
        base_cmd = ["docker-compose", "run", "--rm", "freqtrade"]
    
    if action == "backtest":
        cmd = base_cmd + [
            "backtesting",
            "--strategy", strategy,
            "--timeframe", timeframe,
            "--timerange", timerange,
            "--config", "user_data/config_external_signals.json"
        ]
        print(f"📊 运行回测: {strategy}")
        
    elif action == "hyperopt":
        cmd = base_cmd + [
            "hyperopt",
            "--strategy", strategy,
            "--epochs", str(epochs),
            "--hyperopt-loss", "SharpeHyperOptLoss",
            "--config", "user_data/config_external_signals.json"
        ]
        print(f"⚙️ 参数优化: {strategy} ({epochs} 轮)")
        
    elif action == "download":
        cmd = base_cmd + [
            "download-data",
            "--exchange", "binance",
            "--pairs", "BTC/USDT", "ETH/USDT",
            "--timeframes", timeframe,
            "--days", "30",
            "--config", "user_data/config_external_signals.json"
        ]
        print("📥 下载数据...")
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"执行失败: {e}")
        return False


def show_results():
    """显示回测结果"""
    results_dir = Path("user_data/backtest_results")
    if results_dir.exists():
        result_files = list(results_dir.glob("*.json"))
        if result_files:
            latest_result = max(result_files, key=lambda x: x.stat().st_mtime)
            print(f"📊 最新结果: {latest_result}")
            
            with open(latest_result, 'r') as f:
                data = json.load(f)
                
            # 显示关键指标
            if 'strategy' in data and 'ClassicStrategy' in data['strategy']:
                stats = data['strategy']['ClassicStrategy']
                print("\n📈 回测结果:")
                print(f"总收益: {stats.get('profit_total_abs', 0):.2f}")
                print(f"收益率: {stats.get('profit_total', 0):.2%}")
                print(f"交易次数: {stats.get('trades', 0)}")
                print(f"胜率: {stats.get('wins', 0)/stats.get('trades', 1)*100:.1f}%")
                print(f"最大回撤: {stats.get('max_drawdown', 0):.2%}")
        else:
            print("没有找到回测结果")
    else:
        print("没有找到结果目录")


def main():
    parser = argparse.ArgumentParser(description='Docker Freqtrade 策略分析工具')
    parser.add_argument('--action', choices=['backtest', 'hyperopt', 'download', 'results', 'optimize-strategy'], 
                       default='backtest', help='执行的操作')
    parser.add_argument('--strategy', default='ClassicStrategy', help='策略名称')
    parser.add_argument('--timeframe', default='5m', help='时间周期')
    parser.add_argument('--timerange', default='20240101-', help='时间范围')
    parser.add_argument('--epochs', type=int, default=100, help='优化轮数')
    
    args = parser.parse_args()
    
    if args.action in ['backtest', 'hyperopt', 'download']:
        success = run_docker_freqtrade(
            args.action, 
            args.strategy, 
            args.timeframe, 
            args.timerange, 
            args.epochs
        )
        if success and args.action == 'backtest':
            show_results()
            # 询问是否要优化策略
            optimize = input("\n🎯 是否基于结果优化策略？(y/n): ").strip().lower()
            if optimize == 'y':
                import subprocess
                subprocess.run(["python", "strategy_manager.py"])
    elif args.action == 'results':
        show_results()
    elif args.action == 'optimize-strategy':
        import subprocess
        subprocess.run(["python", "strategy_manager.py"])


if __name__ == "__main__":
    main()