"""This is the component that handles async responses from the async service"""

import os
from time import time

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from ...orchestrator.orchestrator_main import OrchestratorState, ORCHESTRATOR_HISTORY_IDENTIFIER, ORCHESTRATOR_HISTORY_CONFIG
from ...services.history_service import HistoryService
from ..action_manager import ActionManager
from ...common.constants import ORCHESTRATOR_COMPONENT_NAME

info = {
    "class_name": "OrchestratorAsyncResponseComponent",
    "description": ("This component handles async responses from the async service"),
    "config_parameters": [],
    "input_schema": {
        # An async response object - it doesn't have a fixed schema
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


class OrchestratorAsyncResponseComponent(ComponentBase):
    """This is the component that handles async responses from the async service"""

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

    def invoke(self, message: Message, data):
        """Handle async responses from the async service"""
        
        user_properties = message.get_user_properties()
        user_properties['timestamp_start'] = time()
        message.set_user_properties(user_properties)

        if not data:
            log.error("No data received from async service")
            self.discard_current_message()
            return None
            
        stimulus_uuid = data.get("stimulus_uuid")
        session_id = data.get("session_id")
        gateway_id = data.get("gateway_id")
        user_responses = data.get("user_responses", {})
        agent_responses = data.get("agent_responses", [])  # Get all agent responses
        stimulus_state = data.get("stimulus_state", [])    # Get stimulus state for history
        timed_out = data.get("timed_out", False)
        
        if not stimulus_uuid or not session_id:
            log.error("Missing required fields for async_response")
            self.discard_current_message()
            return None
        
        # Restore conversation history if available
        if stimulus_state and self.history:
            # Clear existing history for this stimulus_uuid
            self.history.clear_history(stimulus_uuid)
            
            # Restore history from stimulus state
            for entry in stimulus_state:
                role = entry.get("role")
                content = entry.get("content")
                if role and content:
                    self.history.store_history(stimulus_uuid, role, content)
            
            log.info(f"Restored conversation history for stimulus {stimulus_uuid}")
        
        # Process user responses and create a response to send back to the model
        response_text = "User responses received:\n\n"
        
        # Create a set of action_idx values that have corresponding user responses
        user_response_action_indices = set()
        for task_id, response_data in user_responses.items():
            action_idx = response_data.get("action_idx")
            if action_idx is not None:
                user_response_action_indices.add(action_idx)
        
        # Prepare all actions for the action manager
        all_actions = []
        
        # Process all agent responses
        for i, agent_response in enumerate(agent_responses):
            action_name = agent_response.get("action_name")
            action_params = agent_response.get("action_params")
            agent_name = agent_response.get("agent_name")
            
            # Add all actions to the list
            all_actions.append({
                "agent_name": agent_name,
                "action_name": action_name,
                "action_params": action_params,
                "action_idx": i,
                "originator": ORCHESTRATOR_COMPONENT_NAME,  # Use the imported constant
            })
            
            # Check if this agent response has a corresponding user response
            if i in user_response_action_indices:
                # Find the task_id for this action_idx
                for task_id, response_data in user_responses.items():
                    if response_data.get("action_idx") == i:
                        user_response = response_data.get("user_response")
                        response_text += f"Action {action_name} with params {action_params} received user response: {user_response}\n\n"
                        break
            else:
                response_text += f"Action {action_name} with params {action_params} did not require user input\n\n"
        
        # Add all actions to the action manager
        action_list_id = None
        if all_actions:
            # Add all actions to the action manager
            self.action_manager.add_action_request(all_actions, message.get_user_properties())
            
            # Get the action_list_id from the first action (they all have the same ID)
            action_list_id = all_actions[0].get("action_list_id")
            
            log.info(f"Added {len(all_actions)} actions to the action manager with action_list_id {action_list_id}")
            
            # For actions that didn't require user input, add responses to mark them as completed
            for i, agent_response in enumerate(agent_responses):
                if i not in user_response_action_indices:
                    # This action didn't require user input, so mark it as completed
                    action_response_obj = {
                        "action_name": agent_response.get("action_name"),
                        "action_params": agent_response.get("action_params"),
                        "action_idx": i,
                        "action_list_id": action_list_id,
                        "originator": ORCHESTRATOR_COMPONENT_NAME,
                    }
                    
                    # Get the response from the agent_response
                    response_text_and_files = {
                        "text": agent_response.get("response", {}).get("text", ""),
                        "files": agent_response.get("response", {}).get("files", []),
                    }
                    
                    # Add the response to the action manager
                    self.action_manager.add_action_response(action_response_obj, response_text_and_files)
                    
                    log.info(f"Marked action {i} as completed")
        
        # Re-send action requests for actions that required user feedback
        action_events = []
        for task_id, response_data in user_responses.items():
            user_response = response_data.get("user_response")
            action_name = response_data.get("action_name")
            action_params = response_data.get("action_params")
            agent_name = response_data.get("agent_name")
            action_idx = response_data.get("action_idx")
            
            # Get the original user properties from the message
            original_user_properties = message.get_user_properties() or {}
            
            # Create a copy of the original user properties and add the user_responses
            event_user_properties = original_user_properties.copy()
            event_user_properties["user_responses"] = [user_response]
            
            # Create an event to re-send the action request
            action_events.append({
                "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/actionRequest/orchestrator/agent/{agent_name}/{action_name}",
                "payload": {
                    "agent_name": agent_name,
                    "action_name": action_name,
                    "action_params": action_params,
                    "action_list_id": action_list_id,
                    "action_idx": action_idx,
                    "originator": ORCHESTRATOR_COMPONENT_NAME,
                },
                "user_properties": event_user_properties,
            })
            
            response_text += f"Re-sending action request for {action_name} with user response: {user_response}\n\n"
        
        if timed_out:
            response_text += "\nSome tasks timed out and did not receive a response."
        
        # Send the result back to the model
        user_properties = message.get_user_properties()
        user_properties['timestamp_end'] = time()
        message.set_user_properties(user_properties)
        
        return action_events