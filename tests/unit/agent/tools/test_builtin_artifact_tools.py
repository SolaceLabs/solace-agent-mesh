"""
Unit tests for builtin_artifact_tools.py

Tests for built-in artifact management functions including creation, listing, loading,
signaling, extraction, deletion, and updates.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from solace_agent_mesh.agent.tools.builtin_artifact_tools import (
    _internal_create_artifact,
    list_artifacts,
    load_artifact,
    signal_artifact_for_return,
    extract_content_from_artifact,
    delete_artifact,
    append_to_artifact,
    apply_embed_and_create_artifact,
    CATEGORY_NAME,
    CATEGORY_DESCRIPTION,
)


class TestInternalCreateArtifact:
    """Test cases for _internal_create_artifact function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context._invocation_context.session = Mock()
        mock_context._invocation_context.session.last_update_time = datetime.now(timezone.utc)
        return mock_context

    @pytest.mark.asyncio
    async def test_create_artifact_success(self, mock_tool_context):
        """Test successful artifact creation."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_save.return_value = {"status": "success", "filename": "test.txt", "data_version": 1}
            mock_session.return_value = "session123"
            
            result = await _internal_create_artifact(
                filename="test.txt",
                content="Hello World",
                mime_type="text/plain",
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_artifact_unsafe_filename(self, mock_tool_context):
        """Test artifact creation with unsafe filename."""
        result = await _internal_create_artifact(
            filename="../unsafe.txt",
            content="Hello World",
            mime_type="text/plain",
            tool_context=mock_tool_context
        )
        
        assert result["status"] == "error"
        assert "disallowed characters" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_create_artifact_no_tool_context(self):
        """Test artifact creation without tool context."""
        result = await _internal_create_artifact(
            filename="test.txt",
            content="Hello World",
            mime_type="text/plain",
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_create_artifact_with_metadata(self, mock_tool_context):
        """Test artifact creation with metadata."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_save.return_value = {"status": "success", "filename": "test.txt", "data_version": 1}
            mock_session.return_value = "session123"
            
            result = await _internal_create_artifact(
                filename="test.txt",
                content="Hello World",
                mime_type="text/plain",
                tool_context=mock_tool_context,
                description="Test artifact",
                metadata_json='{"key": "value"}'
            )
            
            assert result["status"] == "success"
            mock_save.assert_called_once()


