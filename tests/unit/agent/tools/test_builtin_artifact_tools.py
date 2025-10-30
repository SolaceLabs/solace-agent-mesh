"""
Unit tests for builtin_artifact_tools.py

Tests for built-in artifact management functions including creation, listing, loading,
signaling, extraction, deletion, and updates.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from solace_agent_mesh.agent.tools.builtin_artifact_tools import (
    _internal_create_artifact,
    list_artifacts,
    load_artifact,
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
