"""AsyncServiceComponent for handling asynchronous tasks in the flow."""

import os
from uuid import uuid4
from datetime import datetime

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

from .async_service import AsyncService


info = {
    "class_name": "AsyncServiceComponent",
    "description": ("This component manages asynchronous tasks"),
    "config_parameters": [
        {
            "name": "db_config",
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["mysql", "postgres", "memory"]},
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "database": {"type": "string"},
            },
            "description": "Database configuration for storing async tasks",
        },
        {
            "name": "default_timeout_seconds",
            "type": "integer",
            "description": "Default timeout for async tasks in seconds",
            "default": 3600
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "task_id": {"type": "string"},
            "stimulus_id": {"type": "string"},
            "approval_id": {"type": "string"},
            "decision": {"type": "string"},
            "form_data": {"type": "object"},
            "session_state": {"type": "object"},
            "stimulus_state": {"type": "object"},
            "agent_list_state": {"type": "object"},
            "gateway_id": {"type": "string"},
            "originator": {"type": "string"},
            "form_schema": {"type": "object"},
            "approval_data": {"type": "object"},
            "timeout_seconds": {"type": "integer"},
        },
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "payload": {"type": "object"},
        },
    },
}


class AsyncServiceComponent(ComponentBase):
    """This component manages asynchronous tasks."""
    
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        
        db_config = self.get_config("db_config", {})
        if "default_timeout_seconds" in self.config:
            db_config["default_timeout_seconds"] = self.get_config("default_timeout_seconds")
            
        self.async_service = AsyncService(db_config)
    
    def invoke(self, message: Message, data):
        """Handle incoming messages."""
        if not data:
            log.error("No data received")
            self.discard_current_message()
            return None
        
        user_properties = message.get_user_properties() or {}
        action = data.get("action")
        
        if not action:
            log.error("No action specified")
            self.discard_current_message()
            return None
        
        try:
            if action == "create_task":
                return self._handle_create_task(data, user_properties)
            elif action == "add_approval":
                return self._handle_add_approval(data, user_properties)
            elif action == "add_decision":
                return self._handle_add_decision(data, user_properties)
            elif action == "check_timeouts":
                return self._handle_check_timeouts(data, user_properties)
            elif action == "get_task":
                return self._handle_get_task(data, user_properties)
            else:
                log.error(f"Unknown action: {action}")
                self.discard_current_message()
                return None
        except Exception as e:
            log.error(f"Error processing async service request: {e}")
            self.discard_current_message()
            return None
    
    def _handle_create_task(self, data, user_properties):
        """Handle create_task action."""
        stimulus_id = data.get("stimulus_id")
        session_state = data.get("session_state", {})
        stimulus_state = data.get("stimulus_state", {})
        agent_list_state = data.get("agent_list_state", {})
        gateway_id = data.get("gateway_id")
        timeout_seconds = data.get("timeout_seconds")
        
        if not stimulus_id:
            log.error("No stimulus_id provided")
            self.discard_current_message()
            return None
            
        if not gateway_id:
            log.error("No gateway_id provided")
            self.discard_current_message()
            return None
        
        task_id = self.async_service.create_task(
            stimulus_id=stimulus_id,
            session_state=session_state,
            stimulus_state=stimulus_state,
            agent_list_state=agent_list_state,
            gateway_id=gateway_id,
            timeout_seconds=timeout_seconds
        )
        
        return {
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/task/created",
            "payload": {
                "task_id": task_id,
                "stimulus_id": stimulus_id,
                "gateway_id": gateway_id,
                "status": "pending"
            }
        }
    
    def _handle_add_approval(self, data, user_properties):
        """Handle add_approval action."""
        task_id = data.get("task_id")
        originator = data.get("originator")
        form_schema = data.get("form_schema")
        approval_data = data.get("approval_data")
        
        if not task_id:
            log.error("No task_id provided")
            self.discard_current_message()
            return None
            
        if not originator:
            log.error("No originator provided")
            self.discard_current_message()
            return None
            
        if not form_schema:
            log.error("No form_schema provided")
            self.discard_current_message()
            return None
            
        if not approval_data:
            log.error("No approval_data provided")
            self.discard_current_message()
            return None
        
        approval_id = self.async_service.add_approval(
            task_id=task_id,
            originator=originator,
            form_schema=form_schema,
            approval_data=approval_data
        )
        
        # Get the task to get the gateway_id
        task = self.async_service.get_task(task_id)
        if not task:
            log.error(f"Task {task_id} not found")
            self.discard_current_message()
            return None
        
        gateway_id = task.get("gateway_id")
        if not gateway_id:
            log.error(f"No gateway_id found for task {task_id}")
            self.discard_current_message()
            return None
        
        # Send approval request to the gateway
        return {
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/approval/request/{gateway_id}",
            "payload": {
                "task_id": task_id,
                "approval_id": approval_id,
                "form_schema": form_schema,
                "approval_data": approval_data,
                "originator": originator
            }
        }
    
    def _handle_add_decision(self, data, user_properties):
        """Handle add_decision action."""
        approval_id = data.get("approval_id")
        decision = data.get("decision")
        form_data = data.get("form_data", {})
        
        if not approval_id:
            log.error("No approval_id provided")
            self.discard_current_message()
            return None
            
        if not decision:
            log.error("No decision provided")
            self.discard_current_message()
            return None
        
        try:
            # Add the decision
            decision_id = self.async_service.add_decision(
                approval_id=approval_id,
                decision=decision,
                form_data=form_data
            )
            
            # Find the task containing this approval
            task_id = None
            for tid, task in self.async_service.tasks.items():
                if "approvals" in task and approval_id in task["approvals"]:
                    task_id = tid
                    break
            
            if not task_id:
                log.error(f"No task found for approval {approval_id}")
                self.discard_current_message()
                return None
        except ValueError as e:
            log.error(f"Error processing approval decision: {e}")
            self.discard_current_message()
            return None
        
        # Check if the task is complete
        if self.async_service.is_task_complete(task_id):
            task = self.async_service.get_task(task_id)
            
            # Resume the task
            return {
                "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/orchestrator/resume",
                "payload": {
                    "task_id": task_id,
                    "stimulus_id": task["stimulus_id"],
                    "session_state": task["session_state"],
                    "stimulus_state": task["stimulus_state"],
                    "agent_list_state": task["agent_list_state"],
                    "approval_decisions": task["approval_decisions"]
                }
            }
        else:
            # Just acknowledge the decision
            return {
                "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/decision/received",
                "payload": {
                    "approval_id": approval_id,
                    "decision": decision,
                    "status": "pending"  # Task is still pending more approvals
                }
            }
    
    def _handle_check_timeouts(self, data, user_properties):
        """Handle check_timeouts action."""
        timed_out_tasks = self.async_service.check_timeouts()
        
        if not timed_out_tasks:
            self.discard_current_message()
            return None
        
        events = []
        for task in timed_out_tasks:
            gateway_id = task.get("gateway_id")
            if gateway_id:
                events.append({
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/approval/timeout/{gateway_id}",
                    "payload": {
                        "task_id": task["task_id"],
                        "stimulus_id": task["stimulus_id"],
                        "status": "timeout"
                    }
                })
        
        return events
    
    def _handle_get_task(self, data, user_properties):
        """Handle get_task action."""
        task_id = data.get("task_id")
        stimulus_id = data.get("stimulus_id")
        
        if not task_id and not stimulus_id:
            log.error("Neither task_id nor stimulus_id provided")
            self.discard_current_message()
            return None
        
        task = None
        if task_id:
            task = self.async_service.get_task(task_id)
        elif stimulus_id:
            task = self.async_service.get_task_by_stimulus_id(stimulus_id)
        
        if not task:
            log.error(f"Task not found: task_id={task_id}, stimulus_id={stimulus_id}")
            self.discard_current_message()
            return None
        
        return {
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/task/info",
            "payload": {
                "task_id": task["task_id"],
                "stimulus_id": task["stimulus_id"],
                "status": task["status"],
                "created_at": task["created_at"].isoformat() if isinstance(task["created_at"], datetime) else task["created_at"],
                "timeout_at": task["timeout_at"].isoformat() if isinstance(task["timeout_at"], datetime) else task["timeout_at"],
                "gateway_id": task.get("gateway_id"),
                "approvals": {
                    aid: {
                        "originator": a["originator"],
                        "created_at": a["created_at"].isoformat() if isinstance(a["created_at"], datetime) else a["created_at"]
                    } for aid, a in task.get("approvals", {}).items()
                },
                "approval_decisions": {
                    aid: {
                        "decision": d["decision"],
                        "created_at": d["created_at"].isoformat() if isinstance(d["created_at"], datetime) else d["created_at"]
                    } for aid, d in task.get("approval_decisions", {}).items()
                }
            }
        }