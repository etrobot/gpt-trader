# 🚀 Docker Freqtrade 策略系统

基于 Docker 部署的 Freqtrade K线形态交易策略。

## ✨ 功能

- 📊 **策略回测**: 使用 Freqtrade 回测引擎
- ⚙️ **参数优化**: Freqtrade hyperopt 优化  
- 📥 **数据下载**: 自动下载交易数据
- 🎯 **策略管理**: 基于回测结果自动优化策略
- 🐳 **Docker 部署**: 容器化运行

## 🎯 策略介绍

纯K线策略 (`PriceActionStrategy`)，完全基于开高低收价格数据，拒绝技术指标和量能分析：

**策略架构 - 分层结构:**
- **第零层：K线预处理** - 基础K线属性计算和多周期封装
- **第一层：基础判断方法** - 趋势判断、波幅增强检测
- **第二层：组合策略入场** - 突破入场、抢反弹策略
- **第三层：简单出场条件** - 75分钟强制离场

**入场条件示例:**
- **突破入场**：趋势上升 + 波幅增强 + 最后2根阳线
- **抢反弹**：趋势下降 + 波幅增强 + 1根阳线 + 近期阴线比例>60%

**出场机制:**
- 75分钟强制出场
- 5%止损保护
- ROI目标：初始10%

## 🚀 快速开始

```bash
# 1. 启动交互式菜单
./run_analysis.sh

# 2. 直接使用 Python 脚本
python backtest.py --action backtest
python backtest.py --action hyperopt --epochs 50
```

## 📁 项目结构

```
├── docker-cprice-act_strategy  # Docker 配置
├── backtest.py              # 回测分析脚本
├── strategy_maprice-act_strategy 策略管理器
├── run_analysis.sh          # 交互式启动
├── user_data/
│   ├── strategies/
│   │   └── price-act_strategy.py  # K线形态策略
│   ├── strategy_backups/     # 策略备份目录
│   └── config_price-act_strategy.json  # Freqtrade 配置
└── pyproject.toml           # 项目配置
```

## 🐳 Docker 使用

```bash
# 下载数据
docker-compose run --rm freqtrade download-data --exchange binance --pairs BTC/USDT --timeframes 5m --days 30

# 策略回测
docker-compose run --rm freqtrade backtesting --strategy PriceActionStrategy --timerange 20240101-

# 参数优化
docker-compose run --rm freqtrade hyperopt --strategy PriceActionStrategy --epochs 100

# 策略管理
python strategy_manager.py
```

## 🎯 策略管理

系统提供完整的策略管理功能：

### 1. 创建优化副本 🧠
- 基于回测结果创建新的优化策略
- 保留原策略不变
- 智能调整 ROI、止损、过滤条件
- 文件名：`PriceActionStrategy_optimized_1219_1430.py`

### 2. 复制策略 📋
- **用户输入策略名**复制出新策略
- **源策略保持不动**
- 仅更新类名，不做参数优化
- 适合创建策略变体进行测试

### 3. 直接更新现有策略 🔄
- 自动备份原策略到 `user_data/strategy_backups/`
- 直接优化现有策略文件
- 基于回测数据智能调整参数

### 使用场景
```bash
# 场景1：测试新想法
./run_analysis.sh -> 5) 策略管理 -> 2) 复制策略
输入源策略: PriceActionStrategy
输入新策略: MyTestStrategy

# 场景2：优化现有策略
./run_analysis.sh -> 2) 策略回测 -> 完成后选择优化

# 场景3：手动管理
python strategy_manager.py
```

### 智能优化逻辑
- **高收益** (>10%): 更激进的ROI设置
- **高回撤** (>15%): 收紧止损保护  
- **低胜率** (<40%): 增强过滤条件
- **高胜率** (>70%): 适当放宽条件

### 文件管理
- 📁 **策略目录**: `user_data/strategies/`
- 💾 **备份目录**: `user_data/strategy_backups/`
- 🏷️ **命名规范**: `策略名_backup_20241219_143012.py`