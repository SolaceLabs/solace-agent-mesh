"""
SAC Component to forward messages from an internal BrokerInput
to the WebUIBackendComponent's internal queue for visualization.
"""

import asyncio
import logging
import queue
from typing import Any, Dict

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message as SolaceMessage

log = logging.getLogger(__name__)

info = {
    "class_name": "VisualizationForwarderComponent",
    "description": (
        "Forwards A2A messages from an internal BrokerInput to the main "
        "WebUIBackendComponent's internal queue for visualization."
    ),
    "config_parameters": [
        {
            "name": "target_queue_ref",
            "required": True,
            "type": "queue.Queue",
            "description": "A direct reference to the target queue.Queue instance in WebUIBackendComponent.",
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


class VisualizationForwarderComponent(ComponentBase):
    """
    A simple SAC component that takes messages from its input (typically
    from a BrokerInput) and puts them onto a target Python queue.Queue or asyncio.Queue instance
    instance provided in its configuration.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(info, **kwargs)
        self.target_queue = self.get_config("target_queue_ref")
        if not isinstance(self.target_queue, (queue.Queue, asyncio.Queue)):
            log.error(
                "%s Configuration 'target_queue_ref' is not a valid Queue instance. Type: %s",
                self.log_identifier,
                type(self.target_queue),
            )
            raise ValueError(
                f"{self.log_identifier} 'target_queue_ref' must be a queue.Queue instance."
            )
        log.info("%s VisualizationForwarderComponent initialized.", self.log_identifier)

    def invoke(self, message: SolaceMessage, data: Dict[str, Any]) -> None:
        """
        Processes the incoming message and forwards it.

        Args:
            message: The SolaceMessage object from BrokerInput (this is the original message).
            data: The data extracted by BrokerInput's output_schema (payload, topic, user_properties).
        """
        log_id_prefix = f"{self.log_identifier}[Invoke]"
        try:
            topic = data.get("topic", "")
            payload = data.get("payload", {})

            # Filter out discovery, trust messages, in-progress updates for files and LLM stream
            # early to prevent queue buildup and reduce noise in visualization streams
            is_working_state = payload.get("result", {}).get("status", {}).get('state') == "working"
            parts = payload.get("result", {}).get("status", {}).get("message", {}).get("parts", [])
            is_in_progress_data = bool(parts) and all(
                part.get("data", {}).get("status") == "in-progress" for part in parts
            )
            is_text_update = bool(parts) and all(part.get("kind") == "text" for part in parts)
            if ("/a2a/v1/discovery/" in topic) or ("/a2a/v1/trust/" in topic) or (
                is_working_state and (is_in_progress_data or is_text_update)
            ):
                message.call_acknowledgements()
                log.debug(
                    "%s Skipping discovery/trust message: %s",
                    log_id_prefix,
                    topic,
                )
                return None

            forward_data = {
                "topic": topic,
                "payload": payload,
                "user_properties": data.get("user_properties") or {},
                "_original_broker_message": message,
            }
            log.debug(
                "%s Forwarding message for topic: %s",
                log_id_prefix,
                forward_data["topic"],
            )
            try:
                self.target_queue.put_nowait(forward_data)
            except (queue.Full, asyncio.QueueFull):
                log.warning(
                    "%s Visualization queue is full. Message dropped. Current size: %d",
                    log_id_prefix,
                    self.target_queue.qsize(),
                )

            message.call_acknowledgements()
            log.debug("%s Message acknowledged to BrokerInput.", log_id_prefix)

        except Exception as e:
            log.exception(
                "%s Error in VisualizationForwarderComponent invoke: %s",
                log_id_prefix,
                e,
            )
            if message:
                message.call_negative_acknowledgements()
            raise
        return None
