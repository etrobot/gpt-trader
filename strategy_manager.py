#!/usr/bin/env python3
"""
Freqtrade 策略管理器
基于回测结果优化和更新策略
"""

import json
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


class StrategyManager:
    """策略管理器"""
    
    def __init__(self, strategy_dir="user_data/strategies"):
        self.strategy_dir = Path(strategy_dir)
        self.backup_dir = Path("user_data/strategy_backups")
        self.backup_dir.mkdir(exist_ok=True)
        self.results_dir = Path("user_data/backtest_results")
    
    def get_latest_results(self) -> Optional[Dict]:
        """获取最新的回测结果"""
        if not self.results_dir.exists():
            return None
        
        result_files = list(self.results_dir.glob("*.json"))
        if not result_files:
            return None
        
        latest_result = max(result_files, key=lambda x: x.stat().st_mtime)
        
        try:
            with open(latest_result, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"读取结果文件失败: {e}")
            return None
    
    def backup_strategy(self, strategy_name: str) -> str:
        """备份策略文件"""
        strategy_file = self.strategy_dir / f"{strategy_name}.py"
        if not strategy_file.exists():
            raise FileNotFoundError(f"策略文件不存在: {strategy_file}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{strategy_name}_backup_{timestamp}.py"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(strategy_file, backup_path)
        print(f"✅ 策略已备份: {backup_path}")
        return str(backup_path)
    
    def create_optimized_strategy(self, base_strategy: str, results: Dict, new_name: str = None) -> str:
        """基于回测结果创建优化策略副本"""
        
        # 读取原策略
        strategy_file = self.strategy_dir / f"{base_strategy}.py"
        with open(strategy_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分析结果并生成优化参数
        optimized_params = self._analyze_results_for_optimization(results)
        
        # 生成新策略名称
        if not new_name:
            timestamp = datetime.now().strftime("%m%d_%H%M")
            new_name = f"{base_strategy}_optimized_{timestamp}"
        
        # 更新策略内容
        new_content = self._update_strategy_content(content, base_strategy, new_name, optimized_params, results)
        
        # 保存新策略
        new_file = self.strategy_dir / f"{new_name}.py"
        with open(new_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ 新策略已创建: {new_file}")
        return new_name
    
    def copy_strategy(self, source_strategy: str, new_name: str) -> str:
        """复制策略文件（不做优化）"""
        
        # 读取源策略
        source_file = self.strategy_dir / f"{source_strategy}.py"
        if not source_file.exists():
            raise FileNotFoundError(f"源策略文件不存在: {source_file}")
        
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查新策略是否已存在
        new_file = self.strategy_dir / f"{new_name}.py"
        if new_file.exists():
            raise FileExistsError(f"策略文件已存在: {new_file}")
        
        # 更新类名和注释
        new_content = self._update_strategy_name_only(content, source_strategy, new_name)
        
        # 保存新策略
        with open(new_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ 策略已复制: {new_file}")
        return new_name
    
    def update_existing_strategy(self, strategy_name: str, results: Dict) -> bool:
        """直接更新现有策略"""
        
        # 先备份
        self.backup_strategy(strategy_name)
        
        # 读取策略文件
        strategy_file = self.strategy_dir / f"{strategy_name}.py"
        with open(strategy_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 分析结果并生成优化参数
        optimized_params = self._analyze_results_for_optimization(results)
        
        # 更新策略内容（保持原名称）
        new_content = self._update_strategy_content(content, strategy_name, strategy_name, optimized_params, results)
        
        # 保存更新的策略
        with open(strategy_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ 策略已更新: {strategy_file}")
        return True
    
    def _analyze_results_for_optimization(self, results: Dict) -> Dict:
        """分析回测结果，生成优化建议"""
        strategy_results = results.get('strategy', {})
        
        if not strategy_results:
            return {}
        
        # 获取策略统计数据
        strategy_name = list(strategy_results.keys())[0]
        stats = strategy_results[strategy_name]
        
        optimizations = {}
        
        # 基于回测结果调整参数
        profit_total = stats.get('profit_total', 0)
        max_drawdown = stats.get('max_drawdown', 0)
        win_rate = stats.get('wins', 0) / max(stats.get('trades', 1), 1)
        
        # ROI 调整
        if profit_total > 0.1:  # 高收益
            optimizations['roi'] = {
                "0": 0.03,
                "30": 0.015,
                "60": 0.008,
                "120": 0
            }
        elif profit_total > 0.05:  # 中等收益
            optimizations['roi'] = {
                "0": 0.025,
                "35": 0.012,
                "70": 0.006,
                "140": 0
            }
        else:  # 保守策略
            optimizations['roi'] = {
                "0": 0.02,
                "40": 0.01,
                "80": 0.005,
                "160": 0
            }
        
        # 止损调整
        if max_drawdown > 0.15:  # 高回撤，收紧止损
            optimizations['stoploss'] = -0.03
        elif max_drawdown > 0.10:
            optimizations['stoploss'] = -0.04
        else:
            optimizations['stoploss'] = -0.05
        
        # 胜率调整
        if win_rate < 0.4:  # 低胜率，调整过滤条件
            optimizations['rsi_filter'] = 75  # 更严格的RSI过滤
        elif win_rate > 0.7:  # 高胜率，可以放宽
            optimizations['rsi_filter'] = 85
        
        return optimizations
    
    def _update_strategy_content(self, content: str, old_name: str, new_name: str, 
                                optimizations: Dict, results: Dict) -> str:
        """更新策略文件内容"""
        lines = content.split('\n')
        updated_lines = []
        
        # 添加优化注释
        optimization_header = f"""
# 策略优化版本 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 基于回测结果自动优化
# 原策略: {old_name}
# 优化数据: 收益 {results.get('strategy', {}).get(list(results.get('strategy', {}).keys())[0] if results.get('strategy') else '', {}).get('profit_total', 0):.2%}, 
#          胜率 {results.get('strategy', {}).get(list(results.get('strategy', {}).keys())[0] if results.get('strategy') else '', {}).get('wins', 0) / max(results.get('strategy', {}).get(list(results.get('strategy', {}).keys())[0] if results.get('strategy') else '', {}).get('trades', 1), 1):.1%}
"""
        
        for i, line in enumerate(lines):
            # 更新类名
            if f'class {old_name}(' in line:
                updated_lines.append(optimization_header)
                updated_lines.append(line.replace(old_name, new_name))
                continue
            
            # 更新 ROI
            if 'minimal_roi = {' in line and 'roi' in optimizations:
                updated_lines.append('    minimal_roi = {')
                for time_key, roi_value in optimizations['roi'].items():
                    updated_lines.append(f'        "{time_key}": {roi_value},')
                updated_lines.append('    }')
                # 跳过原来的ROI定义
                while i + 1 < len(lines) and '}' not in lines[i + 1]:
                    i += 1
                continue
            
            # 更新止损
            if 'stoploss = ' in line and 'stoploss' in optimizations:
                updated_lines.append(f'    stoploss = {optimizations["stoploss"]}  # 优化后止损')
                continue
            
            # 更新RSI过滤条件
            if 'rsi' in line and '<' in line and 'rsi_filter' in optimizations:
                updated_lines.append(line.replace('< 80', f'< {optimizations["rsi_filter"]}'))
                continue
            
            updated_lines.append(line)
        
        return '\n'.join(updated_lines)
    
    def _update_strategy_name_only(self, content: str, old_name: str, new_name: str) -> str:
        """仅更新策略名称，不做优化"""
        lines = content.split('\n')
        updated_lines = []
        
        # 添加复制说明
        copy_header = f"""
# 策略副本 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 源策略: {old_name}
# 新策略: {new_name}
"""
        
        for line in lines:
            # 更新类名
            if f'class {old_name}(' in line:
                updated_lines.append(copy_header)
                updated_lines.append(line.replace(old_name, new_name))
                continue
            
            updated_lines.append(line)
        
        return '\n'.join(updated_lines)
    
    def list_strategies(self) -> list:
        """列出所有策略文件"""
        strategies = []
        for strategy_file in self.strategy_dir.glob("*.py"):
            if strategy_file.name != "__init__.py":
                strategies.append(strategy_file.stem)
        return strategies
    
    def list_backups(self) -> list:
        """列出所有备份文件"""
        backups = []
        for backup_file in self.backup_dir.glob("*.py"):
            backups.append(backup_file.name)
        return sorted(backups, reverse=True)


def main():
    """交互式策略管理"""
    manager = StrategyManager()
    
    print("🎯 策略管理器")
    print("=" * 30)
    
    # 获取最新结果
    results = manager.get_latest_results()
    if not results:
        print("❌ 未找到回测结果")
        return
    
    print("✅ 发现最新回测结果")
    
    # 显示当前策略
    strategies = manager.list_strategies()
    print(f"📁 当前策略: {', '.join(strategies)}")
    
    print("\n请选择操作:")
    print("1) 创建优化策略副本")
    print("2) 复制策略(无优化)")
    print("3) 直接更新现有策略") 
    print("4) 查看策略备份")
    print("5) 退出")
    
    choice = input("\n选择 (1-5): ").strip()
    
    if choice == "1":
        base_strategy = input("请输入基础策略名称 (默认: ClassicStrategy): ").strip() or "ClassicStrategy"
        new_name = input("请输入新策略名称 (留空自动生成): ").strip() or None
        
        try:
            new_strategy = manager.create_optimized_strategy(base_strategy, results, new_name)
            print(f"🎉 优化策略已创建: {new_strategy}")
        except Exception as e:
            print(f"❌ 创建失败: {e}")
    
    elif choice == "2":
        source_strategy = input("请输入源策略名称 (默认: ClassicStrategy): ").strip() or "ClassicStrategy"
        new_name = input("请输入新策略名称: ").strip()
        
        if not new_name:
            print("❌ 新策略名称不能为空")
            return
            
        try:
            manager.copy_strategy(source_strategy, new_name)
            print(f"🎉 策略已复制: {source_strategy} → {new_name}")
        except Exception as e:
            print(f"❌ 复制失败: {e}")
    
    elif choice == "3":
        strategy_name = input("请输入要更新的策略名称 (默认: ClassicStrategy): ").strip() or "ClassicStrategy"
        
        confirm = input(f"⚠️  确认要更新策略 '{strategy_name}' 吗？(y/n): ").strip().lower()
        if confirm == 'y':
            try:
                manager.update_existing_strategy(strategy_name, results)
                print(f"🎉 策略已更新: {strategy_name}")
            except Exception as e:
                print(f"❌ 更新失败: {e}")
        else:
            print("❌ 操作已取消")
    
    elif choice == "4":
        backups = manager.list_backups()
        if backups:
            print("📚 策略备份文件:")
            for backup in backups[:10]:  # 显示最新10个
                print(f"  - {backup}")
        else:
            print("📁 没有备份文件")
    
    else:
        print("👋 退出策略管理器")


if __name__ == "__main__":
    main()