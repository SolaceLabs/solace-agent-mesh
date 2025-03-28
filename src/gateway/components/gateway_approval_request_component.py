"""This component handles approval requests from the AsyncService."""

import os
import json
from uuid import uuid4

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

from ...common.form_utils import rjfs_to_slack_blocks
from .gateway_base import GatewayBase

info = {
    "class_name": "GatewayApprovalRequestComponent",
    "description": ("This component handles approval requests from the AsyncService"),
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
            "task_id": {"type": "string"},
            "approval_id": {"type": "string"},
            "form_schema": {"type": "object"},
            "approval_data": {"type": "object"},
            "originator": {"type": "string"},
        },
        "required": ["task_id", "approval_id", "form_schema", "approval_data", "originator"],
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


class GatewayApprovalRequestComponent(GatewayBase):
    """This component handles approval requests from the AsyncService."""

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)

    def invoke(self, message: Message, data):
        """Handle approval requests from the AsyncService."""
        if not data:
            log.error("No data received")
            self.discard_current_message()
            return None

        if not isinstance(data, dict):
            log.error("Data received is not a dictionary")
            self.discard_current_message()
            return None

        task_id = data.get("task_id")
        approval_id = data.get("approval_id")
        form_schema = data.get("form_schema")
        approval_data = data.get("approval_data")
        originator = data.get("originator")

        if not task_id or not approval_id or not form_schema or not approval_data or not originator:
            log.error("Missing required fields in approval request")
            self.discard_current_message()
            return None

        # Convert RJFS form to Slack blocks
        try:
            blocks = rjfs_to_slack_blocks(form_schema, approval_data)
        except Exception as e:
            log.error(f"Error converting form to Slack blocks: {e}")
            # Create a simplified form with just approve/reject buttons
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Approval Request",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "An approval is required for a task. Please approve or reject."
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "actions",
                    "block_id": "approval_actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Approve",
                                "emoji": True
                            },
                            "style": "primary",
                            "value": "approve",
                            "action_id": "approve_button"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Reject",
                                "emoji": True
                            },
                            "style": "danger",
                            "value": "reject",
                            "action_id": "reject_button"
                        }
                    ]
                }
            ]

        # Add metadata to the blocks for the Slack interface
        metadata = {
            "task_id": task_id,
            "approval_id": approval_id,
            "originator": originator
        }

        # Forward the approval request to the Slack interface
        user_properties = message.get_user_properties() or {}
        
        return {
            "topic": f"{os.getenv('SOLACE_AGENT_MESH_NAMESPACE')}solace-agent-mesh/v1/interface/slack/approval",
            "payload": {
                "blocks": blocks,
                "metadata": metadata,
                "identity": originator,
                "channel": user_properties.get("channel"),
                "thread_ts": user_properties.get("thread_ts"),
                "gateway_id": self.gateway_id
            }
        }