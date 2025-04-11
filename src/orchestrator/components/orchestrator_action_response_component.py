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
                        "response_suspended": True,
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
        
