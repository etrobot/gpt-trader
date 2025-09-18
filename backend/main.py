from __future__ import annotations
import logging
import warnings
from typing import List
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, List
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from models import (
    RunRequest,
    RunResponse,
    TaskResult,
    NewsTaskResult,
    Message,
    AuthRequest,
    AuthResponse,
    NewsEvaluationRequest,
    create_db_and_tables,
    User,
    get_session,
)
from sqlmodel import select
from api import (
    read_root,
    run_analysis,
    get_task_status,
    get_latest_results,
    list_all_tasks,
    stop_analysis,
    login_user,
    run_news_evaluation,
    get_task_status_universal,
    stop_task_universal,
    get_latest_results_universal,
    get_scheduler_status_api,
    stop_scheduled_tasks,
    set_scheduler_enabled,
    get_timeframe_analysis,
    get_freqtrade_credentials,
    test_freqtrade_connection,
    get_freqtrade_health,
    refresh_freqtrade_token,
    get_open_trades,
    run_scheduler_now,
)
from utils import get_task, TASK_VERSIONS
from factors import list_factors

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress warnings
warnings.filterwarnings("ignore")

app = FastAPI(title="Crypto Analysis")

# Initialize database
create_db_and_tables()
logger.info("Database initialized successfully")


def create_admin_user():
    """Check if user table is empty - if so, the first user created will be admin"""
    try:
        with next(get_session()) as session:
            # Check if any users exist
            statement = select(User)
            existing_users = session.exec(statement).all()
            
            if len(existing_users) == 0:
                logger.info("User table is empty - first user created will automatically be admin")
            else:
                logger.info(f"User table has {len(existing_users)} users")
    except Exception as e:
        logger.error(f"Failed to check user table: {e}")


# Check user table status on startup
create_admin_user()

# Start the task scheduler
from scheduler import start_scheduler
import atexit
from scheduler import stop_scheduler

start_scheduler()
atexit.register(stop_scheduler)

# CORS configuration
origins = [
    "http://localhost:14245",
    "https://btc.subx.fun",
    "http://127.0.0.1:14245",
]

# Allow all origins in development
if os.getenv("ENVIRONMENT") == "development":
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if they exist (for production)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    # Mount specific static folders used by the SPA
    assets_dir = os.path.join(static_dir, "assets")
    icons_dir = os.path.join(static_dir, "icons")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    if os.path.isdir(icons_dir):
        app.mount("/icons", StaticFiles(directory=icons_dir), name="icons")

    # Backward compatible mount (optional)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Direct file endpoints for PWA files
    @app.get("/manifest.json", include_in_schema=False)
    async def serve_manifest():
        path = os.path.join(static_dir, "manifest.json")
        if os.path.isfile(path):
            return FileResponse(path)
        return {"detail": "manifest.json not found"}

    @app.get("/sw.js", include_in_schema=False)
    async def serve_sw():
        path = os.path.join(static_dir, "sw.js")
        if os.path.isfile(path):
            return FileResponse(path)
        return {"detail": "sw.js not found"}

    @app.get("/favicon.ico", include_in_schema=False)
    async def serve_favicon():
        path = os.path.join(static_dir, "favicon.ico")
        if os.path.isfile(path):
            return FileResponse(path)
        return {"detail": "favicon.ico not found"}


# Explicit root route: return index.html
@app.get("/", include_in_schema=False)
async def root_index():
    if os.path.exists(static_dir):
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
    return {"message": "Crypto Analysis API", "docs": "/docs"}


@app.post("/run", response_model=RunResponse)
def run(request: RunRequest) -> RunResponse:
    return run_analysis(request)


@app.post("/run-news-evaluation", response_model=RunResponse)
def run_news_eval(request: NewsEvaluationRequest) -> RunResponse:
    return run_news_evaluation(request)


@app.get("/task/{task_id}", response_model=TaskResult | NewsTaskResult)
def get_task_route(task_id: str):
    return get_task_status_universal(task_id)


@app.post("/task/{task_id}/stop", response_model=TaskResult | NewsTaskResult)
def stop_task(task_id: str):
    return stop_task_universal(task_id)


@app.get("/results", response_model=TaskResult | NewsTaskResult | Message)
def get_results():
    return get_latest_results_universal()


# SSE stream for task updates
@app.get("/task/{task_id}/events")
async def task_events(task_id: str):
    import asyncio

    async def event_generator():
        last_version = -1
        # Send initial state immediately if available
        task = get_task(task_id)
        if task is not None:
            from models import TaskResult

            initial = TaskResult(
                task_id=task.task_id,
                status=task.status,
                progress=task.progress,
                message=task.message,
                created_at=task.created_at,
                completed_at=task.completed_at,
                top_n=task.top_n,
                selected_factors=task.selected_factors,
                data=task.result["data"] if task.result else None,
                count=task.result["count"] if task.result else None,
                extended=task.result.get("extended") if task.result else None,
                error=task.error,
            )
            yield f"event: update\n"
            yield f"data: {initial.model_dump_json()}\n\n"
            last_version = TASK_VERSIONS.get(task_id, 0)
        # Stream updates when version changes
        while True:
            await asyncio.sleep(0.5)
            if task_id not in TASK_VERSIONS:
                # If we have never seen this task version, initialize
                TASK_VERSIONS[task_id] = TASK_VERSIONS.get(task_id, 0)
            current_version = TASK_VERSIONS.get(task_id, 0)
            if current_version != last_version:
                task = get_task(task_id)
                if task is None:
                    break
                from models import TaskResult

                update = TaskResult(
                    task_id=task.task_id,
                    status=task.status,
                    progress=task.progress,
                    message=task.message,
                    created_at=task.created_at,
                    completed_at=task.completed_at,
                    top_n=task.top_n,
                    selected_factors=task.selected_factors,
                    data=task.result["data"] if task.result else None,
                    count=task.result["count"] if task.result else None,
                    extended=task.result.get("extended") if task.result else None,
                    error=task.error,
                )
                yield f"event: update\n"
                yield f"data: {update.model_dump_json()}\n\n"
                last_version = current_version
            # Stop after terminal states to allow client to close
            task = get_task(task_id)
            if task:
                from models import TaskStatus as _TS

                if task.status in (_TS.COMPLETED, _TS.FAILED, _TS.CANCELLED):
                    break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/tasks", response_model=List[TaskResult])
