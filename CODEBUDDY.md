# CodeBuddy Code Instructions

## Development Commands
for exposing problems, avoid try catch as much as possible
fix promblem without modifying params

### Fullstack Development
- `pnpm run install:all`: Install all dependencies (frontend and backend)
- `pnpm run dev`: Run both frontend and backend development servers concurrently
- `pnpm run build`: Build both frontend and backend for production

### Backend (Python/FastAPI)
- `uv run uvicorn main:app --host 0.0.0.0 --port 14250 --reload`: Run backend server with auto-reload
- `uv sync --quiet`: Sync Python dependencies
- `black .`: Format Python code
- `ruff .`: Lint Python code

### Frontend (React/Vite)
- `pnpm dev`: Run frontend development server
- `pnpm build`: Build frontend for production

## Architecture Overview

### Fullstack Structure
- Monorepo with `backend/` (Python) and `frontend/` (React) directories
- Uses pnpm for Node.js package management and UV for Python dependency management

### Backend Architecture
- FastAPI application serving REST API and SSE streams
- SQLModel for database models (SQLite)
- Organized into:
  - `api.py`: Core API endpoints
  - `models.py`: Database models and Pydantic schemas
  - `data_management/`: Data processing and analysis services
  - `factors/`: Crypto analysis factor implementations
- Features:
  - Background task system for long-running crypto analysis
  - SSE for real-time task updates
  - Authentication system

### Frontend Architecture
- React application using Vite
- Key features:
  - Dynamic rendering based on backend factor metadata
  - Real-time updates via SSE
  - Theme support (light/dark mode)
- Structure:
  - `app/components/`: UI components
  - `app/services/`: API client services
  - `app/hooks/`: Custom React hooks

### Global Task Management System

#### Task Concurrency Control
- **Single Task Execution**: Only one background task can run simultaneously
- **Semaphore Control**: `threading.Semaphore(1)` in `backend/data_management/services.py:28`
- **Task Queue**: New tasks wait in PENDING status if another task is running
- **Timeout Protection**: 5-second timeout when acquiring semaphore to prevent blocking

#### Real-time Communication (SSE + Polling Fallback)
- **Primary**: Server-Sent Events (SSE) for real-time task updates
  - Endpoint: `/task/{task_id}/events`
  - Event type: `update` with JSON task status
  - Auto-closes on terminal states (completed/failed/cancelled)
- **Fallback**: Automatic polling if SSE fails
  - 1-second interval polling
  - Same termination conditions as SSE

#### Task State Management
- **Backend Storage**: Global `TASKS` dict in `utils.py:17`
- **Version Control**: `TASK_VERSIONS` dict for SSE change detection
- **Thread Management**: `TASK_THREADS` and `TASK_STOP_EVENTS` for lifecycle control

#### Polling Termination Logic
Polling stops when:
1. **Task completion**: `status === 'completed'`
2. **Task cancellation**: `status === 'cancelled'`
3. **Task failure**: `status === 'failed'`
4. **Network errors**: API request failures
5. **Manual stop**: Component unmount or explicit cleanup

#### Data Flow
1. Frontend submits analysis request via `/run` endpoint
2. Backend creates background task and returns task ID
3. Frontend subscribes to task updates via `/task/{id}/events` SSE stream
4. If SSE fails, automatically falls back to polling mode
5. Backend processes crypto data using factors from `factors/` directory
6. Task status updates streamed in real-time via SSE or polling
7. Results stored in SQLite database and delivered to frontend
8. Communication automatically terminates on task completion

## K-line Analysis Principle
- **For Sideways Movement Detection**: Find the **longest** candle in the sideways period
- **For Trend Movement Reference**: Find the **shortest** candle in the trend period (3 consecutive bullish/bearish candles) 
- **Reason**: This ensures all candles in the sideways period are shorter than even the weakest momentum candle from the trend period, providing a conservative threshold for genuine consolidation
- **Implementation Pattern**: 
  - `sideways_max_length = max(candle_lengths_in_sideways_period)`
  - `trend_min_length = min(candle_lengths_in_trend_period)`
  - `is_sideways = sideways_max_length < trend_min_length`