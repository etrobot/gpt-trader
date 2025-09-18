from __future__ import annotations
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import uuid4

import numpy as np
from models import Task, TaskStatus
from utils import (
    add_task,
    get_task,
    set_last_completed_task,
    handle_task_error,
    update_task_progress,
    TASK_STOP_EVENTS,
    TASK_THREADS,
)
from .analysis_task_runner import run_analysis_task
from .news_evaluation_task_runner import run_news_evaluation_task

logger = logging.getLogger(__name__)

# In-memory storage for calculation results
ANALYSIS_RESULTS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = threading.Lock()

# Global semaphore to limit concurrent analysis tasks (only 1 at a time)
ANALYSIS_SEMAPHORE = threading.Semaphore(1)


def get_cached_analysis_results(task_id: Optional[str] = None) -> Dict[str, Any]:
    """Get cached analysis results. If task_id is provided, get specific task results."""
    with CACHE_LOCK:
        if task_id:
            return ANALYSIS_RESULTS_CACHE.get(task_id, {})
        return dict(ANALYSIS_RESULTS_CACHE)


def get_latest_analysis_results() -> Optional[Dict[str, Any]]:
    """Get the most recent analysis results based on completion timestamp."""
    with CACHE_LOCK:
        if not ANALYSIS_RESULTS_CACHE:
            return None

        # Find the task with the most recent completion time
        latest_task_id = max(
            ANALYSIS_RESULTS_CACHE.keys(),
            key=lambda tid: ANALYSIS_RESULTS_CACHE[tid].get("completed_at", ""),
        )
        return ANALYSIS_RESULTS_CACHE[latest_task_id]


def clear_analysis_cache(task_id: Optional[str] = None) -> None:
    """Clear cached analysis results. If task_id is provided, clear specific task only."""
    with CACHE_LOCK:
        if task_id:
            ANALYSIS_RESULTS_CACHE.pop(task_id, None)
        else:
            ANALYSIS_RESULTS_CACHE.clear()


def run_analysis_wrapper(
    task_id: str,
    top_n: int,
    selected_factors: Optional[List[str]] = None,
    collect_latest_data: bool = True,
    stop_event: Optional[threading.Event] = None,
):
    """Wrapper to handle task errors properly and cleanup registries"""
    error_occurred = False
    semaphore_acquired = False

    try:
        # Try to acquire semaphore with timeout to prevent blocking indefinitely
        if not ANALYSIS_SEMAPHORE.acquire(timeout=5):
            logger.warning(
                f"Task {task_id} could not acquire semaphore - another analysis is running"
            )
            task = get_task(task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.message = (
                    "无法启动分析：已有其他分析任务正在运行，请等待完成后重试"
                )
                task.completed_at = datetime.now().isoformat()
                from utils import bump_task_version

                bump_task_version(task_id)
            return

        semaphore_acquired = True
        logger.info(f"Task {task_id} acquired analysis semaphore, starting execution")

        run_analysis_task(
            task_id, top_n, selected_factors, collect_latest_data, stop_event=stop_event
        )
    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        handle_task_error(task_id, e)
        error_occurred = True
    finally:
        # Release semaphore first
        if semaphore_acquired:
            ANALYSIS_SEMAPHORE.release()
            logger.info(f"Task {task_id} released analysis semaphore")

        # Cleanup thread and stop event registries once task ends
        try:
            TASK_THREADS.pop(task_id, None)
            TASK_STOP_EVENTS.pop(task_id, None)
        except Exception:
            pass

    if error_occurred:
        logger.error(f"Task {task_id} encountered an error and was marked as failed")


def create_analysis_task(
    top_n: int = 50,
    selected_factors: Optional[List[str]] = None,
    collect_latest_data: bool = True,
) -> str:
    """Create and start a new analysis task"""
    # Check if there are any running tasks
    from utils import get_all_tasks

    running_tasks = [
        task for task in get_all_tasks().values() if task.status == TaskStatus.RUNNING
    ]

    task_id = str(uuid4())

    if running_tasks:
        # Create task but mark it as pending with appropriate message
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0.0,
            message=f"任务已创建，等待其他任务完成（当前有{len(running_tasks)}个任务运行中）",
            created_at=datetime.now().isoformat(),
            top_n=top_n,
            selected_factors=selected_factors,
        )
    else:
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0.0,
            message="任务已创建，正在启动",
            created_at=datetime.now().isoformat(),
            top_n=top_n,
            selected_factors=selected_factors,
        )

    add_task(task)

    # Prepare a stop event and thread, and register them
    stop_event = threading.Event()
    TASK_STOP_EVENTS[task_id] = stop_event

    # Start background thread with error wrapper
    thread = threading.Thread(
        target=run_analysis_wrapper,
        args=(task_id, top_n, selected_factors, collect_latest_data, stop_event),
    )
    thread.daemon = True
    TASK_THREADS[task_id] = thread
    thread.start()

    return task_id


