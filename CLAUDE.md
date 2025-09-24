# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Docker-based cryptocurrency trading bot system built on Freqtrade framework. It implements automated backtesting, optimization, and strategy management for trading based on candlestick patterns (K线形态).

**Main Strategy**: `ClassicStrategy` - A candlestick pattern strategy that trades on consecutive bullish/bearish candle sequences with specific entry and exit conditions.

## Common Development Commands

### Quick Start
```bash
# Interactive menu system
./run_analysis.sh

# Direct Python commands
python backtest.py --action backtest
python backtest.py --action hyperopt --epochs 50
python strategy_manager.py
```

### Docker Operations
```bash
# Download market data
docker-compose run --rm freqtrade download-data --exchange binance --pairs BTC/USDT --timeframes 5m --days 30

# Run backtesting
docker-compose run --rm freqtrade backtesting --strategy ClassicStrategy --timerange 20240101-

# Parameter optimization
docker-compose run --rm freqtrade hyperopt --strategy ClassicStrategy --epochs 100

# Start trading container
docker-compose up -d freqtrade
```

### Strategy Operations
```bash
# Strategy management (creates/modifies strategies based on backtest results)
python strategy_manager.py
```

## Architecture & Key Components

### Core Scripts
- **`backtest.py`**: Main interface for Docker Freqtrade operations (backtest/download/hyperopt)
- **`strategy_manager.py`**: Strategy management system for creating/optimizing/modifying strategies
- **`run_analysis.sh`**: Interactive CLI menu for all operations
- **`docker-compose.yml`**: Freqtrade service configuration

### Strategy System
- **`user_data/strategies/classic_strategy.py`**: Main candlestick pattern strategy
- **Strategy logic**: 3 bullish candles → 10 period consolidation → buy signal
- **Entry conditions**: Consecutive bullish patterns + technical filters (RSI, EMA)
- **Exit conditions**: Time-based (7 candles), bearish patterns, RSI extremes
- **Risk management**: 5% stop loss, ROI table with decreasing targets

### Configuration Structure
- **`user_data/config_classic_strategy.json`**: Main Freqtrade configuration
- **`.env`**: API keys and sensitive settings
- **`user_data/strategy_backups/`**: Automatic strategy backups before modifications
- **`user_data/backtest_results/`**: Backtest and optimization results storage

### Strategy Management Workflow
1. StrategyManager analyzes latest backtest results
2. Creates optimized strategy based on performance (ROI, drawdown, win rate)
3. Offers three modes: create new optimized copy, replicate strategy, or update existing
4. Automatic backup system prevents data loss

## Key Technical Details

### Data Flow
1. Historical data downloads via Freqtrade Docker container
2. Backtesting produces JSON results in user_data/backtest_results/
3. StrategyManager reads results to create optimized strategies
4. Strategies automatically backed up before modification

### Pattern Recognition
- Consecutive candle counting (bullish/bearish sequences)
- Consolidation detection (sideways movement analysis)
- Combined with technical indicators (RSI, EMA20)
- Multi-timeframe analysis capabilities

### Optimization Logic
- High returns (>10%): More aggressive ROI settings
- High drawdown (>15%): Tighter stoploss protection
- Low win rate (<40%): Enhanced filtering conditions
- High win rate (>70%): Relaxed conditions for more trades

## Important Considerations

DONT USE TALIB! JUST USE CANDELS TO MAKE A STRATEGY!

### Strategy Naming
- Optimized strategies follow pattern: `ClassicStrategy_optimized_MMDD_HHMM.py`
- Backup files: `StrategyName_backup_YYMMDD_HHMMSS.py`
- Strategy class names must match filename (without .py extension)

### Container Management
- Check running container status before operations
- Freqtrade container exposes API on port 8080 (mapped to 6677)
- Container restart policies for production deployment

### Market Data
- Supports multiple exchanges (Binance, OKX)
- Configurable timeframes (default: 5m)
- Automatic data download for optimization periods