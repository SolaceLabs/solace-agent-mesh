"""
API Router for task events and status queries.
Supports reconnection and event replay for background tasks.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from typing import List

from ....gateway.http_sse.dependencies import get_db
from ....gateway.http_sse.repository.task_repository import TaskRepository
from ....gateway.http_sse.repository.entities import Task, TaskEvent
from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter()


class TaskStatusResponse(BaseModel):
    """Response model for task status queries."""
    task: Task
    is_running: bool
    is_background: bool
    can_reconnect: bool


class TaskEventsResponse(BaseModel):
    """Response model for task events queries."""
    task: Task
    events: List[TaskEvent]
    total_events: int
    has_more: bool


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db: DBSession = Depends(get_db),
):
    """
    Get the current status of a task.
    Used by frontend to check if a background task is still running.
    
    Args:
        task_id: The task ID to query
        
    Returns:
        Task status information including whether it's running and can be reconnected to
    """
    log_prefix = f"[GET /api/v1/tasks/{task_id}/status]"
    log.debug(f"{log_prefix} Querying task status")
    
    repo = TaskRepository()
    task = repo.find_by_id(db, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Determine if task is still running
    is_running = task.status in [None, "running", "pending"] and task.end_time is None
    
    # Check if it's a background task
    is_background = task.background_execution_enabled or False
    
    # Can reconnect if it's a background task and still running
    can_reconnect = is_background and is_running
    
    log.info(
        f"{log_prefix} Task status: running={is_running}, background={is_background}, "
        f"can_reconnect={can_reconnect}"
    )
    
    return TaskStatusResponse(
        task=task,
        is_running=is_running,
        is_background=is_background,
        can_reconnect=can_reconnect
    )


@router.get("/tasks/{task_id}/events", response_model=TaskEventsResponse)
async def get_task_events(
    task_id: str,
    since_timestamp: int = Query(0, description="Return events after this timestamp (epoch ms)"),
    limit: int = Query(100, description="Maximum number of events to return"),
    db: DBSession = Depends(get_db),
):
    """
    Retrieve events for a task, optionally filtered by timestamp.
    Used for reconnection to replay missed events.
    
    Args:
        task_id: The task ID to query
        since_timestamp: Only return events after this timestamp (epoch milliseconds)
        limit: Maximum number of events to return
        
    Returns:
        Task information and list of events
    """
    log_prefix = f"[GET /api/v1/tasks/{task_id}/events]"
    log.debug(f"{log_prefix} Querying events since {since_timestamp}")
    
    repo = TaskRepository()
    result = repo.find_by_id_with_events(db, task_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    task, all_events = result
    
    # Filter events by timestamp
    filtered_events = [
        event for event in all_events
        if event.created_time > since_timestamp
    ]
    
    # Apply limit
    limited_events = filtered_events[:limit]
    has_more = len(filtered_events) > limit
    
    log.info(
        f"{log_prefix} Returning {len(limited_events)} events "
        f"(filtered from {len(all_events)} total, has_more={has_more})"
    )
    
    return TaskEventsResponse(
        task=task,
        events=limited_events,
        total_events=len(filtered_events),
        has_more=has_more
    )


@router.get("/tasks/background/active")
async def get_active_background_tasks(
    user_id: str = Query(..., description="User ID to filter tasks"),
    db: DBSession = Depends(get_db),
):
    """
    Get all active background tasks for a user.
    Used by frontend on session load to detect running background tasks.
    
    Args:
        user_id: The user ID to filter by
        
    Returns:
        List of active background tasks
    """
    log_prefix = f"[GET /api/v1/tasks/background/active]"
    log.debug(f"{log_prefix} Querying active background tasks for user {user_id}")
    
    repo = TaskRepository()
    
    # Get all background tasks
    all_background_tasks = repo.find_background_tasks_by_status(db, status=None)
    
    # Filter by user and running status
    active_tasks = [
        task for task in all_background_tasks
        if task.user_id == user_id
        and task.status in [None, "running", "pending"]
        and task.end_time is None
    ]
    
    log.info(f"{log_prefix} Found {len(active_tasks)} active background tasks for user {user_id}")
    
    return {
        "tasks": active_tasks,
        "count": len(active_tasks)
    }