from __future__ import annotations
import logging
import threading
from datetime import datetime
from typing import Dict, Optional
from models import Task, TaskStatus

# Types
from typing import Optional as _Optional
import threading as _threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global task storage
TASKS: Dict[str, Task] = {}
LAST_COMPLETED_TASK: Optional[Task] = None

# Thread and cancellation management for analysis tasks
TASK_THREADS: Dict[str, _threading.Thread] = {}
TASK_STOP_EVENTS: Dict[str, _threading.Event] = {}

# Simple change-tracking for SSE streams
TASK_VERSIONS: Dict[str, int] = {}


def bump_task_version(task_id: str):
    try:
        TASK_VERSIONS[task_id] = TASK_VERSIONS.get(task_id, 0) + 1
    except Exception:
        pass


def update_task_progress(task_id: str, progress: float, message: str):
    """Update task progress"""
    if task_id in TASKS:
        TASKS[task_id].progress = progress
        TASKS[task_id].message = message
        bump_task_version(task_id)
        logger.info(f"Task {task_id}: {progress:.1%} - {message}")


def handle_task_error(task_id: str, error: Exception):
    """Handle task errors by updating task status"""
    task = TASKS[task_id]
    task.status = TaskStatus.FAILED
    task.error = str(error)
    task.message = f"分析失败: {str(error)}"
    task.completed_at = datetime.now().isoformat()


def get_task(task_id: str) -> Optional[Task]:
    """Get task by ID"""
    return TASKS.get(task_id)


def add_task(task: Task) -> None:
    """Add task to storage"""
    TASKS[task.task_id] = task


def set_last_completed_task(task: Task) -> None:
    """Set the last completed task"""
    global LAST_COMPLETED_TASK
    LAST_COMPLETED_TASK = task


def get_last_completed_task() -> Optional[Task]:
    """Get the last completed task"""
    return LAST_COMPLETED_TASK


def get_all_tasks() -> Dict[str, Task]:
    """Get all tasks"""
    return TASKS
