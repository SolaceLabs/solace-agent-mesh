"""This component handles asynchronous tasks for a stimulus id."""

import os
import uuid
import threading
import time
from datetime import datetime, timedelta

from solace_ai_connector.common.event import Event, EventType

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

from .storage_providers.memory_storage_provider import MemoryStorageProvider
from .storage_providers.mongodb_storage_provider import MongoDBStorageProvider

info = {
    "class_name": "AsyncServiceComponent",
    "description": ("This component handles asynchronous tasks for a stimulus id"),
    "config_parameters": [
        {
            "name": "storage_provider",
            "description": "The storage provider to use (memory or mongodb)",
            "type": "string",
            "default": "memory",
        },
        {
            "name": "mongodb_connection_string",
            "description": "The connection string for MongoDB (if using mongodb)",
            "type": "string",
            "default": "mongodb://localhost:27017/",
        },
        {
            "name": "mongodb_username",
            "description": "The username for MongoDB authentication",
            "type": "string",
            "default": "",
        },
        {
            "name": "mongodb_password",
            "description": "The password for MongoDB authentication",
            "type": "string",
            "default": "",
        },
        {
            "name": "task_timeout",
            "description": "The timeout for tasks in seconds",
            "type": "integer",
            "default": 3600,  # 1 hour
        },
        {
            "name": "timeout_check_interval",
            "description": "The interval in seconds between timeout checks",
            "type": "integer",
            "default": 60,  # Default: check every 60 seconds
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "event_type": {"type": "string"},
            "task_group_id": {"type": "string"},
            "task_id": {"type": "string"},
            "user_response": {"type": "object"},
            "stimulus_uuid": {"type": "string"},
            "session_id": {"type": "string"},
            "gateway_id": {"type": "string"},
            "identity": {"type": "string"},
            "stimulus_state": {"type": "array"},
            "agent_responses": {"type": "array"},
            "async_responses": {"type": "array"},
        },
        "required": ["event_type"],
        "allOf": [
            {
                "if": {
                    "properties": {"event_type": {"enum": ["get_pending_forms"]}}
                },
                "then": {
                    "required": ["gateway_id", "identity"]
                }
            }
        ]
    },
    "output_schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "payload": {"type": "object"},
            },
            "required": ["topic", "payload"],
        },
    },
}


