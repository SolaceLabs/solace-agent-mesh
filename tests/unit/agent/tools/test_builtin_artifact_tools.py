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
    artifact_search_and_replace_regex,
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


class TestArtifactSearchAndReplaceRegex:
    """Test cases for artifact_search_and_replace_regex function."""

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
        mock_context._invocation_context.agent.host_component.get_config = Mock(return_value=20)
        return mock_context

    @pytest.mark.asyncio
    async def test_literal_string_replacement_success(self, mock_tool_context):
        """Test successful literal string replacement."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            # Setup mocks
            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "hello world, hello universe"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="hello",
                replace_expression="hi",
                is_regexp=False,
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 2
            assert result["output_filename"] == "test.txt"
            assert result["output_version"] == 2

    @pytest.mark.asyncio
    async def test_regex_with_capture_groups(self, mock_tool_context):
        """Test regex replacement with capture groups."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "user123 and user456"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression=r"user(\d+)",
                replace_expression="id:$1",
                is_regexp=True,
                regexp_flags="g",
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 2
            assert result["replacements_made"] == 2

    @pytest.mark.asyncio
    async def test_regex_global_flag_behavior(self, mock_tool_context):
        """Test that global flag replaces all matches vs first match only."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo bar foo baz"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            # Without global flag - should replace only first match
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="foo",
                replace_expression="qux",
                is_regexp=True,
                regexp_flags="",
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 2
            assert result["replacements_made"] == 1  # Only first match replaced

    @pytest.mark.asyncio
    async def test_regex_case_insensitive_flag(self, mock_tool_context):
        """Test case-insensitive flag."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "Hello HELLO hello"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="hello",
                replace_expression="hi",
                is_regexp=True,
                regexp_flags="gi",  # global + case-insensitive
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 3
            assert result["replacements_made"] == 3

    @pytest.mark.asyncio
    async def test_regex_multiline_flag(self, mock_tool_context):
        """Test multiline flag for ^ and $ matching."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "line1\nline2\nline3"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression=r"^line",
                replace_expression="LINE",
                is_regexp=True,
                regexp_flags="gm",  # global + multiline
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 3

    @pytest.mark.asyncio
    async def test_regex_dotall_flag(self, mock_tool_context):
        """Test dotall flag for . matching newlines."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "start\nmiddle\nend"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression=r"start.+end",
                replace_expression="replaced",
                is_regexp=True,
                regexp_flags="s",  # dotall
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 1

    @pytest.mark.asyncio
    async def test_new_filename_creation(self, mock_tool_context):
        """Test creating a new artifact with different filename."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "Hello world"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 0  # New file, version 0
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="world",
                replace_expression="universe",
                is_regexp=False,
                new_filename="modified.txt",
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["source_filename"] == "test.txt"
            assert result["output_filename"] == "modified.txt"
            assert result["output_version"] == 0

    @pytest.mark.asyncio
    async def test_no_matches_found(self, mock_tool_context):
        """Test behavior when no matches are found."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "Hello world"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="foobar",
                replace_expression="baz",
                is_regexp=False,
                tool_context=mock_tool_context
            )

            assert result["status"] == "no_matches"
            assert result["match_count"] == 0
            assert "No matches found" in result["message"]

    @pytest.mark.asyncio
    async def test_artifact_not_found_error(self, mock_tool_context):
        """Test error when artifact doesn't exist."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session:

            mock_session.return_value = "session123"
            mock_load.return_value = {
                "status": "error",
                "message": "Artifact not found"
            }

            result = await artifact_search_and_replace_regex(
                filename="nonexistent.txt",
                search_expression="foo",
                replace_expression="bar",
                is_regexp=False,
                tool_context=mock_tool_context
            )

            assert result["status"] == "error"
            assert "Failed to load artifact" in result["message"]

    @pytest.mark.asyncio
    async def test_binary_artifact_error(self, mock_tool_context):
        """Test error when trying to search/replace in binary artifact."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = False

            binary_content = b'\x89PNG\r\n\x1a\n'
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": binary_content,
                "mime_type": "image/png",
                "version": 1
            }

            result = await artifact_search_and_replace_regex(
                filename="image.png",
                search_expression="foo",
                replace_expression="bar",
                is_regexp=False,
                tool_context=mock_tool_context
            )

            assert result["status"] == "error"
            assert "binary artifact" in result["message"].lower()
            assert "text-based" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_invalid_regex_pattern_error(self, mock_tool_context):
        """Test error when regex pattern is invalid."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "Hello world"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="[invalid(",  # Invalid regex
                replace_expression="bar",
                is_regexp=True,
                tool_context=mock_tool_context
            )

            assert result["status"] == "error"
            assert "Invalid regular expression" in result["message"]

    @pytest.mark.asyncio
    async def test_no_tool_context_error(self):
        """Test error when tool context is missing."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            search_expression="foo",
            replace_expression="bar",
            is_regexp=False,
            tool_context=None
        )

        assert result["status"] == "error"
        assert "ToolContext is missing" in result["message"]

    @pytest.mark.asyncio
    async def test_empty_search_expression_error(self, mock_tool_context):
        """Test error when search expression is empty."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            search_expression="",
            replace_expression="bar",
            is_regexp=False,
            tool_context=mock_tool_context
        )

        assert result["status"] == "error"
        assert "search_expression cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_new_filename_error(self, mock_tool_context):
        """Test error when new_filename contains invalid characters."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            search_expression="foo",
            replace_expression="bar",
            is_regexp=False,
            new_filename="../unsafe.txt",
            tool_context=mock_tool_context
        )

        assert result["status"] == "error"
        assert "Invalid new_filename" in result["message"]

    @pytest.mark.asyncio
    async def test_custom_description_preserved(self, mock_tool_context):
        """Test that custom description is included in metadata."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "Hello world"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                search_expression="world",
                replace_expression="universe",
                is_regexp=False,
                new_description="Custom description for modified file",
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            # Check that save was called with metadata containing the description
            call_args = mock_save.call_args
            assert call_args is not None
            metadata = call_args.kwargs['metadata_dict']
            assert metadata['description'] == "Custom description for modified file"

    @pytest.mark.asyncio
    async def test_regex_escaped_dollar_sign_in_replacement(self, mock_tool_context):
        """Test that $$ in replacement expression becomes a literal $."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            # CSV-like content with numbers at end of lines
            original_content = "item,100\nproduct,200\nservice,300"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            # Capture what was actually saved
            saved_content = None
            def capture_save(**kwargs):
                nonlocal saved_content
                saved_content = kwargs['content_bytes'].decode('utf-8')
                return {"status": "success", "data_version": 2}

            mock_save.side_effect = capture_save

            # Test the problematic pattern: ,$$$1 should become ,$ followed by the number
            result = await artifact_search_and_replace_regex(
                filename="test.csv",
                search_expression=r",(\d+)$",  # Match comma followed by digits at end of line
                replace_expression=",$$$1",     # Should become ,$ followed by the captured digits
                is_regexp=True,
                regexp_flags="gm",  # global + multiline
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["match_count"] == 3
            assert result["replacements_made"] == 3

            # Verify the actual content has literal $ before each number
            assert saved_content == "item,$100\nproduct,$200\nservice,$300"

    @pytest.mark.asyncio
    async def test_regex_no_matches_with_multiline_flag(self, mock_tool_context):
        """Test that multiline flag works correctly and reports no matches when pattern doesn't match."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            # CSV with text values (no numbers)
            original_content = "col1,col2\nrow_6_col_1,row_6_col_2\nrow_7_col_1,row_7_col_2"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/csv",
                "version": 1
            }

            # Pattern looking for digits at end of line - won't match text values
            result = await artifact_search_and_replace_regex(
                filename="test.csv",
                search_expression=r",(\d+)$",  # Looks for digits, but CSV has text
                replace_expression=",$$$1",
                is_regexp=True,
                regexp_flags="gm",  # global + multiline
                tool_context=mock_tool_context
            )

            # Should report no matches
            assert result["status"] == "no_matches"
            assert result["match_count"] == 0
            assert "No matches found" in result["message"]
            assert "not modified" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_batch_replacements_success(self, mock_tool_context):
        """Test successful batch replacements with multiple operations."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo bar baz qux"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            saved_content = None
            def capture_save(**kwargs):
                nonlocal saved_content
                saved_content = kwargs['content_bytes'].decode('utf-8')
                return {"status": "success", "data_version": 2}

            mock_save.side_effect = capture_save

            # Multiple sequential replacements
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "foo", "replace": "FOO", "is_regexp": False},
                    {"search": "bar", "replace": "BAR", "is_regexp": False},
                    {"search": "baz", "replace": "BAZ", "is_regexp": False}
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["total_replacements"] == 3
            assert result["total_matches"] == 3
            assert len(result["replacement_results"]) == 3

            # Verify all replacements succeeded
            for r in result["replacement_results"]:
                assert r["status"] == "success"
                assert r["match_count"] == 1

            # Verify final content has all replacements applied
            assert saved_content == "FOO BAR BAZ qux"

    @pytest.mark.asyncio
    async def test_batch_replacements_sequential_processing(self, mock_tool_context):
        """Test that batch replacements are applied sequentially (each sees previous results)."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "hello hello hello"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            saved_content = None
            def capture_save(**kwargs):
                nonlocal saved_content
                saved_content = kwargs['content_bytes'].decode('utf-8')
                return {"status": "success", "data_version": 2}

            mock_save.side_effect = capture_save

            # First replacement: hello -> hi (all 3 instances)
            # Second replacement: hi -> HI (should find 3 instances of "hi" from first replacement)
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "hello", "replace": "hi", "is_regexp": False},
                    {"search": "hi", "replace": "HI", "is_regexp": False}
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["replacement_results"][0]["match_count"] == 3
            assert result["replacement_results"][1]["match_count"] == 3  # Proves sequential processing
            assert saved_content == "HI HI HI"

    @pytest.mark.asyncio
    async def test_batch_replacements_atomic_rollback_on_error(self, mock_tool_context):
        """Test that batch replacements rollback all changes if any operation fails."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo bar baz"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            # Second replacement has invalid regex
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "foo", "replace": "FOO", "is_regexp": False},
                    {"search": "[invalid(", "replace": "BAR", "is_regexp": True},  # Invalid regex
                    {"search": "baz", "replace": "BAZ", "is_regexp": False}
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "error"
            assert "Batch replacement failed" in result["message"]
            assert result["failed_replacement"]["index"] == 1
            assert "Invalid regular expression" in result["failed_replacement"]["error"]

            # First replacement should be marked as success
            assert result["replacement_results"][0]["status"] == "success"
            # Second replacement should be marked as error
            assert result["replacement_results"][1]["status"] == "error"
            # Third replacement should be skipped
            assert result["replacement_results"][2]["status"] == "skipped"

            # Save should not have been called (rollback)
            mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_replacements_no_matches_error(self, mock_tool_context):
        """Test that batch rollback occurs when no matches found."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo bar baz"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            # Second replacement won't find any matches
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "foo", "replace": "FOO", "is_regexp": False},
                    {"search": "notfound", "replace": "NOTFOUND", "is_regexp": False},
                    {"search": "baz", "replace": "BAZ", "is_regexp": False}
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "error"
            assert "Batch replacement failed" in result["message"]
            assert result["failed_replacement"]["index"] == 1
            assert "No matches found" in result["failed_replacement"]["error"]

            # Save should not have been called (rollback)
            mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_replacements_multiple_matches_without_global_flag(self, mock_tool_context):
        """Test that batch mode errors on multiple matches without global flag."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo foo foo"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            # Regex without global flag but multiple matches - should error in batch mode
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "foo", "replace": "bar", "is_regexp": True, "regexp_flags": ""}  # No 'g' flag
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "error"
            assert "Multiple matches found" in result["failed_replacement"]["error"]
            assert "global flag 'g' not set" in result["failed_replacement"]["error"]

            # Save should not have been called (rollback)
            mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_replacements_with_regex_and_literal_mixed(self, mock_tool_context):
        """Test batch replacements with mix of regex and literal operations."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "user123 user456 and hello world"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            saved_content = None
            def capture_save(**kwargs):
                nonlocal saved_content
                saved_content = kwargs['content_bytes'].decode('utf-8')
                return {"status": "success", "data_version": 2}

            mock_save.side_effect = capture_save

            # Mix of regex with capture groups and literal replacement
            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": r"user(\d+)", "replace": "id:$1", "is_regexp": True, "regexp_flags": "g"},
                    {"search": "hello", "replace": "hi", "is_regexp": False}
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["total_replacements"] == 2
            assert result["replacement_results"][0]["match_count"] == 2
            assert result["replacement_results"][1]["match_count"] == 1
            assert saved_content == "id:123 id:456 and hi world"

    @pytest.mark.asyncio
    async def test_batch_replacements_empty_array_error(self, mock_tool_context):
        """Test error when replacements array is empty."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            replacements=[],
            tool_context=mock_tool_context
        )

        assert result["status"] == "error"
        assert "non-empty array" in result["message"]

    @pytest.mark.asyncio
    async def test_batch_replacements_missing_required_fields(self, mock_tool_context):
        """Test error when replacement entry is missing required fields."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            replacements=[
                {"search": "foo", "replace": "bar"}  # Missing 'is_regexp'
            ],
            tool_context=mock_tool_context
        )

        assert result["status"] == "error"
        assert "missing required fields" in result["message"]
        assert "is_regexp" in result["message"]

    @pytest.mark.asyncio
    async def test_batch_replacements_invalid_type(self, mock_tool_context):
        """Test error when replacement entry is not a dictionary."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            replacements=["not a dict"],
            tool_context=mock_tool_context
        )

        assert result["status"] == "error"
        assert "must be a dictionary" in result["message"]

    @pytest.mark.asyncio
    async def test_batch_and_single_mode_mutually_exclusive(self, mock_tool_context):
        """Test error when both replacements array and single search_expression provided."""
        result = await artifact_search_and_replace_regex(
            filename="test.txt",
            search_expression="foo",
            replace_expression="bar",
            replacements=[
                {"search": "baz", "replace": "qux", "is_regexp": False}
            ],
            tool_context=mock_tool_context
        )

        assert result["status"] == "error"
        assert "Cannot provide both" in result["message"]

    @pytest.mark.asyncio
    async def test_batch_replacements_with_new_filename(self, mock_tool_context):
        """Test batch replacements saving to a new filename."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo bar baz"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 0  # New file
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "foo", "replace": "FOO", "is_regexp": False},
                    {"search": "bar", "replace": "BAR", "is_regexp": False}
                ],
                new_filename="modified.txt",
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"
            assert result["source_filename"] == "test.txt"
            assert result["output_filename"] == "modified.txt"
            assert result["output_version"] == 0

    @pytest.mark.asyncio
    async def test_batch_replacements_metadata_includes_batch_info(self, mock_tool_context):
        """Test that batch replacement metadata includes batch-specific information."""
        with patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.load_artifact_content_or_metadata') as mock_load, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.save_artifact_with_metadata') as mock_save, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.get_original_session_id') as mock_session, \
             patch('solace_agent_mesh.agent.tools.builtin_artifact_tools.is_text_based_file') as mock_is_text:

            mock_session.return_value = "session123"
            mock_is_text.return_value = True

            original_content = "foo bar baz"
            mock_load.return_value = {
                "status": "success",
                "raw_bytes": original_content.encode("utf-8"),
                "mime_type": "text/plain",
                "version": 1
            }

            mock_save.return_value = {
                "status": "success",
                "data_version": 2
            }

            result = await artifact_search_and_replace_regex(
                filename="test.txt",
                replacements=[
                    {"search": "foo", "replace": "FOO", "is_regexp": False},
                    {"search": "bar", "replace": "BAR", "is_regexp": False}
                ],
                tool_context=mock_tool_context
            )

            assert result["status"] == "success"

            # Check that save was called with batch metadata
            call_args = mock_save.call_args
            assert call_args is not None
            metadata = call_args.kwargs['metadata_dict']
            assert "batch" in metadata['source'].lower()
            assert metadata['total_replacements'] == 2
            assert metadata['total_matches'] == 2
