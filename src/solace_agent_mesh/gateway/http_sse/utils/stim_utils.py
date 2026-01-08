"""
Utility functions for creating .stim file structures.
"""

from typing import Dict, List

from ..repository.entities import Task, TaskEvent


def create_stim_from_task_data(task: Task, events: List[TaskEvent]) -> dict:
    """
    Formats a task and its events into the .stim file structure.

    Args:
        task: The task entity.
        events: A list of task event entities.

    Returns:
        A dictionary representing the .stim file content.
    """
    return {
        "invocation_details": {
            "log_file_version": "2.0",  # New version for gateway-generated logs
            "task_id": task.id,
            "user_id": task.user_id,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "status": task.status,
            "initial_request_text": task.initial_request_text,
        },
        "invocation_flow": [event.model_dump() for event in events],
    }


def create_stim_from_task_hierarchy(
    tasks: Dict[str, Task], all_events: Dict[str, List[TaskEvent]], root_task_id: str
) -> dict:
    """
    Formats a task hierarchy (parent + children) and all their events into the .stim file structure.

    Args:
        tasks: Dictionary of task_id -> Task entity for all tasks in hierarchy.
        all_events: Dictionary of task_id -> List[TaskEvent] for all tasks.
        root_task_id: The root task ID (used for invocation_details).

    Returns:
        A dictionary representing the .stim file content with all task events.
    """
    root_task = tasks[root_task_id]

    # Collect all events from all tasks and sort by created_time
    combined_events = []
    for task_id, events in all_events.items():
        combined_events.extend(events)

    # Sort all events chronologically
    combined_events.sort(key=lambda e: e.created_time)

    return {
        "invocation_details": {
            "log_file_version": "2.0",  # New version for gateway-generated logs
            "task_id": root_task.id,
            "user_id": root_task.user_id,
            "start_time": root_task.start_time,
            "end_time": root_task.end_time,
            "status": root_task.status,
            "initial_request_text": root_task.initial_request_text,
            "includes_child_tasks": len(tasks) > 1,
            "total_tasks": len(tasks),
        },
        "invocation_flow": [event.model_dump() for event in combined_events],
    }