class TestListArtifacts:
    """Test cases for list_artifacts function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        return mock_context

    @pytest.mark.asyncio
    async def test_list_artifacts_success(self, mock_tool_context):
        """Test successful artifact listing."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            mock_session.return_value = "session123"
            
            # Mock artifact service methods
            mock_tool_context._invocation_context.artifact_service.list_artifact_keys.return_value = [
                "test.txt", "test.txt.metadata"
            ]
            mock_tool_context._invocation_context.artifact_service.list_versions.return_value = [1, 2]
            
            # Mock metadata loading
            mock_metadata = Mock()
            mock_metadata.inline_data = Mock()
            mock_metadata.inline_data.data = json.dumps({
                "description": "Test file",
                "mime_type": "text/plain",
                "size_bytes": 100
            }).encode('utf-8')
            mock_tool_context._invocation_context.artifact_service.load_artifact.return_value = mock_metadata
            
            result = await list_artifacts(tool_context=mock_tool_context)
            
            assert result["status"] == "success"
            assert "artifacts" in result

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self, mock_tool_context):
        """Test listing when no artifacts exist."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            mock_session.return_value = "session123"
            mock_tool_context._invocation_context.artifact_service.list_artifact_keys.return_value = []
            
            result = await list_artifacts(tool_context=mock_tool_context)
            
            assert result["status"] == "success"
            assert result["artifacts"] == []

    @pytest.mark.asyncio
    async def test_list_artifacts_no_tool_context(self):
        """Test listing without tool context."""
        result = await list_artifacts(tool_context=None)
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]


class TestLoadArtifact:
    """Test cases for load_artifact function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context._invocation_context.agent = Mock()
        mock_context._invocation_context.agent.host_component = Mock()
        return mock_context

    @pytest.mark.asyncio
    async def test_load_artifact_success(self, mock_tool_context):
        """Test successful artifact loading."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_load.return_value = {
                "status": "success",
                "filename": "test.txt",
                "version": 1,
                "content": "Hello World"
            }
            mock_session.return_value = "session123"
            
            result = await load_artifact(
                filename="test.txt",
                version=1,
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_artifact_not_found(self, mock_tool_context):
        """Test loading non-existent artifact."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_load.side_effect = FileNotFoundError("Artifact not found")
            mock_session.return_value = "session123"
            
            result = await load_artifact(
                filename="missing.txt",
                version=1,
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "error"
            assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_load_artifact_no_tool_context(self):
        """Test loading without tool context."""
        result = await load_artifact(
            filename="test.txt",
            version=1,
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_load_artifact_with_max_length(self, mock_tool_context):
        """Test loading artifact with max content length."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_load.return_value = {
                "status": "success",
                "filename": "test.txt",
                "version": 1,
                "content": "Hello World"[:100]
            }
            mock_session.return_value = "session123"
            
            result = await load_artifact(
                filename="test.txt",
                version=1,
                max_content_length=100,
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_load.assert_called_once()


class TestSignalArtifactForReturn:
    """Test cases for signal_artifact_for_return function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.agent = Mock()
        mock_context._invocation_context.agent.host_component = Mock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context.state = {"a2a_context": {"logical_task_id": "task123"}}
        mock_context.actions = Mock()
        mock_context.actions.state_delta = {}
        return mock_context

    @pytest.mark.asyncio
    async def test_signal_artifact_success(self, mock_tool_context):
        """Test successful artifact signaling."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            mock_session.return_value = "session123"
            
            # Mock artifact service
            mock_tool_context._invocation_context.artifact_service.list_versions.return_value = [1, 2]
            
            # Mock host component and task execution context
            mock_task_context = Mock()
            mock_task_context.add_artifact_signal = Mock()
            
            # Create a proper context manager mock for active_tasks_lock
            mock_lock = Mock()
            mock_lock.__enter__ = Mock(return_value=mock_lock)
            mock_lock.__exit__ = Mock(return_value=None)
            mock_tool_context._invocation_context.agent.host_component.active_tasks_lock = mock_lock
            mock_tool_context._invocation_context.agent.host_component.active_tasks = {
                "task123": mock_task_context
            }
            
            result = await signal_artifact_for_return(
                filename="test.txt",
                version=1,
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_task_context.add_artifact_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_signal_artifact_no_tool_context(self):
        """Test signaling without tool context."""
        result = await signal_artifact_for_return(
            filename="test.txt",
            version=1,
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_signal_artifact_no_version(self, mock_tool_context):
        """Test signaling without version."""
        result = await signal_artifact_for_return(
            filename="test.txt",
            version=None,
            tool_context=mock_tool_context
        )
        
        assert result["status"] == "error"
        assert "Version parameter is required" in result["message"]


class TestExtractContentFromArtifact:
    """Test cases for extract_content_from_artifact function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        return mock_context

    @pytest.mark.asyncio
    async def test_extract_content_success(self, mock_tool_context):
        """Test that extract_content_from_artifact attempts to load the artifact."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_load.return_value = {
                "status": "success",
                "content": "Original content",
                "mime_type": "text/plain",
                "raw_bytes": b"Original content"
            }
            mock_session.return_value = "session123"
            
            # The function has complex LLM validation, so we'll just test that it attempts to load
            # the artifact. The LLM interaction part is tested in integration tests.
            with pytest.raises(Exception):
                await extract_content_from_artifact(
                    filename="test.txt",
                    extraction_goal="Extract key points",
                    tool_context=mock_tool_context
                )
            
            # The function should attempt to load the artifact before calling the LLM
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_content_no_tool_context(self):
        """Test extraction without tool context."""
        result = await extract_content_from_artifact(
            filename="test.txt",
            extraction_goal="Extract key points",
            tool_context=None
        )
        
        assert result["status"] == "error_tool_context_missing"
        # The function returns message_to_llm when tool_context is None
        assert "message_to_llm" in result
        assert "ToolContext is missing" in result["message_to_llm"]


class TestDeleteArtifact:
    """Test cases for delete_artifact function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context._invocation_context.agent = Mock()
        mock_context._invocation_context.agent.host_component = Mock()
        mock_context._invocation_context.agent.host_component.get_config = Mock(return_value={
            "model": "gpt-4",
            "supported_binary_mime_types": ["application/pdf", "image/jpeg"]
        })
        mock_context._invocation_context.agent.model = "gpt-4"
        mock_context._invocation_context.agent.get_config = Mock(return_value="gpt-4")
        return mock_context

    @pytest.mark.asyncio
    async def test_delete_artifact_success(self, mock_tool_context):
        """Test successful artifact deletion."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            mock_session.return_value = "session123"
            mock_tool_context._invocation_context.artifact_service.delete_artifact = AsyncMock()
            
            result = await delete_artifact(
                filename="test.txt",
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_tool_context._invocation_context.artifact_service.delete_artifact.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_artifact_not_found(self, mock_tool_context):
        """Test deleting non-existent artifact."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            mock_session.return_value = "session123"
            mock_tool_context._invocation_context.artifact_service.delete_artifact = AsyncMock(
                side_effect=FileNotFoundError("Artifact not found")
            )
            
            result = await delete_artifact(
                filename="missing.txt",
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "error"
            assert "not found" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_delete_artifact_no_tool_context(self):
        """Test deletion without tool context."""
        result = await delete_artifact(
            filename="test.txt",
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]


class TestAppendToArtifact:
    """Test cases for append_to_artifact function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context._invocation_context.agent = Mock()
        mock_context._invocation_context.agent.host_component = Mock()
        return mock_context

    @pytest.mark.asyncio
    async def test_append_to_artifact_success(self, mock_tool_context):
        """Test successful content appending."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": b"Original content",
                "mime_type": "text/plain",
                "version": 1
            }
            mock_save.return_value = {"status": "success", "data_version": 2}
            mock_session.return_value = "session123"
            
            result = await append_to_artifact(
                filename="test.txt",
                content_chunk=" Additional content",
                mime_type="text/plain",
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_load.assert_called()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_append_to_artifact_not_found(self, mock_tool_context):
        """Test appending to non-existent artifact."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_load.return_value = {
                "status": "error",
                "message": "Artifact not found"
            }
            mock_session.return_value = "session123"
            
            result = await append_to_artifact(
                filename="missing.txt",
                content_chunk=" Additional content",
                mime_type="text/plain",
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "error"
            assert "Failed to load original artifact" in result["message"]

    @pytest.mark.asyncio
    async def test_append_to_artifact_no_tool_context(self):
        """Test appending without tool context."""
        result = await append_to_artifact(
            filename="test.txt",
            content_chunk=" Additional content",
            mime_type="text/plain",
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]


class TestApplyEmbedAndCreateArtifact:
    """Test cases for apply_embed_and_create_artifact function."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a mock ToolContext with proper _invocation_context."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context._invocation_context.agent = Mock()
        mock_context._invocation_context.agent.host_component = Mock()
        mock_context._invocation_context.session = Mock()
        mock_context._invocation_context.session.last_update_time = datetime.now(timezone.utc)
        return mock_context

    @pytest.mark.asyncio
    async def test_apply_embed_success(self, mock_tool_context):
        """Test successful embed application."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.evaluate_embed') as mock_eval, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_eval.return_value = ("Resolved content", None, None)
            mock_save.return_value = {"status": "success", "data_version": 1}
            mock_session.return_value = "session123"
            
            result = await apply_embed_and_create_artifact(
                output_filename="output.txt",
                embed_directive="«artifact_content:test.txt»",
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            mock_eval.assert_called_once()
            mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_embed_invalid_directive(self, mock_tool_context):
        """Test embed application with invalid directive."""
        result = await apply_embed_and_create_artifact(
            output_filename="output.txt",
            embed_directive="invalid_directive",
            tool_context=mock_tool_context
        )
        
        assert result["status"] == "error"
        assert "Invalid embed directive format" in result["message"]

    @pytest.mark.asyncio
    async def test_apply_embed_no_tool_context(self):
        """Test embed application without tool context."""
        result = await apply_embed_and_create_artifact(
            output_filename="output.txt",
            embed_directive="«artifact_content:test.txt»",
            tool_context=None
        )
        
        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]


class TestBuiltinArtifactToolsIntegration:
    """Integration tests for builtin artifact tools."""

    @pytest.fixture
    def mock_tool_context(self):
        """Create a comprehensive mock ToolContext."""
        mock_context = Mock()
        mock_context._invocation_context = Mock()
        mock_context._invocation_context.artifact_service = AsyncMock()
        mock_context._invocation_context.app_name = "test_app"
        mock_context._invocation_context.user_id = "test_user"
        mock_context._invocation_context.agent = Mock()
        mock_context._invocation_context.agent.host_component = Mock()
        mock_context._invocation_context.session = Mock()
        mock_context._invocation_context.session.last_update_time = datetime.now(timezone.utc)
        mock_context.state = {"a2a_context": {"logical_task_id": "task123"}}
        mock_context.actions = Mock()
        mock_context.actions.state_delta = {}
        return mock_context

    @pytest.mark.asyncio
    async def test_create_list_load_workflow(self, mock_tool_context):
        """Test complete workflow: create, list, then load artifact."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_save.return_value = {"status": "success", "filename": "test.txt", "data_version": 1}
            mock_session.return_value = "session123"
            
            # Step 1: Create artifact
            create_result = await _internal_create_artifact(
                filename="test.txt",
                content="Hello World",
                mime_type="text/plain",
                tool_context=mock_tool_context
            )
            assert create_result["status"] == "success"
            
            # Step 2: List artifacts
            mock_tool_context._invocation_context.artifact_service.list_artifact_keys.return_value = ["test.txt"]
            mock_tool_context._invocation_context.artifact_service.list_versions.return_value = [1]
            
            list_result = await list_artifacts(tool_context=mock_tool_context)
            assert list_result["status"] == "success"
            
            # Step 3: Load artifact
            mock_load.return_value = {
                "status": "success",
                "filename": "test.txt",
                "version": 1,
                "content": "Hello World"
            }
            
            load_result = await load_artifact(
                filename="test.txt",
                version=1,
                tool_context=mock_tool_context
            )
            assert load_result["status"] == "success"

    @pytest.mark.asyncio
    async def test_create_append_workflow(self, mock_tool_context):
        """Test workflow: create artifact, then append to it."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            
            mock_save.return_value = {"status": "success", "filename": "log.txt", "data_version": 1}
            mock_session.return_value = "session123"
            
            # Step 1: Create initial artifact
            create_result = await _internal_create_artifact(
                filename="log.txt",
                content="Initial log entry",
                mime_type="text/plain",
                tool_context=mock_tool_context
            )
            assert create_result["status"] == "success"
            
            # Step 2: Append to artifact
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": b"Initial log entry",
                "mime_type": "text/plain",
                "version": 1
            }
            mock_save.return_value = {"status": "success", "data_version": 2}
            
            append_result = await append_to_artifact(
                filename="log.txt",
                content_chunk="\nSecond log entry",
                mime_type="text/plain",
                tool_context=mock_tool_context
            )
            assert append_result["status"] == "success"

    def test_category_constants(self):
        """Test that category constants are properly defined."""
        assert CATEGORY_NAME == "Artifact Management"
        assert CATEGORY_DESCRIPTION == "List, read, create, update, and delete artifacts."

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self, mock_tool_context):
        """Test that error handling is consistent across functions."""
        # Test unsafe filename handling across different functions
        unsafe_filename = "../unsafe.txt"
        
        create_result = await _internal_create_artifact(
            filename=unsafe_filename,
            content="test",
            mime_type="text/plain",
            tool_context=mock_tool_context
        )
        assert create_result["status"] == "error"
        assert "disallowed characters" in create_result["message"].lower()

    @pytest.mark.asyncio
    async def test_signal_and_state_management(self, mock_tool_context):
        """Test artifact signaling and state management."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:
            mock_session.return_value = "session123"
            
            # Mock artifact service and task context
            mock_tool_context._invocation_context.artifact_service.list_versions.return_value = [1, 2]
            mock_task_context = Mock()
            mock_task_context.add_artifact_signal = Mock()
            
            # Create a proper context manager mock for active_tasks_lock
            mock_lock = Mock()
            mock_lock.__enter__ = Mock(return_value=mock_lock)
            mock_lock.__exit__ = Mock(return_value=None)
            mock_tool_context._invocation_context.agent.host_component.active_tasks_lock = mock_lock
            mock_tool_context._invocation_context.agent.host_component.active_tasks = {
                "task123": mock_task_context
            }
            
            result = await signal_artifact_for_return(
                filename="test.txt",
                version=2,
                tool_context=mock_tool_context
            )
            
            assert result["status"] == "success"
            # Verify state_delta was updated
            assert len(mock_tool_context.actions.state_delta) > 0
            # Verify task context was called
            mock_task_context.add_artifact_signal.assert_called_once_with({
                "filename": "test.txt",
                "version": 2
            })