class AsyncServiceComponent(ComponentBase):
    """This component handles asynchronous tasks for a stimulus id."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        
        # Initialize storage provider
        storage_provider = self.config.get("storage_provider", "memory")
        if storage_provider == "memory":
            self.storage_provider = MemoryStorageProvider()
        elif storage_provider == "mongodb":
            mongodb_connection_string = self.config.get("mongodb_connection_string", "mongodb://localhost:27017/")
            mongodb_username = self.config.get("mongodb_username", "")
            mongodb_password = self.config.get("mongodb_password", "")
            self.storage_provider = MongoDBStorageProvider(
                connection_string=mongodb_connection_string,
                username=mongodb_username,
                password=mongodb_password
            )
        else:
            raise ValueError(f"Unsupported storage provider: {storage_provider}")
        
        # Set task timeout
        self.task_timeout = self.config.get("task_timeout", 60)  # Default 1 hour
        
        # Set timeout checker parameters
        self.timeout_check_interval = self.config.get("timeout_check_interval", 60)  # Default: check every 60 seconds
        self.timeout_checker_running = False
        self.timeout_checker_thread = None
        
        # Start timeout checker
        self.start_timeout_checker()

    def invoke(self, message: Message, data):
        """Handle async service events"""
        
        if not data:
            log.error("No data received")
            self.discard_current_message()
            return None
            
        event_type = data.get("event_type")
        
        if event_type == "create_task_group":
            return self.handle_create_task_group(message, data)  # Pass message parameter
        elif event_type == "post_user_form":
            return self.handle_user_response(data)
        elif event_type == "get_pending_forms":
            return self.handle_get_pending_forms(message, data)  # New handler
        else:
            log.error(f"Unknown event type: {event_type}")
            self.discard_current_message()
            return None
    
    def handle_create_task_group(self, message, data):
        """Handle create task group event"""
        
        stimulus_uuid = data.get("stimulus_uuid")
        session_id = data.get("session_id")
        gateway_id = data.get("gateway_id")
        stimulus_state = data.get("stimulus_state")
        agent_responses = data.get("agent_responses")
        async_responses = data.get("async_responses", [])
        
        if not stimulus_uuid or not session_id or not gateway_id:
            log.error("Missing required fields for create_task_group")
            self.discard_current_message()
            return None
        
        # Extract interface_properties and identity from user_properties
        interface_properties = message.user_properties.get("interface_properties", {})
        identity = message.user_properties.get("identity", {})
        
        # Create originator and approver_list
        originator = {
            "interface_properties": interface_properties,
            "identity": identity
        }
        
        approver_list = [originator]
        
        # Get the original user properties from the message
        user_properties = message.get_user_properties() or {}
            
        # Create task group
        task_group_id = str(uuid.uuid4())
        task_id_list = []
        
        # Create events for each async task
        events = []
        
        # Create tasks for each async response
        for async_response in async_responses:
            task_id = str(uuid.uuid4())
            task_id_list.append(task_id)
            
            # Create task
            self.storage_provider.create_task(
                task_id=task_id,
                task_group_id=task_group_id,
                async_response=async_response,
                creation_time=datetime.now(),
                timeout_time=datetime.now() + timedelta(seconds=self.task_timeout),
                status="pending",
                user_response=None,
                originator=originator,  # Add originator
                approver_list=approver_list  # Add approver_list
            )
            
            # Extract user_form from async_response
            # The user_form is nested under the "response" key
            user_form = async_response.get("response", {}).get("user_form")
            
            if user_form:
                # Create event for this task
                events.append({
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/userRequest/async-service/{gateway_id}",
                    "payload": {
                        "task_id": task_id,
                        "user_form": user_form,
                        "stimulus_uuid": stimulus_uuid,
                        "session_id": session_id,
                    },
                    "user_properties" : user_properties,
                })
        
        # Create task group
        self.storage_provider.create_task_group(
            task_group_id=task_group_id,
            stimulus_uuid=stimulus_uuid,
            session_id=session_id,
            gateway_id=gateway_id,
            stimulus_state=stimulus_state,
            agent_responses=agent_responses,
            user_responses={},
            task_id_list=task_id_list,
            creation_time=datetime.now(),
            status="pending",
            user_properties=user_properties,  # Store the original user properties
        )
        
        log.info(f"Created task group {task_group_id} with {len(task_id_list)} tasks for stimulus {stimulus_uuid}")
        
        # Return events if any
        if events:
            log.info(f"Sending {len(events)} user form events to gateway {gateway_id}")
            return events
        
        # Return success
        self.discard_current_message()
        return None
    
    def handle_user_response(self, data):
        """Handle user response event"""
        
        task_id = data.get("task_id")
        form_data = data.get("form_data")
        
        if not task_id or not form_data:
            log.error("Missing required fields for user_response")
            self.discard_current_message()
            return None
            
        # Get task
        task = self.storage_provider.get_task(task_id)
        if not task:
            log.error(f"Task not found: {task_id}")
            self.discard_current_message()
            return None
            
        # Update task
        task["status"] = "completed"
        task["user_response"] = form_data
        self.storage_provider.update_task(task)
        
        # Get task group
        task_group = self.storage_provider.get_task_group(task["task_group_id"])
        if not task_group:
            log.error(f"Task group not found: {task['task_group_id']}")
            self.discard_current_message()
            return None
            
        # Update task group
        task_group["user_responses"][task_id] = form_data
        self.storage_provider.update_task_group(task_group)
        
        # Check if all tasks are completed
        all_completed = True
        for task_id in task_group["task_id_list"]:
            task = self.storage_provider.get_task(task_id)
            if task["status"] != "completed":
                all_completed = False
                break
                
        if all_completed:
            # All tasks are completed, send response back to orchestrator
            task_group["status"] = "completed"
            self.storage_provider.update_task_group(task_group)
            
            # Get the original user properties
            original_user_properties = task_group.get("user_properties", {})
            
            # Prepare user responses with action information
            detailed_user_responses = {}
            for task_id, form_data in task_group["user_responses"].items():
                task = self.storage_provider.get_task(task_id)
                if task:
                    async_response = task["async_response"]
                    detailed_user_responses[task_id] = {
                        "user_response": form_data,
                        "action_name": async_response.get("action_name"),
                        "action_params": async_response.get("action_params"),
                        "action_idx": async_response.get("action_idx"),
                        "action_list_id": async_response.get("action_list_id"),
                        "originator": async_response.get("originator"),
                        "async_response_id": async_response.get("async_response_id"),
                        "agent_name": async_response.get("agent_name"),  # Add agent_name
                        "task_id": task_id,
                    }
            
            # Create 2 events:
            # 1. Send response to gateway to update the status that processing has resumed
            # 2. Send response to orchestrator with all user responses
            gateway_id = task_group["gateway_id"]
            events = [{
                    "payload": {
                        "status_update": True,
                        "streaming": True,
                        "text": "Request processing resumed.",
                    },
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/streamingResponse/orchestrator/{gateway_id}",
                    "user_properties": original_user_properties,  # Include the original user properties

                },
                {
                "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/orchestrator/async-response",
                "payload": {
                    "stimulus_uuid": task_group["stimulus_uuid"],
                    "session_id": task_group["session_id"],
                    "gateway_id": task_group["gateway_id"],
                    "user_responses": detailed_user_responses,
                    "agent_responses": task_group["agent_responses"],  # Include all agent responses
                    "stimulus_state": task_group["stimulus_state"],    # Include stimulus state for history
                },
                "user_properties": original_user_properties,  # Include the original user properties
            }]
            
            log.info(f"All tasks completed for task group {task_group['task_group_id']}, sending response back to orchestrator")
            
            return events
        
        # Not all tasks are completed yet
        self.discard_current_message()
        return None
        
    def handle_get_pending_forms(self, message, data):
        """Handle get pending forms event"""
        
        user_properties = message.get_user_properties() or {}
        gateway_id = user_properties.get("gateway_id", None)
        identity = user_properties.get("identity", None)
        
        if not gateway_id:
            log.error("Missing required field 'gateway_id' for get_pending_forms")
            self.discard_current_message()
            return None
            
        if not identity:
            log.error("Missing required field 'identity' for get_pending_forms")
            self.discard_current_message()
            return None
        
        # Get all pending tasks for the gateway_id
        pending_tasks = self.storage_provider.get_pending_tasks_by_gateway_id(gateway_id)
        
        # Format the response, filtering by identity
        pending_forms = []
        for task in pending_tasks:
            # Check if the identity matches any identity in the approver_list
            approver_list = task.get("approver_list", [])
            identity_match = False
            
            for approver in approver_list:
                if approver.get("identity") == identity:
                    identity_match = True
                    break
            
            # Only include tasks where the identity matches
            if identity_match:
                # Extract the user_form from the async_response
                async_response = task.get("async_response", {})
                user_form = async_response.get("response", {}).get("user_form")
                
                if user_form:
                    pending_forms.append({
                        "task_id": task.get("task_id"),
                        "session_id": task.get("session_id"),
                        "stimulus_uuid": task.get("stimulus_uuid"),
                        "user_form": user_form
                    })
        
        # Get the original user properties from the message
        user_properties = message.get_user_properties() or {}
        
        # Create the event to send back
        event = {
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/formsResponse/async-service/{gateway_id}",
            "payload": {
                "event_type": "get_pending_forms_response",
                "pending_forms": pending_forms
            },
            "user_properties": user_properties
        }
        
        log.info(f"Sending {len(pending_forms)} pending forms for gateway {gateway_id} and identity {identity}")
        
        return [event]
    
    def start_timeout_checker(self):
        """Start timeout checker"""
        self.timeout_checker_running = True
        self.timeout_checker_thread = threading.Thread(
            target=self._timeout_checker_loop,
            daemon=True  # Make it a daemon thread so it doesn't block program exit
        )
        self.timeout_checker_thread.start()
        log.info("Started timeout checker thread")
        
    def _timeout_checker_loop(self):
        """Background loop to check for timeouts"""
        while self.timeout_checker_running:
            try:
                # Check for timeouts
                self._process_timeouts()
            except Exception as e:
                log.error(f"Error in timeout checker: {e}")
            
            # Sleep for a while before checking again
            time.sleep(self.timeout_check_interval)
    
    def check_timeouts(self):
        """Check for timed out tasks"""
        now = datetime.now()
        
        # Get all pending tasks
        pending_tasks = self.storage_provider.get_pending_tasks()
        
        events = []
        
        for task in pending_tasks:
            if task["timeout_time"] < now:
                # Task has timed out
                task["status"] = "timed_out"
                self.storage_provider.update_task(task)
                
                # Get task group
                task_group = self.storage_provider.get_task_group(task["task_group_id"])
                if task_group:
                    # Check if all tasks are now completed or timed out
                    all_done = True
                    for task_id in task_group["task_id_list"]:
                        task = self.storage_provider.get_task(task_id)
                        if task["status"] == "pending":
                            all_done = False
                            break
                            
                    if all_done:
                        # All tasks are completed or timed out, send response back to orchestrator
                        task_group["status"] = "timed_out"
                        self.storage_provider.update_task_group(task_group)
                        
                        # Get the original user properties
                        original_user_properties = task_group.get("user_properties", {})
                        
                        # Create event to send back to orchestrator
                        events.append({
                            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/orchestrator/async-response",
                            "payload": {
                                "stimulus_uuid": task_group["stimulus_uuid"],
                                "session_id": task_group["session_id"],
                                "gateway_id": task_group["gateway_id"],
                                "user_responses": task_group["user_responses"],
                                "agent_responses": task_group["agent_responses"],
                                "stimulus_state": task_group["stimulus_state"],
                                "timed_out": True,
                            },
                            "user_properties": original_user_properties,
                        })
                        
                        log.info(f"Task group timed out: {task_group['task_group_id']}")
        
        # Send events if any
        if events:
            self._send_events(events)
            
    def _send_events(self, events):
        """Send events from the background thread"""
        for event in events:
            try:
                # Create a message to send
                message = Message(
                    payload=event["payload"],
                    topic=event["topic"]
                )
                
                # Set user properties if available
                if "user_properties" in event:
                    message.set_user_properties(event["user_properties"])
                
                message.set_previous({"topic": event["topic"], "payload": event["payload"], "user_properties": event["user_properties"]})
                
                # Send the message
                self.send_to_flow("send-spontaneous-message", message)
                log.info(f"Sent timeout event to {event['topic']}")
            except Exception as e:
                log.error(f"Error sending timeout event: {e}")
                
    def stop_timeout_checker(self):
        """Stop the timeout checker thread"""
        if hasattr(self, 'timeout_checker_running'):
            self.timeout_checker_running = False
            if hasattr(self, 'timeout_checker_thread') and self.timeout_checker_thread is not None:
                self.timeout_checker_thread.join(timeout=1.0)  # Wait for thread to finish
                log.info("Stopped timeout checker thread")
                
    def __del__(self):
        """Clean up resources when the component is destroyed"""
        try:
            self.stop_timeout_checker()
        except:
            pass  # Ignore errors during cleanup
            
    def _process_timeouts(self):
        """Process timed out tasks and send events"""
        now = datetime.now()
        
        # Get all pending tasks
        pending_tasks = self.storage_provider.get_pending_tasks()
        
        events = []
        
        for task in pending_tasks:
            if task["timeout_time"] < now:
                # Task has timed out
                task["status"] = "timed_out"
                self.storage_provider.update_task(task)
                
                # Get task group
                task_group = self.storage_provider.get_task_group(task["task_group_id"])
                if task_group:
                    # Check if all tasks are now completed or timed out
                    all_done = True
                    for task_id in task_group["task_id_list"]:
                        task = self.storage_provider.get_task(task_id)
                        if task["status"] == "pending":
                            all_done = False
                            break
                            
                    if all_done:
                        # All tasks are completed or timed out, send response back to orchestrator
                        task_group["status"] = "timed_out"
                        self.storage_provider.update_task_group(task_group)
                        
                        # Get the original user properties
                        original_user_properties = task_group.get("user_properties", {})
                        
                        # Create event to send back to orchestrator
                        events.append({
                            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/orchestrator/async-response",
                            "payload": {
                                "stimulus_uuid": task_group["stimulus_uuid"],
                                "session_id": task_group["session_id"],
                                "gateway_id": task_group["gateway_id"],
                                "user_responses": task_group["user_responses"],
                                "agent_responses": task_group["agent_responses"],
                                "stimulus_state": task_group["stimulus_state"],
                                "timed_out": True,
                            },
                            "user_properties": original_user_properties,
                        })
                        
                        log.info(f"Task group timed out: {task_group['task_group_id']}")
        
        # Send events if any
        if events:
            self._send_events(events)