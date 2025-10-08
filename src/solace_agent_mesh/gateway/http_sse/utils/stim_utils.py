"""
Utility functions for creating .stim file structures.
"""

from typing import List

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
