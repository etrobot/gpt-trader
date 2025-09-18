# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack cryptocurrency trading analysis platform that integrates technical analysis, AI-powered news evaluation, and automated trading through FreqTrade. The platform features a modern React frontend with a FastAPI backend, all containerized with Docker for easy deployment.

### Tech Stack

- **Frontend**: React with TypeScript, Vite, Tailwind CSS, Radix UI components, D3.js for charts
- **Backend**: FastAPI (Python), SQLite with SQLModel ORM, APScheduler for task scheduling
- **Trading**: FreqTrade integration for automated trading
- **AI Integration**: OpenAI API for news evaluation and market analysis
- **Deployment**: Docker and Docker Compose with Traefik reverse proxy

### Project Structure
```
.
├── backend/                    # FastAPI backend
│   ├── data_management/       # Data handling and persistence
│   ├── factors/               # Technical analysis factors
│   ├── llm_utils/             # LLM integration utilities
│   ├── market_data/           # Market data processing
│   ├── news_data/             # News data handling
│   └── static/                # Static assets
├── frontend/                   # React frontend
│   └── app/                   # Main application code
├── user_data/                  # FreqTrade configuration
├── data/                      # Persistent data storage
└── scripts/                   # Utility scripts
```

## Development Commands

### Prerequisites
- Node.js with pnpm
- Python with UV package manager
- Docker and Docker Compose (for deployment)

### Quick Start
```bash
# 1. Install all dependencies (frontend and backend)
pnpm run install:all

# 2. Run development servers (both frontend and backend)
pnpm run dev

# 3. Build for production
pnpm run build
```

### Development Workflow
- **Frontend**: `pnpm run dev:frontend` - Run Vite development server on port 14245
- **Backend**: `pnpm run dev:backend` - Run FastAPI/Uvicorn with auto-reload on port 14250
- **Both**: `pnpm run dev` - Run both frontend and backend concurrently using concurrently

### Testing
Limited formal testing. Manual smoke tests via scripts/smoke_test.sh and factor validation scripts.

### Deployment
```bash
# Deploy with demo settings (safe!)
./deploy.sh

# After deployment, update with real credentials when ready
./update_openai_credentials.sh
./update_exchange_credentials.sh  # For live trading
```

## Architecture Overview

### Backend (FastAPI)
1. **Main Application** (`backend/main.py`):
   - FastAPI application with CORS middleware
   - Static file serving for frontend
   - Background task scheduler integration
   - Authentication system with admin users

2. **Database Models** (`backend/models.py`):
   - SQLModel ORM with SQLite backend
   - User model with admin flag
   - Task management models with status tracking

3. **API Endpoints** (`backend/api.py`):
   - Task management (start, stop, status)
   - User authentication (login/registration)
   - FreqTrade API proxy integration
   - Scheduler control endpoints
   - Factor analysis system API

4. **Task Scheduling** (`backend/scheduler.py`):
   - APScheduler for background jobs
   - Multiple scheduled analysis tasks (daily crypto analysis, news evaluation, trading strategies)
   - Bootstrap execution after startup

5. **Factor Analysis System** (`backend/factors/`):
   - Plugin architecture for technical analysis factors
   - Dynamic factor loading and computation
   - Support for configurable window sizes
   - Sideways Movement Detection Logic:
     - **For Sideways Movement Detection**: Find the **longest** candle in the sideways period
     - **For Trend Movement Reference**: Find the **shortest** candle in the trend period (3 consecutive bullish/bearish candles)
     - **Reason**: This ensures all candles in the sideways period are shorter than even the weakest momentum candle from the trend period, providing a conservative threshold for genuine consolidation
     - **Implementation Pattern**:
       ```python
       sideways_max_length = max(candle_lengths_in_sideways_period)
       trend_min_length = min(candle_lengths_in_trend_period)
       is_sideways = sideways_max_length < trend_min_length
       ```

6. **Trading Integration** (`backend/freqtrade_client.py`, `backend/trade_signal_executor.py`):
   - FreqTrade API client with authentication
   - Trade signal execution system
   - Health check and connection management

7. **Data Management** (`backend/data_management/`):
   - Background task processing with threading
   - Task progress tracking and management
   - Result caching with thread-safe access patterns

### Frontend (React)
1. **Framework**: React with TypeScript and React Router
2. **UI Library**: Tailwind CSS with Radix UI components
3. **State Management**: React hooks and custom services
4. **Key Components**:
   - Dashboard with market analysis
   - Scheduler management
   - Task progress tracking
   - Authentication dialogs
   - Responsive design

## Key Configuration Files

### Environment Variables (`.env`)
- `OPENAI_API_KEY`: OpenAI API key for AI-powered analysis
- `OPENAI_BASE_URL`: OpenAI API base URL
- `FREQTRADE_API_USERNAME`: FreqTrade API username (auto-configured)
- `FREQTRADE_API_PASSWORD`: FreqTrade API password (auto-configured)
- Proxy settings for restricted regions

### Docker Configuration
- `docker-compose.yml`: Main deployment configuration
- `traefik/`: Traefik reverse proxy configuration

## Security Considerations

The platform automatically generates secure credentials during deployment:
- FreqTrade API credentials
- JWT secrets
- WebSocket tokens
- Demo API keys for dry-run mode (safe for testing)

For production:
1. Update OpenAI API key with `./update_openai_credentials.sh`
2. For live trading, update exchange credentials with `./update_exchange_credentials.sh`
3. Never commit `.env` file to version control

## Common Tasks

1. **Add a new analysis factor**: Create a new factor module in `backend/factors/` implementing the standard Factor interface
2. **Modify trading strategy**: Update FreqTrade configuration in `user_data/config_external_signals.json`
3. **Add API endpoints**: Extend `backend/api.py` with new routes
4. **Update frontend components**: Modify files in `frontend/app/components/`
5. **Modify scheduled tasks**: Update `backend/scheduler.py` with new job definitions