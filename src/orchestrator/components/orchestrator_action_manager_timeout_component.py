"""This is a custom component that handles the action_manager timer going off"""

import os

from solace_ai_connector.components.component_base import ComponentBase

from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message
from ..action_manager import ActionManager

info = {
    "class_name": "OrchestratorActionManagerTimeoutComponent",
    "description": ("This component handles the action_manager timer going off"),
    "config_parameters": [],
    "input_schema": {
        "type": "none",
    },
}


class OrchestratorActionManagerTimeoutComponent(ComponentBase):

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.action_manager = ActionManager(self.flow_kv_store, self.flow_lock_manager)

    def invoke(self, message: Message, data):
        """Called when the timer goes off"""

        # Need to go through all the active action_requests and check if any of them have timed out
        timeout_events = self.action_manager.do_timeout_check()

        # Also check on agents
        orchestrator_state = self.kv_store_get("orchestrator_state")
        orchestrator_state.age_out_agents()

        # Now turn these into messages
        messages = []
        for event in timeout_events:
            action_name = event.get("action_name")
            if action_name is None:
                log.error("Action name not found in event")
                continue
            action_parts = action_name.split(".")
            if len(action_parts) == 1:
                action_parts.append(action_parts[0])
                action_parts[0] = "global"
            payload = event
            user_properties = event.get("user_properties")
            del payload["user_properties"]
            new_message = {
                "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/actionResponse/agent/{action_parts[0]}/{action_parts[1]}/timeout",
                "payload": payload,
                "user_properties": user_properties,
            }
            messages.append(new_message)

        return messages
