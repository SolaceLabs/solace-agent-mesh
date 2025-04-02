"""MongoDB storage provider for async service."""

from datetime import datetime
from typing import Dict, List, Optional

import pymongo
from solace_ai_connector.common.log import log

from .base_storage_provider import BaseStorageProvider


class MongoDBStorageProvider(BaseStorageProvider):
    """MongoDB storage provider for async service."""
    
    def __init__(self, connection_string: str, username: str = "", password: str = ""):
        """Initialize the MongoDB storage provider."""
        try:
            # Connect to MongoDB
            if username and password:
                client = pymongo.MongoClient(
                    connection_string,
                    username=username,
                    password=password,
                )
            else:
                client = pymongo.MongoClient(connection_string)
            
            # Get database and collections
            self.db = client["async_service"]
            self.task_groups_collection = self.db["task_groups"]
            self.tasks_collection = self.db["tasks"]
            
            # Create indexes
            self.task_groups_collection.create_index("task_group_id", unique=True)
            self.tasks_collection.create_index("task_id", unique=True)
            self.tasks_collection.create_index("task_group_id")
            self.tasks_collection.create_index("status")
            
            log.info("Connected to MongoDB")
        except Exception as e:
            log.error(f"Failed to connect to MongoDB: {e}")
            raise
    
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
        try:
            self.task_groups_collection.insert_one({
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
            })
            log.debug(f"Created task group: {task_group_id}")
        except Exception as e:
            log.error(f"Failed to create task group: {e}")
            raise
    
    def get_task_group(self, task_group_id: str) -> Optional[Dict]:
        """Get a task group."""
        try:
            task_group = self.task_groups_collection.find_one({"task_group_id": task_group_id})
            return task_group
        except Exception as e:
            log.error(f"Failed to get task group: {e}")
            return None
    
    def update_task_group(self, task_group: Dict) -> None:
        """Update a task group."""
        try:
            task_group_id = task_group.get("task_group_id")
            result = self.task_groups_collection.replace_one(
                {"task_group_id": task_group_id},
                task_group,
            )
            if result.matched_count == 0:
                log.error(f"Task group not found: {task_group_id}")
            else:
                log.debug(f"Updated task group: {task_group_id}")
        except Exception as e:
            log.error(f"Failed to update task group: {e}")
            raise
    
    def delete_task_group(self, task_group_id: str) -> None:
        """Delete a task group."""
        try:
            result = self.task_groups_collection.delete_one({"task_group_id": task_group_id})
            if result.deleted_count == 0:
                log.error(f"Task group not found: {task_group_id}")
            else:
                log.debug(f"Deleted task group: {task_group_id}")
        except Exception as e:
            log.error(f"Failed to delete task group: {e}")
            raise
    
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
        requester_list: List[Dict] = None,  # Add requester_list parameter
    ) -> None:
        """Create a task."""
        try:
            self.tasks_collection.insert_one({
                "task_id": task_id,
                "task_group_id": task_group_id,
                "async_response": async_response,
                "creation_time": creation_time,
                "timeout_time": timeout_time,
                "status": status,
                "user_response": user_response,
                "originator": originator,  # Store originator
                "requester_list": requester_list or [],  # Store requester_list
            })
            log.debug(f"Created task: {task_id}")
        except Exception as e:
            log.error(f"Failed to create task: {e}")
            raise
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a task."""
        try:
            task = self.tasks_collection.find_one({"task_id": task_id})
            return task
        except Exception as e:
            log.error(f"Failed to get task: {e}")
            return None
    
    def update_task(self, task: Dict) -> None:
        """Update a task."""
        try:
            task_id = task.get("task_id")
            result = self.tasks_collection.replace_one(
                {"task_id": task_id},
                task,
            )
            if result.matched_count == 0:
                log.error(f"Task not found: {task_id}")
            else:
                log.debug(f"Updated task: {task_id}")
        except Exception as e:
            log.error(f"Failed to update task: {e}")
            raise
    
    def delete_task(self, task_id: str) -> None:
        """Delete a task."""
        try:
            result = self.tasks_collection.delete_one({"task_id": task_id})
            if result.deleted_count == 0:
                log.error(f"Task not found: {task_id}")
            else:
                log.debug(f"Deleted task: {task_id}")
        except Exception as e:
            log.error(f"Failed to delete task: {e}")
            raise
    
    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks."""
        try:
            tasks = list(self.tasks_collection.find({"status": "pending"}))
            return tasks
        except Exception as e:
            log.error(f"Failed to get pending tasks: {e}")
            return []