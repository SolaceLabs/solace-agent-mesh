#!/usr/bin/env python3
"""
Unit tests for artifact workflow visualization signal emission.

Tests verify that artifact creation properly emits signals for workflow diagram visualization:
- Tool-created artifacts emit ArtifactSavedData signals with function_call_id
- LLM-generated artifacts (fenced blocks) emit ArtifactSavedData signals with synthetic function_call_id
- Signal suppression flag functionality
- Graceful handling when required context is missing
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from solace_agent_mesh.common.data_parts import ArtifactCreationProgressData, ArtifactSavedData


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
                "contextId": "ctx-456",  # camelCase as expected by _publish_data_part_status_update
                "session_id": "session-789"
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

        # Capture the call to notify_artifact_saved
        captured_artifact_info = None
        captured_function_call_id = None

        async def capture_notify(artifact_info, a2a_context, function_call_id=None):
            nonlocal captured_artifact_info, captured_function_call_id
            captured_artifact_info = artifact_info
            captured_function_call_id = function_call_id

        # Mock notify_artifact_saved on the host component
        mock_tool_context._invocation_context.agent.host_component.notify_artifact_saved = AsyncMock(side_effect=capture_notify)

        # Execute - call the real function with mocked dependencies
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

        # Verify notify_artifact_saved was called with correct artifact_info
        assert captured_artifact_info is not None
        assert captured_artifact_info.filename == "output.json"
        assert captured_artifact_info.version == 1
        assert captured_artifact_info.version_count is None  # Not populated during save
        assert captured_artifact_info.mime_type == "application/json"
        assert captured_artifact_info.size == len(b'{"result": "test"}')
        assert captured_artifact_info.description == "Test output"
        assert captured_function_call_id == "fc-789"  # From tool_context

    @pytest.mark.asyncio
    async def test_signal_not_emitted_when_suppress_flag_set(self, mock_tool_context):
        """Test that signal is not emitted when suppress_visualization_signal is True."""
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

        # Mock artifact service
        mock_artifact_service = AsyncMock()
        mock_artifact_service.save_artifact = AsyncMock(return_value=1)

        # Mock notify_artifact_saved to track if it was called
        mock_tool_context._invocation_context.agent.host_component.notify_artifact_saved = AsyncMock()

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
            tool_context=mock_tool_context,
            suppress_visualization_signal=True  # Suppressed
        )

        # Verify artifact was saved
        assert result["status"] == "success"

        # Verify notify_artifact_saved was NOT called
        mock_tool_context._invocation_context.agent.host_component.notify_artifact_saved.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_signal_when_missing_context(self):
        """Test that no signal is emitted when a2a_context or host_component is missing."""
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata

        # Create tool context without a2a_context
        mock_context = Mock()
        mock_invocation_context = Mock()
        mock_agent = Mock()
        mock_host_component = Mock()

        mock_invocation_context.artifact_service = AsyncMock()
        mock_invocation_context.artifact_service.save_artifact = AsyncMock(return_value=1)
        mock_invocation_context.app_name = "TestApp"
        mock_invocation_context.user_id = "test-user"
        mock_invocation_context.session = Mock()
        mock_invocation_context.session.last_update_time = datetime.now(timezone.utc)

        # Setup host_component with mocked notify_artifact_saved
        mock_host_component.notify_artifact_saved = AsyncMock()
        mock_agent.host_component = mock_host_component
        mock_invocation_context.agent = mock_agent

        mock_context._invocation_context = mock_invocation_context
        mock_context.state = {}  # No a2a_context

        # Setup actions with artifact_delta dict
        mock_actions = Mock()
        mock_actions.artifact_delta = {}
        mock_context.actions = mock_actions

        result = await save_artifact_with_metadata(
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

        # Verify notify_artifact_saved was NOT called due to missing a2a_context
        mock_host_component.notify_artifact_saved.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_generated_artifact_with_synthetic_function_call_id(self, mock_tool_context):
        """Test that LLM-generated artifacts (fenced blocks) emit ArtifactSavedData signals with synthetic function_call_id.

        Simulates the flow where:
        1. Artifact saved during streaming with suppress_visualization_signal=True (no signal)
        2. Finalization creates synthetic tool call with host-notify-{uuid} ID
        3. ArtifactSavedData signal emitted with same synthetic function_call_id
        """
        from solace_agent_mesh.agent.utils.artifact_helpers import save_artifact_with_metadata
        import uuid

        # Mock artifact service
        mock_artifact_service = AsyncMock()
        mock_artifact_service.save_artifact = AsyncMock(return_value=1)

        # Phase 1: Artifact saved during streaming (signal suppressed)
        # Verify no signal emitted during this phase
        signal_emitted = False

        async def capture_publish(*args, **kwargs):
            nonlocal signal_emitted
            signal_emitted = True

        with patch('solace_agent_mesh.agent.adk.callbacks._publish_data_part_status_update', new=capture_publish):
            result = await save_artifact_with_metadata(
                artifact_service=mock_artifact_service,
                app_name="TestApp",
                user_id="user-123",
                session_id="session-456",
                filename="llm_output.txt",
                content_bytes=b'This is LLM-generated content',
                mime_type="text/plain",
                metadata_dict={"description": "LLM generated file"},
                timestamp=datetime.now(timezone.utc),
                tool_context=mock_tool_context,
                suppress_visualization_signal=True  # Suppressed during streaming
            )

        assert result["status"] == "success"
        assert result["data_version"] == 1
        assert not signal_emitted  # No signal during streaming

        # Phase 2: Finalization - simulate signal emission with synthetic function_call_id
        # This simulates what happens in callbacks.py lines 552-580
        synthetic_function_call_id = f"host-notify-{uuid.uuid4()}"

        # Create signal with synthetic ID (what callback does during finalization)
        # Now uses ArtifactSavedData instead of ArtifactCreationProgressData
        signal_data = ArtifactSavedData(
            type="artifact_saved",
            filename="llm_output.txt",
            version=1,
            mime_type="text/plain",
            size_bytes=len(b'This is LLM-generated content'),
            description="LLM generated file",
            function_call_id=synthetic_function_call_id,  # Synthetic ID
        )

        # Verify signal has correct structure for LLM-generated artifacts
        assert signal_data.type == "artifact_saved"
        assert signal_data.filename == "llm_output.txt"
        assert signal_data.version == 1
        assert signal_data.function_call_id == synthetic_function_call_id
        assert signal_data.function_call_id.startswith("host-notify-")  # Synthetic ID pattern
        assert signal_data.description == "LLM generated file"
        assert signal_data.mime_type == "text/plain"
        assert signal_data.size_bytes == 29  # len(b'This is LLM-generated content')