def list_tasks() -> List[TaskResult]:
    return list_all_tasks()


@app.get("/factors")
def get_factors() -> Dict[str, object]:
    """Return factor metadata for frontend dynamic rendering"""
    factors = list_factors()
    # Normalize to simple JSON metadata
    items = []
    for f in factors:
        items.append(
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "columns": f.columns,
            }
        )
    return {"items": items}


# Scheduler routes
@app.get("/api/scheduler/status")
def get_scheduler_status():
    """Get scheduler status"""
    from scheduler import get_scheduler_status
    return get_scheduler_status()

@app.post("/api/scheduler/stop")
def stop_scheduled_task():
    """Stop current scheduled task"""
    from scheduler import stop_current_scheduled_task
    success = stop_current_scheduled_task()
    return {"success": success, "message": "Scheduled task stop requested" if success else "No active scheduled task"}

@app.post("/api/scheduler/enable")
def enable_scheduler(enabled: bool = True):
    """Enable or disable scheduled tasks"""
    from scheduler import enable_scheduled_tasks
    enable_scheduled_tasks(enabled)
    return {"success": True, "message": f"Scheduled tasks {'enabled' if enabled else 'disabled'}"}

# Authentication routes
@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> AuthResponse:
    """User login/register with username and email"""
    return login_user(request)


# FreqTrade API routes
@app.get("/api/freqtrade/credentials")
def get_freqtrade_credentials_route():
    """Get Freqtrade API credentials configuration"""
    return get_freqtrade_credentials()


@app.get("/api/freqtrade/test")
def test_freqtrade_connection_route():
    """Test Freqtrade API connection and credentials"""
    return test_freqtrade_connection()


@app.get("/api/freqtrade/health")
def get_freqtrade_health_route():
    """Check Freqtrade API health status"""
    return get_freqtrade_health()


@app.get("/api/freqtrade/open-trades")
def get_freqtrade_open_trades_route():
    """Proxy: List open trades from Freqtrade"""
    return get_open_trades()


@app.post("/api/freqtrade/refresh-token")
def refresh_freqtrade_token_route():
    """Force refresh Freqtrade API token"""
    return refresh_freqtrade_token()


@app.get("/api/scheduler/status")
def get_scheduler_status():
    """Get scheduler status and current tasks"""
    return get_scheduler_status_api()


@app.post("/api/scheduler/stop")
def stop_scheduler_tasks():
    """Stop currently running scheduled tasks"""
    return stop_scheduled_tasks()


@app.post("/api/scheduler/enable")
def enable_scheduler(enabled: bool = True):
    """Enable or disable scheduled tasks"""
    return set_scheduler_enabled(enabled)


@app.post("/api/scheduler/run-now")
def run_scheduler_now_route():
    """Trigger daily task sequence immediately"""
    return run_scheduler_now()


@app.get("/api/scheduler/events")
async def scheduler_events():
    import asyncio
    import json

    async def event_generator():
        last_payload = None
        # Send initial status immediately
        status = get_scheduler_status_api()
        try:
            last_payload = json.dumps(status, sort_keys=True, ensure_ascii=False)
        except Exception:
            last_payload = None
        if last_payload:
            yield f"event: update\n"
            yield f"data: {last_payload}\n\n"
        # Periodically check for changes
        while True:
            await asyncio.sleep(2)
            try:
                status = get_scheduler_status_api()
                payload = json.dumps(status, sort_keys=True, ensure_ascii=False)
                if payload != last_payload:
                    yield f"event: update\n"
                    yield f"data: {payload}\n\n"
                    last_payload = payload
            except Exception:
                # On error, continue loop; client may reconnect
                continue

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/timeframe-analysis")
def get_timeframe_analysis_route():
    """Get the latest timeframe analysis results"""
    return get_timeframe_analysis()


@app.get("/api/ranking")
def get_ranking_data():
    """Get the latest ranking data from ranking.json"""
    import json
    import os

    ranking_file_path = "data_management/ranking.json"

    if not os.path.exists(ranking_file_path):
        return {"error": "ranking.json not found", "message": "No ranking data available yet"}

    try:
        with open(ranking_file_path, 'r', encoding='utf-8') as f:
            ranking_data = json.load(f)
        return ranking_data
    except Exception as e:
        return {"error": f"Failed to read ranking.json: {str(e)}"}


# Serve frontend for production
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve frontend files for production"""
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    # If static directory doesn't exist, return API info
    if not os.path.exists(static_dir):
        return {"message": "Crypto Analysis API", "docs": "/docs"}

    # Handle root path - serve index.html
    if full_path == "":
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        # Fallback to API info if frontend not built
        return {"message": "Crypto Analysis API", "docs": "/docs"}

    # Try to serve the requested file
    file_path = os.path.join(static_dir, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # For SPA routing, serve index.html for non-API routes
    if not full_path.startswith("api/") and not full_path.startswith("docs"):
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

    # Return 404 for API routes or missing files
    return {"detail": "Not found"}
