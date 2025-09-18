from __future__ import annotations
from typing import List
from fastapi import HTTPException
from models import (
    RunRequest,
    RunResponse,
    TaskResult,
    NewsTaskResult,
    TaskStatus,
    Message,
    AuthRequest,
    AuthResponse,
    User,
    NewsEvaluationRequest,
    get_session,
)
from sqlmodel import select
from utils import get_task, get_all_tasks, get_last_completed_task, TASK_STOP_EVENTS
from data_management.services import create_analysis_task, create_news_evaluation_task
from freqtrade_client import get_api_credentials, test_credentials, health as freqtrade_health, refresh_token, list_open_trades as ft_list_open_trades
from scheduler import get_scheduler_status, stop_current_scheduled_task, enable_scheduled_tasks, run_daily_tasks_now


def read_root():
    return {"service": "crypto-analysis-backend", "status": "running"}


def run_analysis(request: RunRequest) -> RunResponse:
    """Start comprehensive crypto analysis as background task"""
    # 强制限制为最多50个交易对
    top_n = min(request.top_n, 50)
    task_id = create_analysis_task(
        top_n, request.selected_factors, request.collect_latest_data
    )

    return RunResponse(
        task_id=task_id, status=TaskStatus.PENDING, message="分析任务已启动"
    )


