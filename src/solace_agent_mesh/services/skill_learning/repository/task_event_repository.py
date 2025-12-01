"""
Task event repository for fetching task events from the gateway database.

This module provides access to task events stored by the gateway,
allowing the skill learning service to fetch historical task data
for learning purposes.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from sqlalchemy import create_engine, Column, String, BigInteger, JSON, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

Base = declarative_base()


class TaskModel(Base):
    """SQLAlchemy model for tasks (read-only mirror of gateway's tasks table)."""
    
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    parent_task_id = Column(String, nullable=True)
    start_time = Column(BigInteger, nullable=False)
    end_time = Column(BigInteger, nullable=True)
    status = Column(String, nullable=True)
    initial_request_text = Column(Text, nullable=True)


class TaskEventModel(Base):
    """SQLAlchemy model for task events (read-only mirror of gateway's task_events table)."""
    
    __tablename__ = "task_events"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"), index=True)
    user_id = Column(String, nullable=True)
    created_time = Column(BigInteger, nullable=False)
    topic = Column(Text, nullable=False)
    direction = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)


@dataclass
class TaskEventData:
    """Task event data for skill learning."""
    id: str
    task_id: str
    user_id: Optional[str]
    created_time: int
    topic: str
    direction: str
    payload: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for task analyzer."""
        # Extract relevant fields from payload for analysis
        result = {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "timestamp": self.created_time,
            "topic": self.topic,
            "direction": self.direction,
        }
        
        # Merge payload fields
        if isinstance(self.payload, dict):
            # Try to extract from A2A JSON-RPC format first
            a2a_result = self._extract_from_a2a_format()
            if a2a_result:
                result.update(a2a_result)
                return result
            
            # Fall back to legacy format extraction
            # Extract event type from topic or payload
            if "event_type" in self.payload:
                result["event_type"] = self.payload["event_type"]
            elif "type" in self.payload:
                result["event_type"] = self.payload["type"]
            else:
                # Infer from topic
                result["event_type"] = self._infer_event_type()
            
            # Extract agent name
            if "agent_name" in self.payload:
                result["agent_name"] = self.payload["agent_name"]
            elif "agent" in self.payload:
                result["agent_name"] = self.payload["agent"]
            
            # Extract tool information
            if "tool_name" in self.payload:
                result["tool_name"] = self.payload["tool_name"]
            if "tool_call" in self.payload:
                tool_call = self.payload["tool_call"]
                if isinstance(tool_call, dict):
                    result["tool_name"] = tool_call.get("name", "")
                    result["parameters"] = tool_call.get("arguments", {})
            
            # Extract content
            if "content" in self.payload:
                result["content"] = self.payload["content"]
            if "data" in self.payload and isinstance(self.payload["data"], dict):
                result["data"] = self.payload["data"]
            
            # Extract success/result
            if "success" in self.payload:
                result["success"] = self.payload["success"]
            if "result" in self.payload:
                result["result"] = self.payload["result"]
        
        return result
    
    def _extract_from_a2a_format(self) -> Optional[Dict[str, Any]]:
        """
        Extract event data from A2A JSON-RPC format.
        
        A2A messages have structure like:
        {
            "id": "task-id",
            "jsonrpc": "2.0",
            "result": {
                "kind": "status-update",
                "metadata": {"agent_name": "..."},
                "status": {
                    "message": {
                        "parts": [
                            {"data": {"type": "llm_response", "data": {...}}}
                        ]
                    }
                }
            }
        }
        """
        if "jsonrpc" not in self.payload:
            return None
        
        result_data: Dict[str, Any] = {}
        
        # Extract from result (response) or params (request)
        a2a_result = self.payload.get("result", {})
        a2a_params = self.payload.get("params", {})
        
        # Get agent name from metadata
        metadata = a2a_result.get("metadata", {})
        if "agent_name" in metadata:
            result_data["agent_name"] = metadata["agent_name"]
        
        # Determine event type from kind
        kind = a2a_result.get("kind", "")
        if kind == "status-update":
            result_data["event_type"] = "status_update"
        elif kind == "message":
            result_data["event_type"] = "message"
        
        # Extract from status.message.parts for status updates
        status = a2a_result.get("status", {})
        message = status.get("message", {})
        parts = message.get("parts", [])
        
        # Also check params.message.parts for requests
        if not parts and a2a_params:
            params_message = a2a_params.get("message", {})
            parts = params_message.get("parts", [])
        
        # Process parts to find tool calls and other data
        for part in parts:
            part_data = part.get("data", {})
            if not isinstance(part_data, dict):
                continue
            
            data_type = part_data.get("type", "")
            
            if data_type == "llm_response":
                # Extract function calls from LLM response
                llm_data = part_data.get("data", {})
                content = llm_data.get("content", {})
                content_parts = content.get("parts", [])
                
                for content_part in content_parts:
                    if "function_call" in content_part:
                        func_call = content_part["function_call"]
                        result_data["event_type"] = "tool_call"
                        result_data["tool_name"] = func_call.get("name", "")
                        result_data["parameters"] = func_call.get("args", {})
                        result_data["tool_call_id"] = func_call.get("id", "")
                        result_data["success"] = True
                        return result_data
                    
                    if "text" in content_part:
                        result_data["content"] = content_part.get("text", "")
            
            elif data_type == "llm_invocation":
                # This is the LLM being called, extract conversation context
                request = part_data.get("request", {})
                contents = request.get("contents", [])
                
                # Get the user request from the conversation
                for content_item in contents:
                    if content_item.get("role") == "user":
                        user_parts = content_item.get("parts", [])
                        for user_part in user_parts:
                            if "text" in user_part and not user_part["text"].startswith("Request received"):
                                result_data["content"] = user_part.get("text", "")
                                result_data["event_type"] = "user_message"
                                break
            
            elif data_type == "tool_result":
                # Tool execution result
                result_data["event_type"] = "tool_result"
                result_data["result"] = part_data.get("result", {})
                result_data["success"] = part_data.get("success", True)
                result_data["tool_name"] = part_data.get("tool_name", "")
        
        # Check for final response
        if a2a_result.get("final", False):
            result_data["event_type"] = "task_complete"
            result_data["success"] = True
        
        return result_data if result_data else None
    
    def _infer_event_type(self) -> str:
        """Infer event type from topic."""
        topic_lower = self.topic.lower()
        
        if "tool" in topic_lower:
            if "result" in topic_lower or "response" in topic_lower:
                return "tool_result"
            return "tool_call"
        elif "message" in topic_lower:
            return "message"
        elif "delegation" in topic_lower:
            return "delegation"
        elif "complete" in topic_lower:
            return "task_complete"
        elif "start" in topic_lower:
            return "task_start"
        else:
            return "unknown"


@dataclass
class TaskData:
    """Task data for skill learning."""
    id: str
    user_id: str
    parent_task_id: Optional[str]
    start_time: int
    end_time: Optional[int]
    status: Optional[str]
    initial_request_text: Optional[str]


class TaskEventRepository:
    """
    Repository for fetching task events from the gateway database.
    
    This is a read-only repository that connects to the same database
    as the gateway to fetch task events for skill learning.
    """
    
    def __init__(
        self,
        database_url: str,
        pool_size: int = 5,
        max_overflow: int = 10,
    ):
        """
        Initialize the task event repository.
        
        Args:
            database_url: Database connection URL
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
        """
        self.database_url = database_url
        
        # Create engine with connection pooling
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,  # Verify connections before use
        )
        
        self.Session = sessionmaker(bind=self.engine)
        
        logger.info(f"Task event repository initialized with database: {database_url}")
    
    def get_task(self, task_id: str) -> Optional[TaskData]:
        """
        Get a task by ID.
        
        Args:
            task_id: The task ID
            
        Returns:
            TaskData if found, None otherwise
        """
        session = self.Session()
        try:
            model = session.query(TaskModel).filter(TaskModel.id == task_id).first()
            if not model:
                return None
            
            return TaskData(
                id=model.id,
                user_id=model.user_id,
                parent_task_id=model.parent_task_id,
                start_time=model.start_time,
                end_time=model.end_time,
                status=model.status,
                initial_request_text=model.initial_request_text,
            )
        finally:
            session.close()
    
    def get_task_events(self, task_id: str) -> List[TaskEventData]:
        """
        Get all events for a task.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of task events ordered by created_time
        """
        session = self.Session()
        try:
            models = (
                session.query(TaskEventModel)
                .filter(TaskEventModel.task_id == task_id)
                .order_by(TaskEventModel.created_time.asc())
                .all()
            )
            
            return [
                TaskEventData(
                    id=model.id,
                    task_id=model.task_id,
                    user_id=model.user_id,
                    created_time=model.created_time,
                    topic=model.topic,
                    direction=model.direction,
                    payload=model.payload or {},
                )
                for model in models
            ]
        finally:
            session.close()
    
    def get_task_events_as_dicts(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get all events for a task as dictionaries suitable for task analyzer.
        
        Args:
            task_id: The task ID
            
        Returns:
            List of event dictionaries
        """
        events = self.get_task_events(task_id)
        return [event.to_dict() for event in events]
    
    def get_task_with_events(
        self, 
        task_id: str
    ) -> Optional[tuple[TaskData, List[TaskEventData]]]:
        """
        Get a task with all its events.
        
        Args:
            task_id: The task ID
            
        Returns:
            Tuple of (task, events) if found, None otherwise
        """
        task = self.get_task(task_id)
        if not task:
            return None
        
        events = self.get_task_events(task_id)
        return task, events
    
    def get_related_task_events(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get events for a task and all related tasks in the hierarchy.
        
        This traverses the parent chain to find the root task,
        then collects events from all tasks in the hierarchy.
        
        Args:
            task_id: The starting task ID
            
        Returns:
            List of event dictionaries from all related tasks
        """
        session = self.Session()
        try:
            # Find root task (traverse up parent chain)
            root_task_id = task_id
            current_id = task_id
            visited = set()
            
            while current_id and current_id not in visited:
                visited.add(current_id)
                task_model = (
                    session.query(TaskModel)
                    .filter(TaskModel.id == current_id)
                    .first()
                )
                if not task_model or not task_model.parent_task_id:
                    root_task_id = current_id
                    break
                current_id = task_model.parent_task_id
            
            # Find all descendants of root (BFS)
            all_task_ids = {root_task_id}
            to_process = [root_task_id]
            
            while to_process:
                current = to_process.pop(0)
                children = (
                    session.query(TaskModel)
                    .filter(TaskModel.parent_task_id == current)
                    .all()
                )
                for child in children:
                    if child.id not in all_task_ids:
                        all_task_ids.add(child.id)
                        to_process.append(child.id)
            
            # Get all events for all tasks
            all_events = []
            for tid in all_task_ids:
                events = self.get_task_events_as_dicts(tid)
                all_events.extend(events)
            
            # Sort by timestamp
            all_events.sort(key=lambda e: e.get("timestamp", 0))
            
            return all_events
            
        finally:
            session.close()
    
    def get_completed_tasks(
        self,
        limit: int = 100,
        since_time: Optional[int] = None,
    ) -> List[TaskData]:
        """
        Get recently completed tasks.
        
        Args:
            limit: Maximum number of tasks to return
            since_time: Only return tasks completed after this time (epoch ms)
            
        Returns:
            List of completed tasks
        """
        session = self.Session()
        try:
            query = (
                session.query(TaskModel)
                .filter(TaskModel.status == "completed")
            )
            
            if since_time:
                query = query.filter(TaskModel.end_time >= since_time)
            
            query = query.order_by(TaskModel.end_time.desc()).limit(limit)
            
            models = query.all()
            
            return [
                TaskData(
                    id=model.id,
                    user_id=model.user_id,
                    parent_task_id=model.parent_task_id,
                    start_time=model.start_time,
                    end_time=model.end_time,
                    status=model.status,
                    initial_request_text=model.initial_request_text,
                )
                for model in models
            ]
        finally:
            session.close()
    
    def close(self):
        """Close the database connection."""
        self.engine.dispose()