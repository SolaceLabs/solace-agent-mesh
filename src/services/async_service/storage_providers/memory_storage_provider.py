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
        user_properties: Dict = None,  # Add user_properties parameter
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
            "user_properties": user_properties or {},  # Store user_properties
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
        originator: Dict = None,  # Add originator parameter
        approver_list: List[Dict] = None,  # Add approver_list parameter
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
            "originator": originator,  # Store originator
            "approver_list": approver_list or [],  # Store approver_list
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
        
    def get_pending_tasks_by_gateway_id(self, gateway_id: str) -> List[Dict]:
        """Get all pending tasks for a specific gateway_id."""
        # First, find all task groups with the matching gateway_id
        matching_task_groups = [
            task_group for task_group in self.task_groups.values()
            if task_group.get("gateway_id") == gateway_id
        ]
        
        # Then, get all pending tasks from these task groups
        pending_tasks = []
        for task_group in matching_task_groups:
            for task_id in task_group.get("task_id_list", []):
                task = self.get_task(task_id)
                if task and task.get("status") == "pending":
                    # Add task_group information to the task
                    task_with_info = task.copy()
                    task_with_info["stimulus_uuid"] = task_group.get("stimulus_uuid")
                    task_with_info["session_id"] = task_group.get("session_id")
                    pending_tasks.append(task_with_info)
        
        return pending_tasks