"""This is the component that handles processing all action responses from agents"""

import os
from time import time

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType
from ...orchestrator.orchestrator_main import OrchestratorState, ORCHESTRATOR_HISTORY_IDENTIFIER, ORCHESTRATOR_HISTORY_CONFIG
from ...orchestrator.orchestrator_prompt import BasicRagPrompt, ContextQueryPrompt
from ...services.history_service import HistoryService
from ..action_manager import ActionManager
from ...common.constants import ORCHESTRATOR_COMPONENT_NAME
from time import sleep

info = {
    "class_name": "OrchestratorActionResponseComponent",
    "description": ("This component handles all action responses from agents"),
    "config_parameters": [],
    "input_schema": {
        # A action response object - it doesn't have a fixed schema
        "type": "object",
        "additionalProperties": True,
    },
    # We will output a list of topics and messages to send to either the
    # orchestrator stimulus or to the originator via slack
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


class OrchestratorActionResponseComponent(ComponentBase):
    """This is the component that handles processing all action responses from agents"""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        with self.get_lock("orchestrator_state"):
            self.orchestrator_state = self.kv_store_get("orchestrator_state")
            if not self.orchestrator_state:
                self.orchestrator_state = OrchestratorState()
                self.kv_store_set("orchestrator_state", self.orchestrator_state)

        self.action_manager = ActionManager(self.flow_kv_store, self.flow_lock_manager)
        self.history = HistoryService(
            ORCHESTRATOR_HISTORY_CONFIG, identifier=ORCHESTRATOR_HISTORY_IDENTIFIER
        )
        self.stream_to_flow = self.get_config("stream_to_flow")

    def invoke(self, message: Message, data):
        """Handle action responses from agents"""

        user_properties = message.get_user_properties()
        user_properties['timestamp_start'] = time()
        message.set_user_properties(user_properties)

        if not data:
            log.error("No data received from agent")
            self.discard_current_message()
            return None

        if not isinstance(data, dict):
            log.error("Data received from agent is not a dictionary")
            self.discard_current_message()
            return None

        session_id = data.get("session_id")
        user_response = {}

        if data.get("message"):
            user_response["text"] = data.get("message")

        user_response["files"] = []
        if data.get("files"):
            user_response["files"] = data.get("files")

        if data.get("clear_history"):
            user_properties = message.get_user_properties()
            keep_depth = data.get("history_depth_to_keep")
            if type(keep_depth) != int:
                if keep_depth.isdigit():
                    keep_depth = int(keep_depth)
                else:
                    keep_depth = 0
            user_properties["clear_gateway_history"] = [True, keep_depth]
            message.set_user_properties(user_properties)

        if data.get("error_info"):
            if self.error_queue is not None:
                error_info = data.get("error_info", {})
                action_name = data.get("action_name")
                action_list_id = data.get("action_list_id")
                action_idx = data.get("action_idx")
                action = (
                    self.action_manager.get_action_info(
                        action_list_id, action_name, action_idx
                    )
                    or {}
                )
                agent_name = action.get("agent_name", "Unknown")

                source = ""
                if agent_name == "global" and action_name == "error_action":
                    source = "Error raised by the Orchestrator"
                else:
                    source = f"Agent: {agent_name}, Action: {action_name}, Params: {action.get('action_params', {})}"

                self.error_queue.put(
                    Event(
                        EventType.MESSAGE,
                        Message(
                            payload={
                                "error_message": error_info.get("error_message"),
                                "source": source,
                            },
                            user_properties=message.get_user_properties()
                            if message
                            else {},
                        ),
                    )
                )

        if data.get("agent_state_change"):
            agent_state_change = data.get("agent_state_change")
            agent_name = agent_state_change.get("agent_name")
            state = agent_state_change.get("new_state")
            self.orchestrator_state.update_agent_state(agent_name, state, session_id)
            if state == "open":
                user_response["text"] = (
                    f"Opened {agent_name}. Now you can interact with it."
                )

        if data.get("context_query"):
            cq = data.get("context_query")
            query = cq.get("query")
            context = cq.get("context")
            context_type = cq.get("context_type")
            if context_type == "raw":
                user_response["text"] = query
            else:
                user_response["text"] = ContextQueryPrompt(query=query, context=context)

        events = []

        # Tell the ActionManager about the result - if it is complete, then
        # it will send the result back to the model
        action_list = self.action_manager.add_action_response(data, user_response)
        if action_list and action_list.is_complete():
            # Check if there are any async responses
            async_responses = []
            for action in action_list.get_responses():
                if action.get("response", {}).get("is_async"):
                    async_responses.append(action)
            
            if async_responses:
                # There are async responses, create a task group
                # Get the history for this stimulus_uuid
                stimulus_uuid = message.get_user_properties().get("stimulus_uuid")
                session_id = message.get_user_properties().get("session_id")
                gateway_id = message.get_user_properties().get("gateway_id")
                
                # Get history from history service
                stimulus_state = self.history.get_history(stimulus_uuid) if self.history else []
                # Send a status update message to the user
                events.append({
                    "payload": {
                        "status_update": True,
                        "streaming": True,
                        "text": "Request suspended. Waiting for user input.",
                    },
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/streamingResponse/orchestrator/{gateway_id}",
                })

                # Create event to send to async service
                events.append({
                    "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/async-service/create-task-group/{stimulus_uuid}",
                    "payload": {
                        "event_type": "create_task_group",
                        "stimulus_uuid": stimulus_uuid,
                        "session_id": session_id,
                        "gateway_id": gateway_id,
                        "stimulus_state": stimulus_state,
                        "agent_responses": action_list.get_responses(),
                        "async_responses": async_responses,
                    },
                })
                                
                log.info(f"Created task group for stimulus {stimulus_uuid} with {len(async_responses)} async responses")
            else:
                # No async responses, proceed as normal
                response_text, files = action_list.format_ai_response()
                
                if response_text:
                    # Send the result back to the model
                    user_properties = message.get_user_properties()
                    events.append({
                        "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/orchestrator/reinvokeModel",
                        "payload": {
                            "text": response_text,
                            "files": files,
                            "identity": user_properties.get("identity"),
                            "channel": user_properties.get("channel"),
                            "thread_ts": user_properties.get("thread_ts"),
                            "action_response_reinvoke": True,
                        },
                    })
            
            self.action_manager.delete_action_request(action_list.action_list_id)

        if len(events) == 0:
            self.discard_current_message()
            return None

        user_properties = message.get_user_properties()
        user_properties['timestamp_end'] = time()
        message.set_user_properties(user_properties)

        return events
        
    # def handle_async_response(self, message: Message, data):
    #     """Handle async responses from the async service"""
        
    #     if not data:
    #         log.error("No data received from async service")
    #         self.discard_current_message()
    #         return None
            
    #     stimulus_uuid = data.get("stimulus_uuid")
    #     session_id = data.get("session_id")
    #     gateway_id = data.get("gateway_id")
    #     user_responses = data.get("user_responses", {})
    #     agent_responses = data.get("agent_responses", [])  # Get all agent responses
    #     stimulus_state = data.get("stimulus_state", [])    # Get stimulus state for history
    #     timed_out = data.get("timed_out", False)
        
    #     if not stimulus_uuid or not session_id:
    #         log.error("Missing required fields for async_response")
    #         self.discard_current_message()
    #         return None
        
    #     # Restore conversation history if available
    #     if stimulus_state and self.history:
    #         # Clear existing history for this stimulus_uuid
    #         self.history.clear_history(stimulus_uuid)
            
    #         # Restore history from stimulus state
    #         for entry in stimulus_state:
    #             role = entry.get("role")
    #             content = entry.get("content")
    #             if role and content:
    #                 self.history.store_history(stimulus_uuid, role, content)
            
    #         log.info(f"Restored conversation history for stimulus {stimulus_uuid}")
        
    #     # Process user responses and create a response to send back to the model
    #     response_text = "User responses received:\n\n"
        
    #     # Prepare all actions for the action manager
    #     all_actions = []
        
    #     # Process all agent responses
    #     for i, agent_response in enumerate(agent_responses):
    #         action_name = agent_response.get("action_name")
    #         action_params = agent_response.get("action_params")
    #         agent_name = agent_response.get("agent_name")
            
    #         # Add this action to the list of all actions
    #         all_actions.append({
    #             "agent_name": agent_name,
    #             "action_name": action_name,
    #             "action_params": action_params,
    #             "action_idx": i,
    #             "originator": ORCHESTRATOR_COMPONENT_NAME,  # Use the imported constant
    #         })
            
    #         # Check if this agent response has a corresponding user response
    #         task_id = agent_response.get("task_id")
    #         if task_id in user_responses:
    #             user_response = user_responses[task_id].get("user_response")
    #             response_text += f"Action {action_name} with params {action_params} received user response: {user_response}\n\n"
    #         else:
    #             response_text += f"Action {action_name} with params {action_params} did not require user input\n\n"
        
    #     # Add all actions to the action manager
    #     action_list_id = None
    #     if all_actions:
    #         # Add all actions to the action manager
    #         self.action_manager.add_action_request(all_actions, message.get_user_properties())
            
    #         # Get the action_list_id from the first action (they all have the same ID)
    #         action_list_id = all_actions[0].get("action_list_id")
            
    #         log.info(f"Added {len(all_actions)} actions to the action manager with action_list_id {action_list_id}")
            
    #         # For actions that didn't require user input, add responses to mark them as completed
    #         for i, agent_response in enumerate(agent_responses):
    #             task_id = agent_response.get("task_id")
    #             if task_id not in user_responses:
    #                 # This action didn't require user input, so mark it as completed
    #                 action_response_obj = {
    #                     "action_name": agent_response.get("action_name"),
    #                     "action_params": agent_response.get("action_params"),
    #                     "action_idx": i,
    #                     "action_list_id": action_list_id,
    #                     "originator": ORCHESTRATOR_COMPONENT_NAME,
    #                 }
                    
    #                 # Get the response from the agent_response
    #                 response_text_and_files = {
    #                     "text": agent_response.get("response", {}).get("text", ""),
    #                     "files": agent_response.get("response", {}).get("files", []),
    #                 }
                    
    #                 # Add the response to the action manager
    #                 self.action_manager.add_action_response(action_response_obj, response_text_and_files)
                    
    #                 log.info(f"Marked action {i} as completed")
        
    #     # Re-send action requests for actions that required user feedback
    #     action_events = []
    #     for task_id, response_data in user_responses.items():
    #         user_response = response_data.get("user_response")
    #         action_name = response_data.get("action_name")
    #         action_params = response_data.get("action_params")
    #         agent_name = response_data.get("agent_name")
            
    #         # Get the original user properties from the message
    #         original_user_properties = message.get_user_properties() or {}
            
    #         # Create a copy of the original user properties and add the user_responses
    #         event_user_properties = original_user_properties.copy()
    #         event_user_properties["user_responses"] = [user_response]
            
    #         # Create an event to re-send the action request
    #         action_events.append({
    #             "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/actionRequest/orchestrator/agent/{agent_name}/{action_name}",
    #             "payload": {
    #                 "agent_name": agent_name,
    #                 "action_name": action_name,
    #                 "action_params": action_params,
    #                 "originator": ORCHESTRATOR_COMPONENT_NAME,
    #             },
    #             "user_properties": event_user_properties,
    #         })
            
    #         response_text += f"Re-sending action request for {action_name} with user response: {user_response}\n\n"
        
    #     if timed_out:
    #         response_text += "\nSome tasks timed out and did not receive a response."
        
    #     return action_events
