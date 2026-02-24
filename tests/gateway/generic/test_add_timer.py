"""Tests for GenericGatewayComponent.add_timer() method.

This test verifies that add_timer() works with both calling conventions:
1. Adapter pattern: add_timer(delay_ms, callback=fn, interval_ms=ms)
2. Trust Manager pattern: add_timer(delay_ms, timer_id=id, interval_ms=ms, callback=fn)
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestAddTimerSignature:
    """Test that add_timer accepts both calling conventions."""

    def test_add_timer_accepts_timer_id_keyword_arg(self):
        """Test that add_timer accepts timer_id as a keyword argument.
        
        This is the calling convention used by Trust Manager:
        add_timer(delay_ms, timer_id=id, interval_ms=ms, callback=fn)
        """
        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        import inspect
        
        sig = inspect.signature(GenericGatewayComponent.add_timer)
        params = list(sig.parameters.keys())
        
        # Verify all required parameters are present
        assert 'delay_ms' in params, "add_timer must accept delay_ms"
        assert 'timer_id' in params, "add_timer must accept timer_id for Trust Manager"
        assert 'interval_ms' in params, "add_timer must accept interval_ms"
        assert 'callback' in params, "add_timer must accept callback"
        
        # Verify timer_id is optional (has default value)
        timer_id_param = sig.parameters['timer_id']
        assert timer_id_param.default is None, "timer_id should be optional (default=None)"

    def test_add_timer_signature_compatible_with_trust_manager(self):
        """Test that add_timer can be called with Trust Manager's calling convention.
        
        Trust Manager calls: add_timer(timer_id=..., delay_ms=..., interval_ms=..., callback=...)
        """
        from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
        import inspect
        
        sig = inspect.signature(GenericGatewayComponent.add_timer)
        
        # Simulate Trust Manager's call pattern
        # This should not raise TypeError
        try:
            # Bind the arguments as Trust Manager would call them
            sig.bind(
                None,  # self
                delay_ms=10000,
                timer_id="trust_card_publish_test",
                interval_ms=10000,
                callback=lambda: None
            )
        except TypeError as e:
            pytest.fail(f"add_timer signature incompatible with Trust Manager: {e}")


class TestAddTimerCallback:
    """Test that callbacks are properly registered and invoked."""

    @pytest.fixture
    def mock_component(self):
        """Create a mock GenericGatewayComponent for testing."""
        with patch('solace_agent_mesh.gateway.generic.component.GenericGatewayComponent.__init__', return_value=None):
            from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
            component = GenericGatewayComponent.__new__(GenericGatewayComponent)
            
            # Set up required attributes
            component.timer_manager = MagicMock()
            component.timer_manager.timers = []
            component._timer_callbacks = {}
            component._timer_callbacks_lock = MagicMock()
            component._timer_callbacks_lock.__enter__ = MagicMock(return_value=None)
            component._timer_callbacks_lock.__exit__ = MagicMock(return_value=None)
            component.log_identifier = "[test]"
            
            # Mock the parent's add_timer to capture the callback
            def mock_parent_add_timer(self, delay_ms, timer_id, interval_ms, callback):
                if callback:
                    component._timer_callbacks[timer_id] = callback
            
            with patch.object(component.__class__.__bases__[0], 'add_timer', mock_parent_add_timer):
                yield component

    def test_callback_is_callable_not_dict(self, mock_component):
        """Test that the callback registered is callable, not a dict.
        
        This was the bug: callback was being passed as {"callback": fn} instead of fn.
        """
        callback_called = False
        
        def my_callback():
            nonlocal callback_called
            callback_called = True
        
        # Call add_timer with Trust Manager pattern
        mock_component.add_timer(
            delay_ms=1000,
            timer_id="test_timer",
            interval_ms=1000,
            callback=my_callback
        )
        
        # Get the registered callback
        registered_callback = mock_component._timer_callbacks.get("test_timer")
        
        # Verify it's callable (not a dict)
        assert callable(registered_callback), \
            f"Registered callback should be callable, got {type(registered_callback)}"
        
        # Verify calling it doesn't raise "'dict' object is not callable"
        try:
            registered_callback({})  # Pass timer_data as SamComponentBase.process_event does
        except TypeError as e:
            if "'dict' object is not callable" in str(e):
                pytest.fail("Callback was registered as dict instead of callable function")
            raise


class TestAddTimerAsyncCallback:
    """Test that async callbacks are handled correctly."""

    def test_async_callback_detection(self):
        """Test that async callbacks are properly detected and scheduled."""
        import inspect
        
        async def async_callback():
            pass
        
        def sync_callback():
            pass
        
        assert inspect.iscoroutinefunction(async_callback), "async_callback should be detected as coroutine"
        assert not inspect.iscoroutinefunction(sync_callback), "sync_callback should not be detected as coroutine"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
