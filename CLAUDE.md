# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Docker-based Freqtrade setup for cryptocurrency trading using a price-action candlestick pattern strategy. The system supports dry-run simulation trading on exchanges like OKX and Binance, with a focus on pure OHLC-based strategy without technical indicators or volume analysis.

**Main Strategy**: `PriceActionStrategy` - A layered candlestick strategy featuring preprocessing, trend/amplitude tools, and breakout/rebound entry conditions with fixed 5-candle exits.

## Common Development Commands

### Deployment and Management
```bash
# Deploy the system (generates .env, configures, starts services)
./deploy.sh

# Update exchange API credentials for live trading
./update_exchange_credentials.sh

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart services
docker-compose restart
```

### Freqtrade Operations (via Docker)
```bash
# Download market data
docker-compose run --rm freqtrade download-data --exchange okx --pairs BTC/USDT ETH/USDT --timeframes 5m --days 30

# Run backtesting
docker-compose run --rm freqtrade backtesting --strategy PriceActionStrategy --timerange 20240101-

# Hyperopt optimization
docker-compose run --rm freqtrade hyperopt --strategy PriceActionStrategy --epochs 100

# Start/stop trading (via API or restart container)
# See API endpoints at http://localhost:6677 (development) or configured domain
```

## Architecture & Key Components

### Core Files
- **`deploy.sh`**: Deployment script that sets up .env, generates credentials, updates Freqtrade config, and starts Docker services.
- **`docker-compose.yml`**: Defines the Freqtrade service with volume mounts for user_data and data persistence.
- **`update_exchange_credentials.sh`**: Script to update OKX/Binance API keys for transitioning from dry-run to live trading.
- **`user_data_template/`**: Source templates for Freqtrade configuration and strategies, copied to `user_data/` during deployment.

### Strategy System
- **`user_data/strategies/price-act_strategy.py`**: Implements the main trading logic.
  - **Preprocessing**: Computes bullish/bearish markers, signed lengths, multi-timeframe (5m/10m/15m/30m/60m) simulations.
  - **Tools**: Trend judgment (segmented close comparison), amplitude enhancement (rolling quantile).
  - **Entries**: Use any of these： Breakout (uptrend + enhanced amplitude + 2 bullish candles); Rebound (downtrend + enhanced + 1 bullish + >60% bearish recent).
  - **Exits**: Fixed 5-candle hold (25 minutes on 5m timeframe) or 5% stoploss; ROI table for 10% target.
- **Config**: `user_data/config_price-act_strategy.json` - Freqtrade configuration with API server enabled (port 8080), dry-run mode, pair whitelist (BTC/USDT, ETH/USDT), 5m timeframe.

### Data Flow
1. Deployment copies templates to `user_data/`, generates secure credentials, starts Freqtrade container.
2. Freqtrade loads strategy and config, downloads data to `user_data/data/`.
3. Simulation trading runs via API start command; results persist in `data/` (SQLite DB) and logs.
4. For backtesting/hyperopt, run Freqtrade commands via docker-compose; results in `user_data/backtest_results/` and `hyperopt_results/`.

### Important Considerations
- **Dry-Run Only**: Default mode is simulation (no real trades). Update credentials for live trading.
- **No External Dependencies**: Strategy uses only pandas/numpy from Freqtrade environment; no TA-Lib or custom installs.
- **Multi-Timeframe**: Internal simulation of higher timeframes without resampling.
- **Security**: Credentials in .env (gitignored); API exposed on 6677 (dev) or domain (prod) with JWT/WS auth.
- **Persistence**: Database in `./data/crypto_data.db`; strategy backups not implemented (manual via git).