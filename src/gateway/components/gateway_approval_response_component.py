"""This component handles approval responses from the Slack interface."""

import os
import json
from uuid import uuid4

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

from ...common.form_utils import extract_form_data_from_slack_payload
from .gateway_base import GatewayBase

info = {
    "class_name": "GatewayApprovalResponseComponent",
    "description": ("This component handles approval responses from the Slack interface"),
    "config_parameters": [
        {
            "name": "gateway_config",
            "type": "object",
            "properties": {
                "gateway_id": {"type": "string"},
                "system_purpose": {"type": "string"},
            },
            "description": "Gateway configuration.",
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "payload": {"type": "object"},
            "metadata": {"type": "object"},
        },
        "required": ["payload", "metadata"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["topic", "payload"],
    },
}


class GatewayApprovalResponseComponent(GatewayBase):
    """This component handles approval responses from the Slack interface."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message: Message, data):
        """Handle approval responses from the Slack interface."""
        if not data:
            log.error("No data received")
            self.discard_current_message()
            return None

        if not isinstance(data, dict):
            log.error("Data received is not a dictionary")
            self.discard_current_message()
            return None

        payload = data.get("payload")
        metadata = data.get("metadata")

        if not payload or not metadata:
            log.error("Missing payload or metadata")
            self.discard_current_message()
            return None

        task_id = metadata.get("task_id")
        approval_id = metadata.get("approval_id")
        originator = metadata.get("originator")

        if not task_id or not approval_id or not originator:
            log.error("Missing task_id, approval_id, or originator in metadata")
            self.discard_current_message()
            return None

        # Extract form data from Slack payload
        try:
            form_data = extract_form_data_from_slack_payload(payload)
        except Exception as e:
            log.error(f"Error extracting form data from Slack payload: {e}")
            form_data = {}

        # Get the decision (approve/reject)
        decision = form_data.get("decision")
        if not decision:
            # Try to extract from the payload directly
            if payload.get("actions"):
                for action in payload.get("actions", []):
                    if action.get("action_id") in ["approve_button", "reject_button"]:
                        decision = action.get("value")
                        break

        if not decision:
            log.error("No decision found in payload")
            self.discard_current_message()
            return None

        # Forward the approval response to the AsyncService
        user_properties = message.get_user_properties() or {}
        
        return {
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/async/decision/submit",
            "payload": {
                "task_id": task_id,
                "approval_id": approval_id,
                "decision": decision,
                "form_data": form_data,
                "originator": originator,
                "gateway_id": self.gateway_id
            }
        }