"""
SAC Component to forward messages from an internal BrokerInput
to the WebUIBackendComponent's internal queue for task logging.
"""
import logging
import queue
from typing import Any, Dict

from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message as SolaceMessage

log = logging.getLogger(__name__)

info = {
    "class_name": "TaskLoggerForwarderComponent",
    "description": (
        "Forwards A2A messages from an internal BrokerInput to the main "
        "WebUIBackendComponent's internal queue for task logging."
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


class TaskLoggerForwarderComponent(ComponentBase):
    """
    A simple SAC component that takes messages from its input (typically
    from a BrokerInput) and puts them onto a target Python queue.Queue
    instance provided in its configuration.
    """

    def __init__(self, **kwargs: Any):
        super().__init__(info, **kwargs)
        self.target_queue: queue.Queue = self.get_config("target_queue_ref")
        if not isinstance(self.target_queue, queue.Queue):
            log.error(
                "%s Configuration 'target_queue_ref' is not a valid queue.Queue instance. Type: %s",
                self.log_identifier,
                type(self.target_queue),
            )
            raise ValueError(
                f"{self.log_identifier} 'target_queue_ref' must be a queue.Queue instance."
            )
        log.info("%s TaskLoggerForwarderComponent initialized.", self.log_identifier)

    def invoke(self, message: SolaceMessage, data: Dict[str, Any]) -> None:
        """
        Processes the incoming message and forwards it.

        Args:
            message: The SolaceMessage object from BrokerInput (this is the original message).
            data: The data extracted by BrokerInput's output_schema (payload, topic, user_properties).
        """
        log_id_prefix = f"{self.log_identifier}[Invoke]"
        try:

            forward_data = {
                "topic": data.get("topic"),
                "payload": data.get("payload"),
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
            except queue.Full:
                log.warning(
                    "%s Task logging queue is full. Message dropped. Current size: %d",
                    log_id_prefix,
                    self.target_queue.qsize(),
                )

            message.call_acknowledgements()
            log.debug("%s Message acknowledged to BrokerInput.", log_id_prefix)

        except Exception as e:
            log.exception(
                "%s Error in TaskLoggerForwarderComponent invoke: %s",
                log_id_prefix,
                e,
            )
            if message:
                message.call_negative_acknowledgements()
            raise
        return None
