"""Memory storage provider for async service."""

from datetime import datetime
from typing import Dict, List, Optional

from solace_ai_connector.common.log import log

from .base_storage_provider import BaseStorageProvider


class MemoryStorageProvider(BaseStorageProvider):
    """Memory storage provider for async service."""
    
    def __init__(self):
        """Initialize the memory storage provider."""
        self.task_groups = {}
        self.tasks = {}
    
    def create_task_group(
        self,
        task_group_id: str,
        stimulus_uuid: str,
        session_id: str,
        gateway_id: str,
        stimulus_state: List,
        agent_responses: List,
        user_responses: Dict,
        task_id_list: List[str],
        creation_time: datetime,
        status: str,
    ) -> None:
        """Create a task group."""
        self.task_groups[task_group_id] = {
            "task_group_id": task_group_id,
            "stimulus_uuid": stimulus_uuid,
            "session_id": session_id,
            "gateway_id": gateway_id,
            "stimulus_state": stimulus_state,
            "agent_responses": agent_responses,
            "user_responses": user_responses,
            "task_id_list": task_id_list,
            "creation_time": creation_time,
            "status": status,
        }
        log.debug(f"Created task group: {task_group_id}")
    
    def get_task_group(self, task_group_id: str) -> Optional[Dict]:
        """Get a task group."""
        return self.task_groups.get(task_group_id)
    
    def update_task_group(self, task_group: Dict) -> None:
        """Update a task group."""
        task_group_id = task_group.get("task_group_id")
        if task_group_id in self.task_groups:
            self.task_groups[task_group_id] = task_group
            log.debug(f"Updated task group: {task_group_id}")
        else:
            log.error(f"Task group not found: {task_group_id}")
    
    def delete_task_group(self, task_group_id: str) -> None:
        """Delete a task group."""
        if task_group_id in self.task_groups:
            del self.task_groups[task_group_id]
            log.debug(f"Deleted task group: {task_group_id}")
        else:
            log.error(f"Task group not found: {task_group_id}")
    
    def create_task(
        self,
        task_id: str,
        task_group_id: str,
        async_response: Dict,
        creation_time: datetime,
        timeout_time: datetime,
        status: str,
        user_response: Optional[Dict],
    ) -> None:
        """Create a task."""
        self.tasks[task_id] = {
            "task_id": task_id,
            "task_group_id": task_group_id,
            "async_response": async_response,
            "creation_time": creation_time,
            "timeout_time": timeout_time,
            "status": status,
            "user_response": user_response,
        }
        log.debug(f"Created task: {task_id}")
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a task."""
        return self.tasks.get(task_id)
    
    def update_task(self, task: Dict) -> None:
        """Update a task."""
        task_id = task.get("task_id")
        if task_id in self.tasks:
            self.tasks[task_id] = task
            log.debug(f"Updated task: {task_id}")
        else:
            log.error(f"Task not found: {task_id}")
    
    def delete_task(self, task_id: str) -> None:
        """Delete a task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            log.debug(f"Deleted task: {task_id}")
        else:
            log.error(f"Task not found: {task_id}")
    
    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks."""
        return [task for task in self.tasks.values() if task.get("status") == "pending"]