def run_news_evaluation_wrapper(
    task_id: str,
    top_n: int,
    news_per_symbol: int,
    openai_model: str,
    stop_event: Optional[threading.Event] = None,
):
    """Wrapper to handle news evaluation task errors properly and cleanup registries"""
    error_occurred = False
    semaphore_acquired = False

    try:
        # Try to acquire semaphore with timeout to prevent blocking indefinitely
        if not ANALYSIS_SEMAPHORE.acquire(timeout=5):
            logger.warning(
                f"News evaluation task {task_id} could not acquire semaphore - another task is running"
            )
            task = get_task(task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.message = (
                    "无法启动新闻评估：已有其他任务正在运行，请等待完成后重试"
                )
                task.completed_at = datetime.now().isoformat()
                from utils import bump_task_version

                bump_task_version(task_id)
            return

        semaphore_acquired = True
        logger.info(
            f"News evaluation task {task_id} acquired semaphore, starting execution"
        )

        run_news_evaluation_task(
            task_id, top_n, news_per_symbol, openai_model, stop_event=stop_event
        )
    except Exception as e:
        logger.error(f"News evaluation task {task_id} failed: {e}")
        handle_task_error(task_id, e)
        error_occurred = True
    finally:
        # Release semaphore first
        if semaphore_acquired:
            ANALYSIS_SEMAPHORE.release()
            logger.info(f"News evaluation task {task_id} released semaphore")

        # Cleanup thread and stop event registries once task ends
        try:
            TASK_THREADS.pop(task_id, None)
            TASK_STOP_EVENTS.pop(task_id, None)
        except Exception:
            pass

    if error_occurred:
        logger.error(
            f"News evaluation task {task_id} encountered an error and was marked as failed"
        )


def create_news_evaluation_task(
    top_n: int = 10, news_per_symbol: int = 3, openai_model: str = "gpt-oss-120b"
) -> str:
    """Create and start a new news evaluation task"""
    # Check if there are any running tasks
    from utils import get_all_tasks

    running_tasks = [
        task for task in get_all_tasks().values() if task.status == TaskStatus.RUNNING
    ]

    task_id = str(uuid4())

    if running_tasks:
        # Create task but mark it as pending with appropriate message
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0.0,
            message=f"新闻评估任务已创建，等待其他任务完成（当前有{len(running_tasks)}个任务运行中）",
            created_at=datetime.now().isoformat(),
            top_n=top_n,
            selected_factors=None,  # News evaluation doesn't use factors
        )
    else:
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0.0,
            message="新闻评估任务已创建，正在启动",
            created_at=datetime.now().isoformat(),
            top_n=top_n,
            selected_factors=None,  # News evaluation doesn't use factors
        )

    add_task(task)

    # Prepare a stop event and thread, and register them
    stop_event = threading.Event()
    TASK_STOP_EVENTS[task_id] = stop_event

    # Start background thread with error wrapper
    thread = threading.Thread(
        target=run_news_evaluation_wrapper,
        args=(task_id, top_n, news_per_symbol, openai_model, stop_event),
    )
    thread.daemon = True
    TASK_THREADS[task_id] = thread
    thread.start()

    return task_id
