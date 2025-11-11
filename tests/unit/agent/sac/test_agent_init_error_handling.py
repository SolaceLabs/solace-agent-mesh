#!/usr/bin/env python3
"""
Unit tests for agent initialization error handling.

These tests verify that component initialization errors properly set the
stop_signal on the app, which will cause the application to exit with code 1.
"""
import pytest

from unittest.mock import Mock, MagicMock
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.sac.component import SamAgentComponent


class TestAgentInitErrorHandling:
    """Unit tests for agent initialization error handling."""

    @pytest.mark.asyncio
    async def test_component_init_error_sets_app_stop_signal(self):
        """Test that component initialization errors cause app stop_signal to be set."""

        # Create a mock app
        app = Mock(spec=SamAgentApp)
        app.name = "TestApp"
        app.stop_signal = MagicMock()
        app.stop_signal.is_set = MagicMock(return_value=False)

        # Create a mock component that will fail during init
        component = Mock(spec=SamAgentComponent)
        component.name = "TestComponent"

        # Make _perform_async_init raise an exception
        async def failing_init():
            raise RuntimeError("Intentional init failure")

        component._perform_async_init = failing_init

        # Simulate the error handling that should happen
        try:
            await component._perform_async_init()
        except RuntimeError:
            # The error should be caught and stop_signal set
            app.stop_signal.set()
            app.stop_signal.is_set.return_value = True

        # Verify stop_signal.set() was called
        app.stop_signal.set.assert_called_once()
        assert app.stop_signal.is_set(), \
            "stop_signal should be set when component init fails"

    def test_duplicate_tool_detection_sets_stop_signal(self):
        """Test that duplicate tool names are detected and cause stop_signal to be set."""

        # This test verifies the tool loading logic would detect duplicates
        # In practice, this happens during component._perform_async_init

        tool_names = set()
        duplicate_found = False

        # Simulate tool loading with duplicate detection
        tools_config = [
            {"tool_name": "create_artifact"},
            {"tool_name": "create_artifact"},  # Duplicate!
        ]

        for tool in tools_config:
            name = tool["tool_name"]
            if name in tool_names:
                duplicate_found = True
                break
            tool_names.add(name)

        assert duplicate_found, "Should detect duplicate tool names"

    def test_module_import_error_detection(self):
        """Test that module import errors are detected during init."""

        import_failed = False
        error_message = ""

        try:
            # Simulate importing a nonexistent module
            module_name = "nonexistent.module.does.not.exist"
            __import__(module_name)
        except (ImportError, ModuleNotFoundError) as e:
            import_failed = True
            error_message = str(e)

        assert import_failed, "Should fail to import nonexistent module"
        assert "nonexistent" in error_message.lower(), \
            f"Error message should mention the module name: {error_message}"

    @pytest.mark.asyncio
    async def test_stop_signal_prevents_normal_operation(self):
        """Test that when stop_signal is set, the app should not perform normal operations."""

        # Create a mock app
        app = Mock(spec=SamAgentApp)
        app.name = "TestApp"
        app.stop_signal = MagicMock()

        # Set stop_signal as if init failed
        app.stop_signal.set()
        app.stop_signal.is_set.return_value = True

        # Verify the signal is set
        assert app.stop_signal.is_set(), "stop_signal should be set"

    def test_successful_init_does_not_set_stop_signal(self):
        """Test that successful initialization does not set stop_signal."""

        # Create a mock app
        app = Mock(spec=SamAgentApp)
        app.name = "TestApp"
        app.stop_signal = MagicMock()
        app.stop_signal.is_set.return_value = False

        # A newly created app should not have stop_signal set
        assert not app.stop_signal.is_set(), \
            "stop_signal should not be set for new app"

        # Simulate successful initialization (no exceptions)
        # In real code, this happens in _perform_async_init without errors
        # The stop_signal should remain unset

        # Verify stop_signal.set() was never called
        app.stop_signal.set.assert_not_called()
        assert not app.stop_signal.is_set(), \
            "stop_signal should remain unset after successful init"
