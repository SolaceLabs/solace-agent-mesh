"""This component handles resuming tasks after approval."""

import os
from time import time

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from ...orchestrator.orchestrator_main import OrchestratorState
from ..action_manager import ActionManager

info = {
    "class_name": "OrchestratorResumeComponent",
    "description": ("This component handles resuming tasks after approval"),
    "config_parameters": [],
    "input_schema": {
        # Resume data from AsyncService
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "stimulus_id": {"type": "string"},
            "session_state": {"type": "object"},
            "stimulus_state": {"type": "object"},
            "agent_list_state": {"type": "object"},
            "approval_decisions": {"type": "object"},
        },
        "required": ["task_id", "stimulus_id", "session_state", "stimulus_state", "agent_list_state"],
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


class OrchestratorResumeComponent(ComponentBase):
    """This component handles resuming tasks after approval."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        with self.get_lock("orchestrator_state"):
            self.orchestrator_state = self.kv_store_get("orchestrator_state")
            if not self.orchestrator_state:
                self.orchestrator_state = OrchestratorState()
                self.kv_store_set("orchestrator_state", self.orchestrator_state)

        self.action_manager = ActionManager(self.flow_kv_store, self.flow_lock_manager)

    def invoke(self, message: Message, data):
        """Handle resuming tasks after approval."""

        user_properties = message.get_user_properties()
        user_properties['timestamp_start'] = time()
        message.set_user_properties(user_properties)

        if not data:
            log.error("No data received")
            self.discard_current_message()
            return None

        if not isinstance(data, dict):
            log.error("Data received is not a dictionary")
            self.discard_current_message()
            return None

        task_id = data.get("task_id")
        stimulus_id = data.get("stimulus_id")
        session_state = data.get("session_state")
        stimulus_state = data.get("stimulus_state")
        agent_list_state = data.get("agent_list_state")
        approval_decisions = data.get("approval_decisions", {})

        if not task_id or not stimulus_id:
            log.error("Missing task_id or stimulus_id")
            self.discard_current_message()
            return None

        # Restore orchestrator state
        if session_state:
            self.orchestrator_state.set_session_state(stimulus_id, session_state)
        if stimulus_state:
            self.orchestrator_state.set_stimulus_state(stimulus_id, stimulus_state)
        if agent_list_state:
            self.orchestrator_state.set_agent_list_state(stimulus_id, agent_list_state)

        # Get the gateway_id from the user_properties
        gateway_id = user_properties.get("gateway_id")
        if not gateway_id:
            log.error("No gateway_id found in user_properties")
            self.discard_current_message()
            return None

        # Send status message to the user
        events = []
        events.append({
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/responseComplete/{gateway_id}",
            "payload": {
                "text": "Your request has been approved. Processing will continue.",
                "identity": user_properties.get("identity"),
                "channel": user_properties.get("channel"),
                "thread_ts": user_properties.get("thread_ts"),
            }
        })

        # Re-invoke the model with the approval decisions
        events.append({
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/stimulus/orchestrator/reinvokeModel",
            "payload": {
                "text": f"The user has approved your request. Here are the approval decisions: {approval_decisions}",
                "identity": user_properties.get("identity"),
                "channel": user_properties.get("channel"),
                "thread_ts": user_properties.get("thread_ts"),
                "approval_decisions": approval_decisions,
                "session_id": stimulus_id,
            }
        })

        user_properties = message.get_user_properties()
        user_properties['timestamp_end'] = time()
        message.set_user_properties(user_properties)

        return events