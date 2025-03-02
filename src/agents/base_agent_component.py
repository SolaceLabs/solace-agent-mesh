"""This is the base class for all custom agent components"""

import json
import traceback
import time
import os
from abc import ABC
from typing import Dict, Any, List, Optional

from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.utils import ensure_slash_on_end

from ..services.llm_service.components.llm_service_component_base import LLMServiceComponentBase
from ..common.action_list import ActionList
from ..common.action_response import ActionResponse, ErrorInfo
from ..services.file_service import FileService
from ..services.file_service.file_utils import recursive_file_resolver
from ..services.middleware_service.middleware_service import MiddlewareService

agent_info = {
    "class_name": "BaseAgentComponent",
    "description": "This component handles action requests",
    "config_parameters": [
        {
            "name": "llm_service_topic",
            "required": False,
            "description": "The topic to use for the LLM service",
        },
        {
            "name": "embedding_service_topic",
            "required": False,
            "description": "The topic to use for the Embedding service",
        },
        {
            "name": "registration_interval",
            "required": False,
            "description": "The interval in seconds for agent registration",
            "default": 30,
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string"},
            "action_name": {"type": "string"},
            "params": {"type": "object", "additionalProperties": True},
        },
        "required": ["agent_name", "action_name", "params"],
    },
}


