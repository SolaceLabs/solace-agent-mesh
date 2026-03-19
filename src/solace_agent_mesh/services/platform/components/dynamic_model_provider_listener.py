"""
Bootstrap request listener component for the Platform Service.

Receives model configuration bootstrap requests from agents (via DynamicModelProvider)
and responds with the full LiteLlm config from the database.
"""

import logging
from typing import Any, Dict

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_agent_mesh.services.platform.api.dependencies import (
    get_platform_db,
    get_model_config_service,
)

log = logging.getLogger(__name__)

_listener_info = {
    "class_name": "BootstrapRequestListenerComponent",
    "description": (
        "Receives model config bootstrap requests from agents and responds "
        "with the full LiteLlm configuration from the platform database."
    ),
    "config_parameters": [
        {
            "name": "platform_component_ref",
            "required": True,
            "type": "object",
            "description": "A direct reference to the PlatformServiceComponent instance.",
        }
    ],
    "input_schema": {
        "type": "object",
        "description": "Output from a BrokerInput component.",
        "properties": {
            "payload": {"type": "any", "description": "The message payload."},
            "topic": {"type": "string", "description": "The message topic."},
            "user_properties": {
                "type": "object",
                "description": "User properties of the message.",
            },
        },
        "required": ["payload", "topic"],
    },
    "output_schema": None,
}


class BootstrapRequestListenerComponent(ComponentBase):
    """
    A SAC component that receives model config bootstrap requests from agents
    and responds with the full LiteLlm configuration from the platform database.

    Agents send bootstrap requests with:
        - model_id: The model alias or UUID to look up
        - reply_to: The topic to publish the response to
        - component_id: The requesting component's identifier
        - component_type: The requesting component's type
    """

    info = _listener_info

    def __init__(self, **kwargs: Any):
        super().__init__(_listener_info, **kwargs)
        self.platform_component = self.get_config("platform_component_ref")
        log.info("%s BootstrapRequestListenerComponent initialized.", self.log_identifier)

    def invoke(self, message: SolaceMessage, data: Dict[str, Any]) -> None:
        log_id_prefix = f"{self.log_identifier}[Invoke]"
        try:
            topic = data.get("topic", "")
            payload = data.get("payload", {})

            log.info(
                "%s Received bootstrap request on topic: %s",
                log_id_prefix,
                topic,
            )

            model_id = payload.get("model_id")
            reply_to = payload.get("reply_to")

            if not model_id or not reply_to:
                log.warning(
                    "%s Missing model_id or reply_to in bootstrap request payload: %s",
                    log_id_prefix,
                    payload,
                )
                message.call_acknowledgements()
                return None

            # Fetch model config from DB
            model_config = self._get_model_config(model_id)

            log.info(
                "%s Responding to bootstrap request for model_id=%s, reply_to=%s, config_found=%s",
                log_id_prefix,
                model_id,
                reply_to,
                model_config is not None,
            )

            # Publish response to the reply_to topic
            response_payload = {"model_config": model_config}
            self.platform_component.publish_a2a_message(
                payload=response_payload, topic=reply_to
            )

            message.call_acknowledgements()
            log.debug("%s Message acknowledged.", log_id_prefix)

        except Exception as e:
            log.exception(
                "%s Error in BootstrapRequestListenerComponent invoke: %s",
                log_id_prefix,
                e,
            )
            if message:
                message.call_negative_acknowledgements()
            raise
        return None

    def _get_model_config(self, model_id: str) -> dict | None:
        """Look up raw LiteLlm config from DB using ModelConfigService."""
        db = get_platform_db()
        service = get_model_config_service()
        return service.get_by_alias_or_id(db, model_id, raw=True)
