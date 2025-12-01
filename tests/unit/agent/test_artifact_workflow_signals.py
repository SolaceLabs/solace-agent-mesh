#!/usr/bin/env python3
"""
Unit tests for artifact workflow visualization signal emission.

Tests verify that artifact creation properly emits artifact_creation_progress signals
for workflow diagram visualization, including:
- Tool-created artifacts with function_call_id
- Signal suppression flag functionality
- Graceful handling when required context is missing
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime, timezone

from solace_agent_mesh.common.data_parts import ArtifactCreationProgressData


class TestArtifactWorkflowSignals:
    """Test artifact signal emission for workflow visualization."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with necessary attributes."""
        mock_context = Mock()
        mock_invocation_context = Mock()
        mock_agent = Mock()
        mock_host_component = Mock()

        # Setup component hierarchy
        mock_host_component.get_async_loop = Mock(return_value=None)
        mock_host_component.agent_name = "test-agent"
        mock_host_component._publish_status_update_with_buffer_flush = AsyncMock()

        mock_agent.host_component = mock_host_component
        mock_invocation_context.agent = mock_agent
        mock_invocation_context.artifact_service = AsyncMock()
        mock_invocation_context.app_name = "TestApp"
        mock_invocation_context.user_id = "test-user-123"
        mock_invocation_context.session = Mock()
        mock_invocation_context.session.last_update_time = datetime.now(timezone.utc)

        mock_context._invocation_context = mock_invocation_context

        # Setup actions with artifact_delta dict
        mock_actions = Mock()
        mock_actions.artifact_delta = {}
        mock_context.actions = mock_actions

        # Setup state with a2a_context
        mock_context.state = {
            "a2a_context": {
                "logical_task_id": "task-123",
                "context_id": "ctx-456"
            },
            "function_call_id": "fc-789"
        }

        return mock_context

    @pytest.mark.asyncio
    async def test_tool_artifact_emits_signal_with_function_call_id(self, mock_tool_context):
        """Test that artifacts created by tools include function_call_id in signal."""
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

        # Mock artifact service
        mock_artifact_service = AsyncMock()
        mock_artifact_service.save_artifact = AsyncMock(return_value=1)  # version 1

        # Mock the signal publishing function to capture the signal
        captured_signal = None

        async def capture_publish(host_component, a2a_context, data_part_model):
            nonlocal captured_signal
            captured_signal = data_part_model

        # Execute - call the real function with mocked dependencies
        with patch('solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update', new=capture_publish):
            result = await save_artifact_with_metadata(
                artifact_service=mock_artifact_service,
                app_name="TestApp",
                user_id="user-123",
                session_id="session-456",
                filename="output.json",
                content_bytes=b'{"result": "test"}',
                mime_type="application/json",
                metadata_dict={"description": "Test output"},
                timestamp=datetime.now(timezone.utc),
                tool_context=mock_tool_context
            )

        # Verify result
        assert result["status"] == "success"
        assert result["data_version"] == 1

        # Verify signal was captured
        assert captured_signal is not None
        assert isinstance(captured_signal, ArtifactCreationProgressData)
        assert captured_signal.filename == "output.json"
        assert captured_signal.status == "completed"
        assert captured_signal.version == 1
        assert captured_signal.mime_type == "application/json"
        assert captured_signal.description == "Test output"
        assert captured_signal.function_call_id == "fc-789"  # From tool_context

    @pytest.mark.asyncio
    async def test_signal_not_emitted_when_suppress_flag_set(self, mock_tool_context):
        """Test that signal is not emitted when suppress_visualization_signal is True."""
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

        # Mock artifact service
        mock_artifact_service = AsyncMock()
        mock_artifact_service.save_artifact = AsyncMock(return_value=1)

        # Capture any signal emissions
        signal_emitted = False

        async def capture_publish(*args, **kwargs):
            nonlocal signal_emitted
            signal_emitted = True

        with patch('solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update', new=capture_publish):
            from solace_agent_mesh.agent.utils import artifact_helpers

            result = await artifact_helpers.save_artifact_with_metadata(
                artifact_service=mock_artifact_service,
                app_name="TestApp",
                user_id="user-123",
                session_id="session-456",
                filename="output.json",
                content_bytes=b'{"result": "test"}',
                mime_type="application/json",
                metadata_dict={"description": "Test output"},
                timestamp=datetime.now(timezone.utc),
                tool_context=mock_tool_context,
                suppress_visualization_signal=True  # Suppressed
            )

        # Verify artifact was saved
        assert result["status"] == "success"

        # Verify signal was NOT emitted
        assert not signal_emitted

    @pytest.mark.asyncio
    async def test_no_signal_when_missing_context(self):
        """Test that no signal is emitted when a2a_context or host_component is missing."""
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

        # Create tool context without a2a_context
        mock_context = Mock()
        mock_invocation_context = Mock()
        mock_invocation_context.artifact_service = AsyncMock()
        mock_invocation_context.artifact_service.save_artifact = AsyncMock(return_value=1)
        mock_invocation_context.app_name = "TestApp"
        mock_invocation_context.user_id = "test-user"
        mock_invocation_context.session = Mock()
        mock_invocation_context.session.last_update_time = datetime.now(timezone.utc)

        mock_context._invocation_context = mock_invocation_context
        mock_context.state = {}  # No a2a_context

        # Setup actions with artifact_delta dict
        mock_actions = Mock()
        mock_actions.artifact_delta = {}
        mock_context.actions = mock_actions

        signal_emitted = False

        async def capture_publish(*args, **kwargs):
            nonlocal signal_emitted
            signal_emitted = True

        with patch('solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update', new=capture_publish):
            from solace_agent_mesh.agent.utils import artifact_helpers

            result = await artifact_helpers.save_artifact_with_metadata(
                artifact_service=mock_invocation_context.artifact_service,
                app_name="TestApp",
                user_id="user-123",
                session_id="session-456",
                filename="output.json",
                content_bytes=b'{"result": "test"}',
                mime_type="application/json",
                metadata_dict={"description": "Test output"},
                timestamp=datetime.now(timezone.utc),
                tool_context=mock_context
            )

        # Verify artifact was still saved
        assert result["status"] == "success"

        # Verify no signal was emitted due to missing context
        assert not signal_emitted
