"""
Custom Solace AI Connector App class for the Slack Gateway.
"""

import logging
from typing import Any, Dict, List, Type

from ..base.component import BaseGatewayComponent
from ..generic.app import GenericGatewayApp

log = logging.getLogger(__name__)

info = {
    "class_name": "SlackGatewayApp",
    "description": "Custom App class for the A2A Slack Gateway, using the Generic Adapter Framework.",
}


class SlackGatewayApp(GenericGatewayApp):
    """
    Custom App class for the A2A Slack Gateway.
    - Extends GenericGatewayApp to use the adapter pattern.
    - Defines Slack-specific configuration parameters.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        # This points to the new adapter implementation
        {
            "name": "gateway_adapter",
            "required": False,
            "type": "string",
            "default": "solace_agent_mesh.gateway.slack.adapter.SlackAdapter",
            "description": "The Python module path to the Slack GatewayAdapter implementation.",
        },
        # All slack-specific configs go into the adapter_config block
        {
            "name": "adapter_config",
            "required": True,
            "type": "object",
            "description": "Configuration settings specific to the Slack adapter.",
            "dict_schema": {
                "slack_bot_token": {
                    "name": "slack_bot_token",
                    "required": True,
                    "type": "string",
                    "description": "Slack Bot Token (xoxb-...). Should use ${ENV_VAR}.",
                },
                "slack_app_token": {
                    "name": "slack_app_token",
                    "required": True,
                    "type": "string",
                    "description": "Slack App Token (xapp-...) for Socket Mode. Should use ${ENV_VAR}.",
                },
                "default_agent_name": {
                    "name": "default_agent_name",
                    "required": False,
                    "type": "string",
                    "default": None,
                    "description": "Default agent to route messages to if not specified via mention.",
                },
                "slack_initial_status_message": {
                    "name": "slack_initial_status_message",
                    "required": False,
                    "type": "string",
                    "default": "Got it, thinking...",
                    "description": "Message posted to Slack upon receiving a user request (set empty to disable).",
                },
                "correct_markdown_formatting": {
                    "name": "correct_markdown_formatting",
                    "required": False,
                    "type": "boolean",
                    "default": True,
                    "description": "Attempt to convert common Markdown (e.g., links) to Slack's format.",
                },
                "feedback_enabled": {
                    "name": "feedback_enabled",
                    "required": False,
                    "type": "boolean",
                    "default": False,
                    "description": "Enable thumbs up/down feedback buttons on final Slack messages.",
                },
                "slack_email_cache_ttl_seconds": {
                    "name": "slack_email_cache_ttl_seconds",
                    "required": False,
                    "type": "integer",
                    "default": 3600,  # Default to 1 hour
                    "description": "TTL in seconds for caching Slack user email addresses. Set to 0 to disable caching.",
                },
            },
        },
    ]

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the GenericGatewayComponent, which will host the Slack adapter.
        """
        from ..generic.component import GenericGatewayComponent

        return GenericGatewayComponent
