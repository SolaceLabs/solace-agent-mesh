"""
Solace Agent Mesh - Event Mesh Gateway Plugin: App Definition
"""

from typing import Any, Dict, List, Type

from solace_ai_connector.common.log import log

from solace_agent_mesh.gateway.base.app import BaseGatewayApp
from solace_agent_mesh.gateway.base.component import (
    BaseGatewayComponent,
)

from .component import EventMeshGatewayComponent


info = {
    "class_name": "EventMeshGatewayApp",
    "description": "App class for the SAM Event Mesh Gateway.",
}


class EventMeshGatewayApp(BaseGatewayApp):
    """
    App class for the SAM Event Mesh Gateway.
    - Extends BaseGatewayApp for common gateway functionalities.
    - Defines Event Mesh Gateway-specific configuration parameters.
    """

    SPECIFIC_APP_SCHEMA_PARAMS: List[Dict[str, Any]] = [
        {
            "name": "event_mesh_broker_config",
            "required": True,
            "type": "object",
            "description": "Configuration for the data plane Solace client. Standard SAC broker parameters apply (broker_url, broker_vpn, etc.).",
            "additionalProperties": True,
        },
        {
            "name": "event_handlers",
            "required": True,
            "type": "list",
            "description": "List of event handlers defining how to process incoming Solace messages.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "required": True,
                        "description": "Unique name for the event handler.",
                    },
                    "subscriptions": {
                        "type": "list",
                        "required": True,
                        "description": "List of Solace topic subscription objects.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {
                                    "type": "string",
                                    "required": True,
                                    "description": "The Solace topic pattern to subscribe to.",
                                },
                                "qos": {
                                    "type": "integer",
                                    "required": False,
                                    "default": 1,
                                    "description": "Quality of Service for the subscription.",
                                },
                            },
                        },
                    },
                    "input_expression": {
                        "type": "string",
                        "required": True,
                        "description": "SAC template string to transform the incoming Solace message into the text part of an A2A task request.",
                    },
                    "payload_encoding": {
                        "type": "string",
                        "required": False,
                        "default": "utf-8",
                        "description": "Expected encoding of the incoming Solace message payload.",
                    },
                    "payload_format": {
                        "type": "string",
                        "required": False,
                        "default": "json",
                        "description": "Expected format of the incoming Solace message payload.",
                    },
                    "on_success": {
                        "type": "string",
                        "required": False,
                        "description": "Name of the output_handler to use for successful A2A task responses.",
                    },
                    "on_error": {
                        "type": "string",
                        "required": False,
                        "description": "Name of the output_handler to use for failed A2A tasks.",
                    },
                    "user_identity_expression": {
                        "type": "string",
                        "required": False,
                        "description": "SAC expression to extract a user identity from the incoming Solace message.",
                    },
                    "target_agent_name": {
                        "type": "string",
                        "required": False,
                        "description": "Static name of the target A2A agent.",
                    },
                    "target_agent_name_expression": {
                        "type": "string",
                        "required": False,
                        "description": "SAC expression to dynamically determine the target A2A agent name.",
                    },
                    "forward_context": {
                        "type": "object",
                        "required": False,
                        "default": {},
                        "description": "A dictionary of key-value pairs where values are SAC expressions to extract data from the incoming message for use in output handlers.",
                    },
                    "artifact_processing": {
                        "type": "object",
                        "required": False,
                        "description": "Defines how to create A2A artifacts from the incoming message.",
                        "properties": {
                            "extract_artifacts_expression": {
                                "type": "string",
                                "required": True,
                                "description": "SAC expression that resolves to a single item or a list of items to be processed as artifacts.",
                            },
                            "artifact_definition": {
                                "type": "object",
                                "required": True,
                                "description": "Defines how to extract data for each artifact.",
                                "properties": {
                                    "filename": {
                                        "type": "string",
                                        "required": True,
                                        "description": "Expression to get the artifact's filename. Use 'list_item:' to reference the current item in a list.",
                                    },
                                    "content": {
                                        "type": "string",
                                        "required": True,
                                        "description": "Expression to get the artifact's content. Use 'list_item:'.",
                                    },
                                    "mime_type": {
                                        "type": "string",
                                        "required": True,
                                        "description": "Expression to get the artifact's MIME type. Use 'list_item:'.",
                                    },
                                    "content_encoding": {
                                        "type": "string",
                                        "required": False,
                                        "description": "Expression to get the content encoding ('base64', 'text', 'binary'). Use 'list_item:'. If omitted, content type is inferred.",
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        {
            "name": "output_handlers",
            "required": False,
            "type": "list",
            "default": [],
            "description": "List of output handlers defining how to process and publish A2A task responses.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "required": True,
                        "description": "Unique name for the output handler.",
                    },
                    "max_file_size_for_base64_bytes": {
                        "type": "integer",
                        "required": False,
                        "default": 1048576,  # 1MB
                        "description": "Maximum size in bytes for a file artifact to be embedded in the output payload. Files larger than this will be omitted and an error will be noted in their place.",
                    },
                    "output_transforms": {
                        "type": "list",
                        "required": False,
                        "default": [],
                        "description": "List of SAC transform definitions applied to the A2A Task object.",
                        "items": {"type": "object"},
                    },
                    "topic_expression": {
                        "type": "string",
                        "required": True,
                        "description": "SAC expression string that dynamically determines the Solace topic to publish the response to.",
                    },
                    "payload_expression": {
                        "type": "string",
                        "required": True,
                        "description": "SAC expression string to dynamically generate the payload for the outgoing Solace message.",
                    },
                    "payload_encoding": {
                        "type": "string",
                        "required": False,
                        "default": "utf-8",
                        "description": "Specifies the encoding for the outgoing payload.",
                    },
                    "payload_format": {
                        "type": "string",
                        "required": False,
                        "default": "json",
                        "description": "Specifies the format of the outgoing payload.",
                    },
                    "output_schema": {
                        "type": "object",
                        "required": False,
                        "default": {},
                        "description": "Embedded JSON Schema object to validate the generated payload against before publishing.",
                        "additionalProperties": True,
                    },
                    "on_validation_error": {
                        "type": "string",
                        "required": False,
                        "default": "log",
                        "enum": ["log", "drop"],
                        "description": "Action to take if output schema validation fails.",
                    },
                },
            },
        },
    ]

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        """
        Initializes the EventMeshGatewayApp.
        Most setup is handled by BaseGatewayApp.
        """
        log_prefix = app_info.get("name", "EventMeshGatewayApp")
        log.debug("[%s] Initializing EventMeshGatewayApp...", log_prefix)
        super().__init__(app_info=app_info, **kwargs)
        log.debug("[%s] EventMeshGatewayApp initialization complete.", self.name)

    def _get_gateway_component_class(self) -> Type[BaseGatewayComponent]:
        """
        Returns the specific gateway component class for this application.
        """
        return EventMeshGatewayComponent
