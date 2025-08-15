"""
This file defines the components and fixtures for the generic test client
that interacts with the dev_mode broker.
"""

import pytest
import queue
import asyncio
from collections import namedtuple
from typing import Any, Dict, Optional

from solace_ai_connector.common.utils import deep_merge
from solace_ai_connector.flow.app import App
from solace_ai_connector.components.component_base import ComponentBase
from solace_ai_connector.common.message import Message as SolaceMessage
from solace_ai_connector.common.log import log
from solace_ai_connector.solace_ai_connector import SolaceAiConnector


capture_info = {
    "class_name": "CaptureComponent",
    "description": "Captures incoming messages from the dev_mode broker and puts them into a shared queue for tests.",
    "config_parameters": [
        {"name": "capture_queue", "required": True, "type": "queue.Queue"}
    ],
    "input_schema": {},
    "output_schema": None,
}


class CaptureComponent(ComponentBase):
    """A simple SAC component that puts any message it receives into a queue."""

    def __init__(self, **kwargs: Any):
        super().__init__(capture_info, **kwargs)
        self.capture_queue: queue.Queue = self.get_config("capture_queue")
        if not isinstance(self.capture_queue, queue.Queue):
            raise TypeError("capture_queue must be a valid queue.Queue instance.")

    def invoke(self, message: SolaceMessage, data: Any) -> None:
        """Puts the message into the capture queue and acknowledges it."""
        log.debug(
            "%s Capturing message on topic: %s",
            self.log_identifier,
            message.get_topic(),
        )
        self.capture_queue.put(message)
        message.call_acknowledgements()
        return None


class TestDataPlaneClientApp(App):
    """A code-defined SAC App that hosts the CaptureComponent for testing."""

    def __init__(self, app_info: Dict[str, Any], **kwargs: Any):
        capture_queue = app_info.get("capture_queue")
        if not capture_queue:
            raise ValueError(
                "TestDataPlaneClientApp requires a 'capture_queue' in its app_info."
            )

        app_structure = {
            "name": "TestDataPlaneClientApp",
            "broker": {
                "dev_mode": True,
                "input_enabled": True,
                "output_enabled": True,
            },
            "components": [
                {
                    "name": "capture_component",
                    "component_class": CaptureComponent,
                    "component_config": {"capture_queue": capture_queue},
                    "subscriptions": [{"topic": "test/em_gateway/out/>"}],
                }
            ],
        }

        final_app_info = deep_merge(app_structure, app_info)
        final_app_info.pop("capture_queue", None)

        super().__init__(app_info=final_app_info, **kwargs)


TestDataPlaneClient = namedtuple("TestDataPlaneClient", ["publish", "get_next_message"])


@pytest.fixture(scope="session")
def test_data_plane_client(shared_solace_connector: SolaceAiConnector):
    """
    Provides a client to interact with the dev_mode broker for data plane testing.
    """
    app_name = "TestDataPlaneClientApp"
    client_app = shared_solace_connector.get_app(app_name)
    if not client_app:
        pytest.fail(
            f"Could not find the '{app_name}' instance in the shared connector."
        )

    capture_component = client_app.flows[0].component_groups[0][0]
    capture_q = capture_component.get_config("capture_queue")

    async def publish(
        topic: str, payload: bytes, user_properties: Optional[Dict] = None
    ):
        """Publishes a message to the dev_mode broker via the client app."""
        client_app.send_message(
            topic=topic, payload=payload, user_properties=user_properties
        )

    async def get_next_message(timeout: float = 5.0) -> SolaceMessage:
        """Retrieves the next captured message from the gateway."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None, lambda: capture_q.get(timeout=timeout)
            )
        except queue.Empty:
            pytest.fail(
                f"Did not receive a message on the capture queue within {timeout} seconds."
            )

    yield TestDataPlaneClient(publish=publish, get_next_message=get_next_message)

    while not capture_q.empty():
        try:
            capture_q.get_nowait()
        except queue.Empty:
            break