class BaseAgentComponent(LLMServiceComponentBase, ABC):
    """Base class for all agent components.
    
    This class provides common functionality for agent components, including
    action management, registration, and command/control integration.
    """

    @classmethod
    def get_actions_list(cls, **kwargs):  
        return ActionList(cls.actions, **kwargs)

    def __init__(self, module_info={}, **kwargs):
        """Initialize the BaseAgentComponent.
        
        Args:
            module_info: Information about the module.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(module_info, **kwargs)
        self.kwargs = kwargs
        self.action_config = kwargs.get("action_config", {})
        self.registration_interval = int(self.get_config("registration_interval", 30))

        self.llm_service_topic = self.get_config("llm_service_topic")
        if self.llm_service_topic:
            self.llm_service_topic = ensure_slash_on_end(self.llm_service_topic)
            # Check that the component's broker request/response is enabled
            if not self.is_broker_request_response_enabled():
                raise ValueError(
                    "LLM service topic is set, but the component does not "
                    f"have its broker request/response enabled, {self.__class__.__name__}"
                )

        self.embedding_service_topic = self.get_config("embedding_service_topic")
        if self.embedding_service_topic:
            self.embedding_service_topic = ensure_slash_on_end(
                self.embedding_service_topic
            )
            # Check that the component's broker request/response is enabled
            if not self.is_broker_request_response_enabled():
                raise ValueError(
                    "Embedding service topic is set, but the component does not "
                    f"have its broker request/response enabled, {self.__class__.__name__}"
                )
            
        self.action_list = self.get_actions_list(agent=self, config_fn=self.get_config)
        
        # Initialize action statistics
        self.action_stats = {}
        for action in self.action_list.actions:
            action_name = action.name
            self.action_stats[action_name] = {
                "total_invocations": 0,
                "successful_invocations": 0,
                "failed_invocations": 0,
                "average_execution_time_ms": 0,
                "last_execution_time_ms": 0,
                "last_error": None,
                "last_invoked_at": None,
            }
        
        # Register with command and control system
        self.register_with_command_control()

    def run(self):
        """Run the component.
        
        This is called when the component is started. We use this to send the
        first registration message.
        """
        # This is called when the component is started - we will use this to send the first registration message
        # Only do this for the first of the agent components
        if self.component_index == 0:
            # Send the registration message immediately - this will also schedule the timer
            self.handle_timer_event(None)

        # Call the base class run method
        super().run()

    def get_actions_summary(self):
        """Get a summary of the agent's actions.
        
        Returns:
            A summary of the agent's actions.
        """
        action_list = self.action_list
        return action_list.get_prompt_summary(prefix=self.info.get("agent_name"))

    def get_agent_summary(self):
        """Get a summary of the agent.
        
        Returns:
            A dictionary containing the agent's summary information.
        """
        return {
            "agent_name": self.info["agent_name"],
            "description": self.info["description"],
            "always_open": self.info.get("always_open", False),
            "actions": self.get_actions_summary(),
        }

    def invoke(self, message, data):
        """Invoke the component.
        
        Args:
            message: The message to process.
            data: The data to process.
            
        Returns:
            The result of the invocation.
        """
        action_name = data.get("action_name")
        action_response = None
        file_service = FileService()
        session_id = (message.get_user_properties() or {}).get("session_id")
        
        # Create a trace context for the action invocation
        with self.create_trace_context(
            operation=f"invoke_action_{action_name}",
            data={
                "action_name": action_name,
                "agent_name": self.info.get("agent_name"),
                "session_id": session_id,
                "params": data.get("action_params", {})
            },
            trace_level="INFO"
        ) as trace_ctx:
            
            start_time = time.time()
            
            if not action_name:
                log.error("Action name not provided. Data: %s", json.dumps(data))
                action_response = ActionResponse(
                    message="Internal error: Action name not provided. Please try again",
                )
                self._update_action_stats(action_name, False, start_time, "Action name not provided")
            else:
                action = self.action_list.get_action(action_name)
                if not action:
                    log.error(
                        "Action not found: %s. Data: %s", action_name, json.dumps(data)
                    )
                    action_response = ActionResponse(
                        message="Internal error: Action not found. Please try again",
                    )
                    self._update_action_stats(action_name, False, start_time, "Action not found")
                else:
                    resolved_params = data.get("action_params", {}).copy()
                    try:
                        resolved_params = recursive_file_resolver(
                            resolved_params,
                            resolver=file_service.resolve_all_resolvable_urls,
                            session_id=session_id,
                        )
                        
                        trace_ctx.progress(data={"resolved_params": "File URLs resolved successfully"})
                        
                        middleware_service = MiddlewareService()
                        if middleware_service.get("base_agent_filter")(message.user_properties or {}, action):
                            try:
                                meta = {
                                    "session_id": session_id,
                                }
                                action_response = action.invoke(resolved_params, meta)
                                
                                # Update action stats for successful invocation
                                self._update_action_stats(action_name, True, start_time)
                                
                                # Add trace data for successful completion
                                file_names = []
                                if action_response.files:
                                    file_names = action_response.files
                                if action_response.inline_files:
                                    file_names.extend([f.name for f in action_response.inline_files])
                                
                                trace_ctx.progress(data={
                                    "status": "success",
                                    "execution_time_ms": int((time.time() - start_time) * 1000),
                                    "message_length": len(action_response.message) if action_response.message else 0,
                                    "file_count": len(file_names),
                                    "file_names": file_names
                                })
                                
                            except Exception as e:
                                error_message = (
                                    f"Error invoking action {action_name} "
                                    f"in agent {self.info.get('agent_name', 'Unknown')}: \n\n"
                                    f"Exception name: {type(e).__name__}\n"
                                    f"Exception info: {str(e)}\n"
                                    f"Stack trace: {traceback.format_exc()}\n\n"
                                    f"Data: {json.dumps(data)}"
                                )
                                log.error(error_message)
                                action_response = ActionResponse(
                                    message=f"Internal error: {type(e).__name__} - Error invoking action. Details: {str(e)}",
                                    error_info=ErrorInfo(
                                        error_message=error_message,
                                    ),
                                )
                                
                                # Update action stats for failed invocation
                                self._update_action_stats(action_name, False, start_time, str(e))
                                
                                # Add trace data for error
                                trace_ctx.progress(data={
                                    "status": "error",
                                    "error_type": type(e).__name__,
                                    "error_message": str(e),
                                    "execution_time_ms": int((time.time() - start_time) * 1000)
                                })
                        else:
                            log.warning(
                                "Unauthorized access attempt for action %s. Data: %s",
                                action_name,
                                json.dumps(data),
                            )
                            action_response = ActionResponse(
                                message="Unauthorized: You don't have permission to perform this action.",
                            )
                            
                            # Update action stats for failed invocation
                            self._update_action_stats(action_name, False, start_time, "Unauthorized access")
                            
                            # Add trace data for unauthorized access
                            trace_ctx.progress(data={
                                "status": "unauthorized",
                                "execution_time_ms": int((time.time() - start_time) * 1000)
                            })
                    except Exception as e:
                        log.error(
                            "Error resolving file service URLs: %s. Data: %s",
                            str(e),
                            json.dumps(data),
                            exc_info=True,
                        )
                        action_response = ActionResponse(
                            message=f"Error resolving file URLs. Details: {str(e)}",
                        )
                        
                        # Update action stats for failed invocation
                        self._update_action_stats(action_name, False, start_time, f"Error resolving file URLs: {str(e)}")
                        
                        # Add trace data for file resolution error
                        trace_ctx.progress(data={
                            "status": "error",
                            "error_type": "FileResolutionError",
                            "error_message": str(e),
                            "execution_time_ms": int((time.time() - start_time) * 1000)
                        })

            action_response.action_list_id = data.get("action_list_id")
            action_response.action_idx = data.get("action_idx")
            action_response.action_name = action_name
            action_response.action_params = data.get("action_params", {})
            try:
                action_response_dict = action_response.to_dict()
            except Exception as e:
                log.error(
                    "Error after action %s in converting action response to dict: %s. Data: %s",
                    action_name,
                    str(e),
                    json.dumps(data),
                    exc_info=True,
                )
                action_response_dict = {
                    "message": "Internal error: Error converting action response to dict",
                }
                
                # Add trace data for serialization error
                trace_ctx.progress(data={
                    "status": "error",
                    "error_type": "SerializationError",
                    "error_message": str(e),
                    "execution_time_ms": int((time.time() - start_time) * 1000)
                })

        # Construct the response topic
        response_topic = f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/actionResponse/agent/{self.info['agent_name']}/{action_name}"

        return {"payload": action_response_dict, "topic": response_topic}

    def handle_timer_event(self, timer_data):
        """Handle the timer event for agent registration.
        
        Args:
            timer_data: The timer data.
        """
        registration_message = self.get_agent_summary()
        registration_topic = f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/register/agent/{self.info['agent_name']}"

        message = Message(
            topic=registration_topic,
            payload=registration_message,
        )

        message.set_previous(
            {"topic": registration_topic, "payload": registration_message}
        )

        self.send_message(message)

        # Re-schedule the timer
        self.add_timer(self.registration_interval * 1000, "agent_registration")
    
    def _update_action_stats(self, action_name: str, success: bool, start_time: float, error: str = None) -> None:
        """Update the statistics for an action.
        
        Args:
            action_name: The name of the action.
            success: Whether the action was successful.
            start_time: The start time of the action.
            error: The error message, if any.
        """
        if action_name not in self.action_stats:
            self.action_stats[action_name] = {
                "total_invocations": 0,
                "successful_invocations": 0,
                "failed_invocations": 0,
                "average_execution_time_ms": 0,
                "last_execution_time_ms": 0,
                "last_error": None,
                "last_invoked_at": None,
            }
        
        stats = self.action_stats[action_name]
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Update counters
        stats["total_invocations"] += 1
        if success:
            stats["successful_invocations"] += 1
        else:
            stats["failed_invocations"] += 1
            stats["last_error"] = error
        
        # Update timing information
        stats["last_execution_time_ms"] = execution_time_ms
        stats["last_invoked_at"] = time.time()
        
        # Update average execution time
        total_time = stats["average_execution_time_ms"] * (stats["total_invocations"] - 1)
        stats["average_execution_time_ms"] = (total_time + execution_time_ms) / stats["total_invocations"]
    
    def register_with_command_control(self) -> None:
        """Register the agent with the command and control system."""
        if not self.connector or not hasattr(self.connector, "get_command_control_service"):
            log.debug("Command and control service not available, skipping registration")
            return
        
        command_control = self.connector.get_command_control_service()
        if not command_control:
            log.debug("Command and control service not enabled, skipping registration")
            return
        
        # Create a unique entity ID for this agent
        entity_id = f"agent_{self.info['agent_name']}"
        
        # Register with the command control service
        success = command_control.register_entity(
            entity_id=entity_id,
            entity_type="agent",
            entity_name=self.info["agent_name"],
            description=self.info.get("description", ""),
            version="1.0.0",
            parent_entity_id=self.flow_name,
            endpoints=self._get_command_control_endpoints(),
            status_attributes=self._get_command_control_status_attributes(),
            metrics=self._get_command_control_metrics(),
            configuration=self._get_command_control_configuration(),
        )
        
        if success:
            log.info(f"Agent {self.info['agent_name']} registered with command and control system")
        else:
            log.warning(f"Failed to register agent {self.info['agent_name']} with command and control system")
    
    def _get_command_control_endpoints(self) -> List[Dict[str, Any]]:
        """Get the endpoints for the command and control system.
        
        Returns:
            A list of endpoint definitions.
        """
        endpoints = [
            # Agent information endpoint
            {
                "path": f"/agents/{self.info['agent_name']}",
                "methods": {
                    "GET": {
                        "description": "Get agent information",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "agent_name": {"type": "string"},
                                "description": {"type": "string"},
                                "always_open": {"type": "boolean"},
                                "actions": {"type": "array"}
                            }
                        },
                        "handler": self._handle_get_agent_info
                    },
                    "PUT": {
                        "description": "Update agent configuration",
                        "path_params": {},
                        "query_params": {},
                        "request_body_schema": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "always_open": {"type": "boolean"}
                            }
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean"},
                                "message": {"type": "string"}
                            }
                        },
                        "handler": self._handle_update_agent_config
                    },
                    "PATCH": {
                        "description": "Update specific agent configuration fields",
                        "path_params": {},
                        "query_params": {},
                        "request_body_schema": {
                            "type": "object",
                            "additionalProperties": True
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean"},
                                "message": {"type": "string"},
                                "updated_fields": {"type": "array", "items": {"type": "string"}}
                            }
                        },
                        "handler": self._handle_patch_agent_config
                    }
                }
            },
            # Agent actions list endpoint
            {
                "path": f"/agents/{self.info['agent_name']}/actions",
                "methods": {
                    "GET": {
                        "description": "Get list of agent actions",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "description": {"type": "string"}
                                }
                            }
                        },
                        "handler": self._handle_get_agent_actions
                    }
                }
            },
            # Agent statistics endpoint
            {
                "path": f"/agents/{self.info['agent_name']}/stats",
                "methods": {
                    "GET": {
                        "description": "Get agent action statistics",
                        "path_params": {},
                        "query_params": {
                            "action_name": {
                                "type": "string",
                                "description": "Filter stats by action name",
                                "required": False
                            }
                        },
                        "response_schema": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "properties": {
                                    "total_invocations": {"type": "integer"},
                                    "successful_invocations": {"type": "integer"},
                                    "failed_invocations": {"type": "integer"},
                                    "average_execution_time_ms": {"type": "number"},
                                    "last_execution_time_ms": {"type": "integer"},
                                    "last_error": {"type": "string"},
                                    "last_invoked_at": {"type": "number"}
                                }
                            }
                        },
                        "handler": self._handle_get_action_stats
                    }
                }
            },
            # Agent configuration endpoint
            {
                "path": f"/agents/{self.info['agent_name']}/config",
                "methods": {
                    "GET": {
                        "description": "Get agent configuration",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "agent": {"type": "object"},
                                "component": {"type": "object"}
                            }
                        },
                        "handler": self._handle_get_agent_config
                    },
                    "PUT": {
                        "description": "Update agent configuration",
                        "path_params": {},
                        "query_params": {},
                        "request_body_schema": {
                            "type": "object",
                            "additionalProperties": True
                        },
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean"},
                                "message": {"type": "string"}
                            }
                        },
                        "handler": self._handle_update_full_agent_config
                    }
                }
            }
        ]
        
        # Add endpoints for each action
        for action in self.action_list.actions:
            action_name = action.name
            endpoints.append({
                "path": f"/agents/{self.info['agent_name']}/actions/{action_name}",
                "methods": {
                    "GET": {
                        "description": f"Get information about the {action_name} action",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "params": {"type": "array"},
                                "examples": {"type": "array"}
                            }
                        },
                        "handler": lambda path_params=None, query_params=None, body=None, context=None, 
                                         action_name=action_name: self._handle_get_action_info(
                                             path_params, query_params, body, context, action_name)
                    }
                }
            })
            
            # Add stats endpoint for each action
            endpoints.append({
                "path": f"/agents/{self.info['agent_name']}/actions/{action_name}/stats",
                "methods": {
                    "GET": {
                        "description": f"Get statistics for the {action_name} action",
                        "path_params": {},
                        "query_params": {},
                        "response_schema": {
                            "type": "object",
                            "properties": {
                                "total_invocations": {"type": "integer"},
                                "successful_invocations": {"type": "integer"},
                                "failed_invocations": {"type": "integer"},
                                "average_execution_time_ms": {"type": "number"},
                                "last_execution_time_ms": {"type": "integer"},
                                "last_error": {"type": "string"},
                                "last_invoked_at": {"type": "number"}
                            }
                        },
                        "handler": lambda path_params=None, query_params=None, body=None, context=None, 
                                         action_name=action_name: self._handle_get_action_stats_by_name(
                                             path_params, query_params, body, context, action_name)
                    }
                }
            })
        
        return endpoints
    
    def _get_command_control_status_attributes(self) -> List[Dict[str, Any]]:
        """Get the status attributes for the command and control system.
        
        Returns:
            A list of status attribute definitions.
        """
        return [
            {
                "name": "state",
                "description": "Current operational state of the agent",
                "type": "string",
                "possible_values": ["running", "stopped", "error"]
            },
            {
                "name": "action_count",
                "description": "Number of actions supported by the agent",
                "type": "integer"
            }
        ]
    
    def _get_command_control_metrics(self) -> List[Dict[str, Any]]:
        """Get the metrics for the command and control system.
        
        Returns:
            A list of metric definitions.
        """
        return [
            {
                "name": "total_action_invocations",
                "description": "Total number of action invocations",
                "type": "counter",
                "unit": "invocations"
            },
            {
                "name": "successful_action_invocations",
                "description": "Number of successful action invocations",
                "type": "counter",
                "unit": "invocations"
            },
            {
                "name": "failed_action_invocations",
                "description": "Number of failed action invocations",
                "type": "counter",
                "unit": "invocations"
            },
            {
                "name": "average_action_execution_time",
                "description": "Average execution time for actions",
                "type": "gauge",
                "unit": "milliseconds"
            }
        ]
    
    def _get_command_control_configuration(self) -> Dict[str, Any]:
        """Get the configuration for the command and control system.
        
        Returns:
            The configuration definition.
        """
        # Filter out sensitive information
        filtered_config = {}
        for key, value in self.component_config.items():
            # Skip passwords, keys, tokens, etc.
            if not any(
                sensitive in key.lower()
                for sensitive in ["password", "secret", "key", "token"]
            ):
                filtered_config[key] = value
        
        # Add agent-specific configuration
        agent_config = {
            "agent_name": self.info["agent_name"],
            "description": self.info.get("description", ""),
            "always_open": self.info.get("always_open", False)
        }
        
        # Add any additional configuration from the agent_info
        for key, value in self.info.items():
            if key not in ["agent_name", "description", "always_open"]:
                # Skip internal or complex objects
                if not key.startswith("_") and not callable(value) and not isinstance(value, (dict, list)):
                    agent_config[key] = value
        
        # Build mutable paths dynamically based on agent_config keys
        mutable_paths = ["agent.description", "agent.always_open"]
        for key in agent_config:
            if key not in ["agent_name"]:  # Don't allow changing the agent name
                mutable_paths.append(f"agent.{key}")
        
        # Build schema properties dynamically based on agent_config keys
        schema_properties = {
            "description": {"type": "string"},
            "always_open": {"type": "boolean"}
        }
        
        for key, value in agent_config.items():
            if key not in ["agent_name", "description", "always_open"]:
                # Determine the type for the schema
                if isinstance(value, bool):
                    schema_properties[key] = {"type": "boolean"}
                elif isinstance(value, int):
                    schema_properties[key] = {"type": "integer"}
                elif isinstance(value, float):
                    schema_properties[key] = {"type": "number"}
                else:
                    schema_properties[key] = {"type": "string"}
        
        return {
            "current_config": {
                "component": filtered_config,
                "agent": agent_config
            },
            "mutable_paths": mutable_paths,
            "config_schema": {
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "object",
                        "properties": schema_properties
                    }
                }
            }
        }
    
    def _handle_get_agent_info(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for agent information.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Agent information.
        """
        return self.get_agent_summary()
    
    def _handle_update_agent_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request to update agent configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Result of the update operation.
        """
        if not body:
            return {"success": False, "message": "No configuration provided"}
        
        updated = False
        
        if "description" in body:
            self.info["description"] = body["description"]
            updated = True
        
        if "always_open" in body:
            self.info["always_open"] = bool(body["always_open"])
            updated = True
        
        return {
            "success": updated,
            "message": "Configuration updated" if updated else "No changes made"
        }
    
    def _handle_patch_agent_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request to patch agent configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Result of the patch operation.
        """
        if not body:
            return {"success": False, "message": "No configuration provided", "updated_fields": []}
        
        updated_fields = []
        
        for key, value in body.items():
            if key in self.info:
                # Handle type conversion for boolean values
                if isinstance(self.info[key], bool) and not isinstance(value, bool):
                    if value.lower()in ["true", "yes", "1"]:
                        value = True
                    elif value.lower() in ["false", "no", "0"]:
                        value = False
                
                # Handle type conversion for numeric values
                if isinstance(self.info[key], int) and not isinstance(value, int):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        continue
                
                if isinstance(self.info[key], float) and not isinstance(value, float):
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        continue
                
                self.info[key] = value
                updated_fields.append(key)
        
        return {
            "success": len(updated_fields) > 0,
            "message": f"Updated {len(updated_fields)} fields" if updated_fields else "No changes made",
            "updated_fields": updated_fields
        }
    
    def _handle_get_agent_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for agent configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Agent configuration.
        """
        config = self._get_command_control_configuration()
        return config["current_config"]
    
    def _handle_update_full_agent_config(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request to update the full agent configuration.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Result of the update operation.
        """
        if not body:
            return {"success": False, "message": "No configuration provided"}
        
        updated = False
        
        # Update agent configuration
        if "agent" in body and isinstance(body["agent"], dict):
            for key, value in body["agent"].items():
                if key != "agent_name":  # Don't allow changing the agent name
                    if key in self.info:
                        # Handle type conversion
                        if isinstance(self.info[key], bool) and not isinstance(value, bool):
                            if value.lower() in ["true", "yes", "1"]:
                                value = True
                            elif value.lower() in ["false", "no", "0"]:
                                value = False
                        
                        if isinstance(self.info[key], int) and not isinstance(value, int):
                            try:
                                value = int(value)
                            except (ValueError, TypeError):
                                continue
                        
                        if isinstance(self.info[key], float) and not isinstance(value, float):
                            try:
                                value = float(value)
                            except (ValueError, TypeError):
                                continue
                        
                        self.info[key] = value
                        updated = True
        
        # Update component configuration (limited to non-sensitive fields)
        if "component" in body and isinstance(body["component"], dict):
            for key, value in body["component"].items():
                # Skip sensitive fields
                if not any(sensitive in key.lower() for sensitive in ["password", "secret", "key", "token"]):
                    self.component_config[key] = value
                    updated = True
        
        return {
            "success": updated,
            "message": "Configuration updated" if updated else "No changes made"
        }
    
    def _handle_get_agent_actions(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for agent actions.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            List of agent actions.
        """
        actions = []
        for action in self.action_list.actions:
            actions.append({
                "name": action.name,
                "description": action.long_description
            })
        return actions
    
    def _handle_get_action_info(self, path_params=None, query_params=None, body=None, context=None, action_name=None):
        """Handle a request for action information.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            action_name: The name of the action.
            
        Returns:
            Action information.
        """
        action = self.action_list.get_action(action_name)
        if not action:
            return {"error": f"Action {action_name} not found"}
        
        return {
            "name": action_name,
            "description": action.long_description,
            "params": action._params,
            "examples": action._examples
        }
    
    def _handle_get_action_stats(self, path_params=None, query_params=None, body=None, context=None):
        """Handle a request for action statistics.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            
        Returns:
            Action statistics.
        """
        action_name = query_params.get("action_name") if query_params else None
        
        if action_name:
            if action_name in self.action_stats:
                return {action_name: self.action_stats[action_name]}
            return {"error": f"Action {action_name} not found"}
        
        return self.action_stats
    
    def _handle_get_action_stats_by_name(self, path_params=None, query_params=None, body=None, context=None, action_name=None):
        """Handle a request for statistics for a specific action.
        
        Args:
            path_params: Path parameters from the request.
            query_params: Query parameters from the request.
            body: Request body.
            context: Request context.
            action_name: The name of the action.
            
        Returns:
            Statistics for the specified action.
        """
        if action_name in self.action_stats:
            return self.action_stats[action_name]
        return {"error": f"Action {action_name} not found"}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for the component.
        
        Returns:
            A dictionary of metrics.
        """
        metrics = super().get_metrics()
        
        # Calculate aggregate metrics
        total_invocations = 0
        successful_invocations = 0
        failed_invocations = 0
        total_execution_time = 0
        action_count = 0
        
        for action_name, stats in self.action_stats.items():
            total_invocations += stats["total_invocations"]
            successful_invocations += stats["successful_invocations"]
            failed_invocations += stats["failed_invocations"]
            total_execution_time += stats["average_execution_time_ms"] * stats["total_invocations"]
            action_count += 1
        
        # Add agent-specific metrics
        metrics["total_action_invocations"] = total_invocations
        metrics["successful_action_invocations"] = successful_invocations
        metrics["failed_action_invocations"] = failed_invocations
        
        if total_invocations > 0:
            metrics["average_action_execution_time"] = total_execution_time / total_invocations
        else:
            metrics["average_action_execution_time"] = 0
        
        metrics["action_count"] = action_count
        
        return metrics
