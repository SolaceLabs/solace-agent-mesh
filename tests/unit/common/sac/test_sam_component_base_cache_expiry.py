import asyncio
import logging
import threading
import time
import unittest
from typing import Any, Dict
from unittest.mock import patch

from solace_ai_connector.common.event import Event, EventType

from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase


logger = logging.getLogger(__name__)


class TestSamComponent(SamComponentBase):
    """
    Concrete implementation of SamComponentBase for testing.
    Provides both async and sync versions of handle_cache_expiry_event.
    """

    def __init__(self, info: dict[str, Any], use_async_handler: bool = True, **kwargs: Any):
        """
        Initialize test component.

        Args:
            info: Component configuration
            use_async_handler: If True, uses async handler; if False, uses sync handler
        """
        self.use_async_handler = use_async_handler
        self.handler_called = threading.Event()
        self.handler_call_data = None
        self.handler_call_count = 0
        # Initialize stop_signal before calling super().__init__
        self.stop_signal = threading.Event()
        super().__init__(info, **kwargs)

    async def _handle_message_async(self, message, topic: str) -> None:
        """Minimal implementation of abstract method."""
        pass

    def _get_component_id(self) -> str:
        """Return test component ID."""
        return "test_component_id"

    def _get_component_type(self) -> str:
        """Return test component type."""
        return "test_component"

    def _pre_async_cleanup(self) -> None:
        """Minimal implementation of abstract method."""
        pass

    async def _async_setup_and_run(self) -> None:
        """Minimal async setup - just wait for stop signal."""
        await super()._async_setup_and_run()
        # Keep running until stop_signal is set
        if self.stop_signal:
            while not self.stop_signal.is_set():
                await asyncio.sleep(0.1)
        else:
            # If stop_signal is None, just sleep briefly
            await asyncio.sleep(0.1)

    # Handler methods for testing
    async def handle_cache_expiry_event_async(self, cache_data: Dict[str, Any]):
        """Async handler for cache expiry events."""
        logger.debug("Async handler called with: %s", cache_data)
        self.handler_call_count += 1
        self.handler_call_data = cache_data
        self.handler_called.set()

    def handle_cache_expiry_event_sync(self, cache_data: Dict[str, Any]):
        """Sync handler for cache expiry events."""
        logger.debug("Sync handler called with: %s", cache_data)
        self.handler_call_count += 1
        self.handler_call_data = cache_data
        self.handler_called.set()

    # Property to dynamically return the correct handler
    @property
    def handle_cache_expiry_event(self):
        """Return the appropriate handler based on configuration."""
        if self.use_async_handler:
            return self.handle_cache_expiry_event_async
        else:
            return self.handle_cache_expiry_event_sync


class TestSamComponentBaseCacheExpiry(unittest.TestCase):
    """Test suite for CACHE_EXPIRY event handling in SamComponentBase."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration
        self.test_info = {
            "component_name": "test_component",
            "component_module": "test_module",
            "component_config": {
                "namespace": "test/namespace",
                "max_message_size_bytes": 1024000,
            }
        }

        # Mock the get_config method to return our test config
        self.config_patch = patch.object(
            SamComponentBase, 'get_config',
            side_effect=lambda key: self.test_info["component_config"].get(key)
        )
        self.config_patch.start()

    def tearDown(self):
        """Clean up after tests."""
        self.config_patch.stop()

    def test_cache_expiry_with_async_handler(self):
        """Test that async handlers are properly scheduled on the event loop."""
        # Create component with async handler
        component = TestSamComponent(self.test_info, use_async_handler=True)

        # Start the async loop
        component._async_thread = threading.Thread(
            target=component._run_async_operations,
            name="TestAsyncOpsThread",
            daemon=True,
        )
        component._async_thread.start()

        # Wait for event loop to be ready
        timeout = 5
        start_time = time.time()
        while not component._async_loop or not component._async_loop.is_running():
            if time.time() - start_time > timeout:
                self.fail("Event loop did not start within timeout")
            time.sleep(0.1)

        try:
            # Create cache expiry event
            cache_data = {"key": "test_key", "expired_data": "test_value"}
            event = Event(event_type=EventType.CACHE_EXPIRY, data=cache_data)

            # Process the event
            component.process_event(event)

            # Wait for async handler to complete
            handler_completed = component.handler_called.wait(timeout=5)
            self.assertTrue(
                handler_completed,
                "Async handler was not called within timeout"
            )

            # Verify handler was called with correct data
            self.assertEqual(component.handler_call_count, 1)
            self.assertEqual(component.handler_call_data, cache_data)

        finally:
            # Cleanup
            if component.stop_signal:
                component.stop_signal.set()
            if component._async_loop and component._async_loop.is_running():
                component._async_loop.call_soon_threadsafe(component._async_loop.stop)
            if component._async_thread and component._async_thread.is_alive():
                component._async_thread.join(timeout=2)

    def test_cache_expiry_with_sync_handler(self):
        """Test that sync handlers are called directly without event loop scheduling."""
        # Create component with sync handler
        component = TestSamComponent(self.test_info, use_async_handler=False)

        # Create cache expiry event
        cache_data = {"key": "test_key", "expired_data": "test_value"}
        event = Event(event_type=EventType.CACHE_EXPIRY, data=cache_data)

        # Process the event (should call handler synchronously)
        component.process_event(event)

        # Verify handler was called immediately with correct data
        self.assertEqual(component.handler_call_count, 1)
        self.assertEqual(component.handler_call_data, cache_data)
        self.assertTrue(component.handler_called.is_set())

    @patch('solace_agent_mesh.common.sac.sam_component_base.log')
    def test_cache_expiry_async_handler_no_event_loop(self, mock_log):
        """Test error handling when async handler is used but event loop is not available."""
        # Create component with async handler
        component = TestSamComponent(self.test_info, use_async_handler=True)

        # Ensure event loop is None
        component._async_loop = None

        # Create cache expiry event
        cache_data = {"key": "test_key", "expired_data": "test_value"}
        event = Event(event_type=EventType.CACHE_EXPIRY, data=cache_data)

        # Process the event
        component.process_event(event)

        # Verify error was logged
        mock_log.error.assert_called()
        error_message = mock_log.error.call_args[0][0]
        self.assertIn("Cannot handle async CACHE_EXPIRY", error_message)

        # Verify handler was not called
        self.assertEqual(component.handler_call_count, 0)


if __name__ == "__main__":
    unittest.main()
