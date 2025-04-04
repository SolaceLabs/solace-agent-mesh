"""Base storage provider for async service."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional


class BaseStorageProvider(ABC):
    """Base storage provider for async service."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_task_group(self, task_group_id: str) -> Optional[Dict]:
        """Get a task group."""
        pass
    
    @abstractmethod
    def update_task_group(self, task_group: Dict) -> None:
        """Update a task group."""
        pass
    
    @abstractmethod
    def delete_task_group(self, task_group_id: str) -> None:
        """Delete a task group."""
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get a task."""
        pass
    
    @abstractmethod
    def update_task(self, task: Dict) -> None:
        """Update a task."""
        pass
    
    @abstractmethod
    def delete_task(self, task_id: str) -> None:
        """Delete a task."""
        pass
    
    @abstractmethod
    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks."""
        pass