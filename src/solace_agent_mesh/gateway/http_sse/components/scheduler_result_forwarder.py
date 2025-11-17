"""
Forwarder component for scheduler result handling.
Receives A2A responses from the broker and forwards them to the result handler.
"""

import logging
from typing import Any

from solace_ai_connector.common.event import Event
from solace_ai_connector.components.component_base import ComponentBase

log = logging.getLogger(__name__)


info = {
    "class_name": "SchedulerResultForwarderComponent",
    "description": "Forwards A2A responses to the scheduler result handler queue",
    "config_parameters": [
        {
            "name": "target_queue_ref",
            "required": True,
            "description": "Reference to the target queue.Queue for forwarding messages",
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {},
    },
    "output_schema": {
        "type": "object",
        "properties": {},
    },
}


class SchedulerResultForwarderComponent(ComponentBase):
    """
    Receives A2A response messages from BrokerInput and forwards them
    to a Python queue for processing by the result handler.
    """

    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.target_queue = self.get_config("target_queue_ref")
        if not self.target_queue:
            raise ValueError("target_queue_ref is required")
        log.info(
            "%s SchedulerResultForwarderComponent initialized.",
            self.log_identifier
        )

    def invoke(self, message: Any, data: Any):
        """
        Receives a message from BrokerInput and forwards it to the target queue.
        
        Args:
            message: The Solace message object
            data: The message data (topic, payload, user_properties)
        """
        try:
            if not isinstance(data, dict):
                log.warning(
                    "%s Received non-dict data, skipping: %s",
                    self.log_identifier,
                    type(data),
                )
                return None

            # Forward to result handler queue
            try:
                self.target_queue.put_nowait(data)
                log.debug(
                    "%s Forwarded scheduler response to result handler queue. Topic: %s",
                    self.log_identifier,
                    data.get("topic", "unknown"),
                )
            except Exception as queue_err:
                log.error(
                    "%s Failed to put message in result handler queue: %s",
                    self.log_identifier,
                    queue_err,
                )

        except Exception as e:
            log.exception(
                "%s Error in SchedulerResultForwarderComponent.invoke: %s",
                self.log_identifier,
                e,
            )

        return None