def stop_analysis(task_id: str) -> TaskResult:
    """Signal a running task to stop and return its status"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    stop_event = TASK_STOP_EVENTS.get(task_id)
    if not stop_event:
        raise HTTPException(
            status_code=400, detail="Task is not cancellable or already finished"
        )

    # Signal cancellation
    stop_event.set()

    # Reflect status change immediately; the worker will mark completed/cancelled later.
    task.status = TaskStatus.RUNNING  # keep running until worker finalizes
    task.message = "已请求停止，正在清理..."
    from utils import bump_task_version

    bump_task_version(task_id)
    return TaskResult(
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


def get_task_status(task_id: str) -> TaskResult:
    """Get status of a specific task"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Note: this endpoint is kept for compatibility/polling but SSE is preferred.
    return TaskResult(
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


def get_latest_results() -> TaskResult | Message:
    """Get the latest completed task results"""
    last_task = get_last_completed_task()
    if not last_task:
        return Message(message="No results yet. POST /run to start a calculation.")

    return TaskResult(
        task_id=last_task.task_id,
        status=last_task.status,
        progress=last_task.progress,
        message=last_task.message,
        created_at=last_task.created_at,
        completed_at=last_task.completed_at,
        top_n=last_task.top_n,
        selected_factors=last_task.selected_factors,
        data=last_task.result["data"] if last_task.result else None,
        count=last_task.result["count"] if last_task.result else None,
        extended=last_task.result.get("extended") if last_task.result else None,
        error=last_task.error,
    )


def list_all_tasks() -> List[TaskResult]:
    """List all tasks"""
    all_tasks = get_all_tasks()
    return [
        TaskResult(
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
        for task in all_tasks.values()
    ]


def login_user(request: AuthRequest) -> AuthResponse:
    """User authentication with username and email (weak validation). Creates user if not exists."""
    try:
        # 基本输入验证
        if not request.name or not request.name.strip():
            return AuthResponse(success=False, message="用户名不能为空")
        
        if not request.email or not request.email.strip():
            return AuthResponse(success=False, message="邮箱不能为空")
        
        # 简单的邮箱格式验证
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, request.email.strip()):
            return AuthResponse(success=False, message="邮箱格式不正确")
        
        with next(get_session()) as session:
            # Find user by name and email (弱校验：只需用户名和邮箱匹配)
            statement = select(User).where(
                User.name == request.name.strip(), 
                User.email == request.email.strip()
            )
            user = session.exec(statement).first()

            if user:
                # 用户存在，直接认证成功
                token = f"token_{user.id}"
                admin_status = " (管理员)" if user.is_admin else ""
                return AuthResponse(
                    success=True, 
                    token=token, 
                    message=f"欢迎回来，{user.name}{admin_status}"
                )
            else:
                # 用户不存在，创建新用户（弱校验：无需密码）
                # Check if this is the first user (admin)
                all_users_statement = select(User)
                all_users = session.exec(all_users_statement).all()
                is_first_user = len(all_users) == 0
                
                new_user = User(
                    name=request.name.strip(),
                    email=request.email.strip(),
                    password_hash=None,  # 弱校验模式下不存储密码
                    is_admin=is_first_user  # First user becomes admin
                )
                session.add(new_user)
                session.commit()
                session.refresh(new_user)
                
                # Generate token for new user
                token = f"token_{new_user.id}"
                admin_status = " (管理员)" if is_first_user else ""
                return AuthResponse(
                    success=True, 
                    token=token, 
                    message=f"用户创建成功，欢迎 {new_user.name}{admin_status}"
                )

    except Exception as e:
        return AuthResponse(success=False, message=f"认证失败: {str(e)}")


def run_news_evaluation(request: NewsEvaluationRequest) -> RunResponse:
    """Start news evaluation task for top cryptocurrencies"""
    # 限制参数范围
    top_n = min(max(request.top_n, 1), 20)  # 1-20个币种
    news_per_symbol = min(max(request.news_per_symbol, 1), 10)  # 每个币种1-10条新闻

    task_id = create_news_evaluation_task(top_n, news_per_symbol, request.openai_model)

    return RunResponse(
        task_id=task_id, status=TaskStatus.PENDING, message="新闻评估任务已启动"
    )


def _is_news_evaluation_task(task) -> bool:
    """Check if a task is a news evaluation task based on selected_factors being None"""
    return task.selected_factors is None


def get_task_status_universal(task_id: str) -> TaskResult | NewsTaskResult:
    """Get status of a specific task, returning appropriate type based on task type"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if _is_news_evaluation_task(task):
        return NewsTaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            result=task.result,
            error=task.error,
        )
    else:
        return TaskResult(
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


def stop_task_universal(task_id: str) -> TaskResult | NewsTaskResult:
    """Signal a running task to stop and return its status"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    stop_event = TASK_STOP_EVENTS.get(task_id)
    if not stop_event:
        raise HTTPException(
            status_code=400, detail="Task is not cancellable or already finished"
        )

    # Signal cancellation
    stop_event.set()

    # Reflect status change immediately; the worker will mark completed/cancelled later.
    task.status = TaskStatus.RUNNING  # keep running until worker finalizes
    task.message = "已请求停止，正在清理..."
    from utils import bump_task_version

    bump_task_version(task_id)
    
    if _is_news_evaluation_task(task):
        return NewsTaskResult(
            task_id=task.task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            created_at=task.created_at,
            completed_at=task.completed_at,
            result=task.result,
            error=task.error,
        )
    else:
        return TaskResult(
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


def get_latest_results_universal() -> TaskResult | NewsTaskResult | Message:
    """Get the latest completed task results, returning appropriate type based on task type"""
    last_task = get_last_completed_task()
    if not last_task:
        return Message(message="No results yet. POST /run to start a calculation.")

    if _is_news_evaluation_task(last_task):
        return NewsTaskResult(
            task_id=last_task.task_id,
            status=last_task.status,
            progress=last_task.progress,
            message=last_task.message,
            created_at=last_task.created_at,
            completed_at=last_task.completed_at,
            result=last_task.result,
            error=last_task.error,
        )
    else:
        return TaskResult(
            task_id=last_task.task_id,
            status=last_task.status,
            progress=last_task.progress,
            message=last_task.message,
            created_at=last_task.created_at,
            completed_at=last_task.completed_at,
            top_n=last_task.top_n,
            selected_factors=last_task.selected_factors,
            data=last_task.result["data"] if last_task.result else None,
            count=last_task.result["count"] if last_task.result else None,
            extended=last_task.result.get("extended") if last_task.result else None,
            error=last_task.error,
        )


def get_freqtrade_credentials():
    """Get Freqtrade API credentials configuration (without sensitive data)."""
    return get_api_credentials()


def test_freqtrade_connection():
    """Test Freqtrade API connection and credentials."""
    return test_credentials()


def get_freqtrade_health():
    """Check Freqtrade API health status."""
    try:
        is_healthy = freqtrade_health()
        return {"healthy": is_healthy, "status": "connected" if is_healthy else "disconnected"}
    except Exception as e:
        return {"healthy": False, "status": "error", "error": str(e)}


def refresh_freqtrade_token():
    """Force refresh Freqtrade API token."""
    try:
        token = refresh_token()
        return {
            "success": bool(token),
            "message": "Token refreshed successfully" if token else "Failed to refresh token",
            "token_length": len(token) if token else 0
        }
    except Exception as e:
        return {"success": False, "message": f"Error refreshing token: {str(e)}"}


def get_open_trades():
    """Return current open trades via Freqtrade API (proxied)."""
    try:
        trades = ft_list_open_trades()
        return {"count": len(trades), "trades": trades}
    except Exception as e:
        return {"count": 0, "trades": [], "error": str(e)}


def get_scheduler_status_api():
    """Get scheduler status and current tasks."""
    return get_scheduler_status()


def stop_scheduled_tasks():
    """Stop currently running scheduled tasks."""
    try:
        stopped = stop_current_scheduled_task()
        return {
            "success": True,
            "message": "Tasks stopped successfully" if stopped else "No tasks were running",
            "stopped": stopped
        }
    except Exception as e:
        return {"success": False, "message": f"Error stopping tasks: {str(e)}"}


def set_scheduler_enabled(enabled: bool):
    """Enable or disable scheduled tasks."""
    try:
        enable_scheduled_tasks(enabled)
        return {
            "success": True,
            "message": f"Scheduled tasks {'enabled' if enabled else 'disabled'}",
            "enabled": enabled
        }
    except Exception as e:
        return {"success": False, "message": f"Error updating scheduler: {str(e)}"}


def run_scheduler_now():
    """Trigger the daily task sequence immediately (async)."""
    try:
        ok = run_daily_tasks_now()
        return {"success": ok, "message": "Daily tasks scheduled to run now" if ok else "Failed to schedule run"}
    except Exception as e:
        return {"success": False, "message": f"Error scheduling run: {str(e)}"}


def get_timeframe_analysis():
    """Get the latest timeframe analysis results."""
    import json
    import os
    from datetime import datetime
    
    try:
        analysis_file = "debug_output/timeframe_analysis.json"
        
        if not os.path.exists(analysis_file):
            return {
                "message": "No timeframe analysis available yet. Analysis runs daily at UTC 1:00.",
                "next_analysis": "Daily at 01:00 UTC"
            }
        
        with open(analysis_file, "r", encoding="utf-8") as f:
            analysis_data = json.load(f)
        
        # 添加文件修改时间
        file_mtime = os.path.getmtime(analysis_file)
        analysis_data["file_updated"] = datetime.fromtimestamp(file_mtime).isoformat()
        
        return analysis_data
        
    except Exception as e:
        return {
            "error": f"Failed to load timeframe analysis: {str(e)}",
            "message": "Error reading analysis file"
        }


