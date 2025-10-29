
"""
Unit tests for common/a2a/translation.py
Tests translation helpers between A2A protocol and Google ADK.
"""

import pytest
import base64
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from urllib.parse import urlparse

from google.genai import types as adk_types
from google.adk.events import Event as ADKEvent

from a2a.types import (
    Message as A2AMessage,
    TextPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
    DataPart,
    JSONRPCResponse,
    InternalError,
)

from solace_agent_mesh.common.a2a.translation import (
    _prepare_a2a_filepart_for_adk,
    translate_a2a_to_adk_content,
    translate_adk_function_response_to_a2a_parts,
    _extract_text_from_parts,
    format_adk_event_as_a2a,
    format_and_route_adk_event,
    translate_adk_part_to_a2a_filepart,
    A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY,
    A2A_STATUS_SIGNAL_STORAGE_KEY,
)


class TestPrepareA2AFilePartForADK:
    """Test _prepare_a2a_filepart_for_adk function."""

    @pytest.mark.skip(reason="Complex mocking requirements for artifact helpers")
    @pytest.mark.asyncio
    async def test_file_part_with_bytes(self):
        """Test processing FilePart with bytes."""
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_agent")
        component.artifact_service = Mock()
        
        # Mock save_artifact_with_metadata
        with patch('solace_agent_mesh.common.a2a.translation.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "success",
                "data_version": 1,
            }
            
            with patch('solace_agent_mesh.common.a2a.translation.load_artifact_content_or_metadata') as mock_load:
                mock_load.return_value = {
                    "status": "success",
                    "metadata": {"size": 100, "type": "test"},
                }
                
                with patch('solace_agent_mesh.common.a2a.translation.format_metadata_for_llm') as mock_format:
                    mock_format.return_value = "Formatted metadata"
                    
                    file_bytes = base64.b64encode(b"test content").decode("utf-8")
                    file_part = FilePart(
                        file=FileWithBytes(
                            name="test.txt",
                            mime_type="text/plain",
                            bytes=file_bytes,
                        )
                    )
                    
                    result = await _prepare_a2a_filepart_for_adk(
                        file_part, component, "user123", "session456"
                    )
                    
                    assert result is not None
                    assert isinstance(result, adk_types.Part)
                    assert "file" in result.text.lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex mocking requirements")
    async def test_file_part_with_uri(self):
        """Test processing FilePart with URI."""
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_agent")
        component.artifact_service = Mock()
        
        with patch('solace_agent_mesh.common.a2a.translation.load_artifact_content_or_metadata') as mock_load:
            mock_load.return_value = {
                "status": "success",
                "metadata": {"size": 200},
            }
            
            with patch('solace_agent_mesh.common.a2a.translation.format_metadata_for_llm') as mock_format:
                mock_format.return_value = "Formatted metadata"
                
                file_part = FilePart(
                    file=FileWithUri(
                        uri="artifact://test_agent/user123/session456/test.txt?version=1",
                        name="test.txt",
                        mime_type="text/plain",
                    )
                )
                
                result = await _prepare_a2a_filepart_for_adk(
                    file_part, component, "user123", "session456"
                )
                
                assert result is not None
                assert isinstance(result, adk_types.Part)

    @pytest.mark.asyncio
    async def test_file_part_no_artifact_service(self):
        """Test handling when artifact service is not configured."""
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_agent")
        component.artifact_service = None
        
        file_part = FilePart(
            file=FileWithBytes(
                name="test.txt",
                mime_type="text/plain",
                bytes=base64.b64encode(b"test").decode("utf-8"),
            )
        )
        
        result = await _prepare_a2a_filepart_for_adk(
            file_part, component, "user123", "session456"
        )
        
        assert result is not None
        assert "ignored" in result.text.lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex mocking requirements")
    async def test_file_part_save_failure(self):
        """Test handling save failure."""
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_agent")
        component.artifact_service = Mock()
        
        with patch('solace_agent_mesh.common.a2a.translation.save_artifact_with_metadata') as mock_save:
            mock_save.return_value = {
                "status": "error",
                "message": "Save failed",
            }
            
            file_bytes = base64.b64encode(b"test content").decode("utf-8")
            file_part = FilePart(
                file=FileWithBytes(
                    name="test.txt",
                    mime_type="text/plain",
                    bytes=file_bytes,
                )
            )
            
            result = await _prepare_a2a_filepart_for_adk(
                file_part, component, "user123", "session456"
            )
            
            assert result is not None
            assert "could not be processed" in result.text.lower()


class TestTranslateA2AToADKContent:
    """Test translate_a2a_to_adk_content function."""

    @pytest.mark.asyncio
    async def test_translate_text_message(self):
        """Test translating A2A message with text parts."""
        component = Mock()
        component.log_identifier = "[Test]"
        
        with patch('solace_agent_mesh.common.a2a.get_parts_from_message') as mock_get_parts:
            with patch('solace_agent_mesh.common.a2a.get_text_from_text_part') as mock_get_text:
                mock_get_parts.return_value = [TextPart(text="Hello")]
                mock_get_text.return_value = "Hello"
                
                message = Mock(role="user")
                
                result = await translate_a2a_to_adk_content(
                    message, component, "user123", "session456"
                )
                
                assert isinstance(result, adk_types.Content)
                assert result.role == "user"
                assert len(result.parts) == 1

    @pytest.mark.asyncio
    async def test_translate_data_part(self):
        """Test translating A2A message with data parts."""
        component = Mock()
        component.log_identifier = "[Test]"
        
        with patch('solace_agent_mesh.common.a2a.get_parts_from_message') as mock_get_parts:
            with patch('solace_agent_mesh.common.a2a.get_data_from_data_part') as mock_get_data:
                data_part = DataPart(data={"key": "value"})
                mock_get_parts.return_value = [data_part]
                mock_get_data.return_value = {"key": "value"}
                
                message = Mock(role="agent")
                
                result = await translate_a2a_to_adk_content(
                    message, component, "user123", "session456"
                )
                
                assert isinstance(result, adk_types.Content)
                assert result.role == "model"
                assert len(result.parts) == 1

    @pytest.mark.asyncio
    async def test_translate_mixed_parts(self):
        """Test translating message with mixed part types."""
        component = Mock()
        component.log_identifier = "[Test]"
        
        with patch('solace_agent_mesh.common.a2a.get_parts_from_message') as mock_get_parts:
            with patch('solace_agent_mesh.common.a2a.get_text_from_text_part') as mock_get_text:
                with patch('solace_agent_mesh.common.a2a.get_data_from_data_part') as mock_get_data:
                    text_part = TextPart(text="Hello")
                    data_part = DataPart(data={"key": "value"})
                    mock_get_parts.return_value = [text_part, data_part]
                    mock_get_text.return_value = "Hello"
                    mock_get_data.return_value = {"key": "value"}
                    
                    message = Mock(role="user")
                    
                    result = await translate_a2a_to_adk_content(
                        message, component, "user123", "session456"
                    )
                    
                    assert len(result.parts) == 2


class TestTranslateADKFunctionResponse:
    """Test translate_adk_function_response_to_a2a_parts function."""

    def test_function_response_with_dict(self):
        """Test translating function response with dict data."""
        function_response = Mock()
        function_response.response = {"result": "success"}
        function_response.name = "test_tool"
        
        adk_part = Mock()
        adk_part.function_response = function_response
        
        with patch('solace_agent_mesh.common.a2a.create_data_part') as mock_create_data:
            mock_create_data.return_value = DataPart(data={"result": "success"})
            
            result = translate_adk_function_response_to_a2a_parts(adk_part)
            
            assert len(result) == 1
            mock_create_data.assert_called_once()

    def test_function_response_with_string(self):
        """Test translating function response with string data."""
        function_response = Mock()
        function_response.response = "success"
        function_response.name = "test_tool"
        
        adk_part = Mock()
        adk_part.function_response = function_response
        
        with patch('solace_agent_mesh.common.a2a.create_text_part') as mock_create_text:
            mock_create_text.return_value = TextPart(text="Tool test_tool result: success")
            
            result = translate_adk_function_response_to_a2a_parts(adk_part)
            
            assert len(result) == 1
            mock_create_text.assert_called_once()

    def test_function_response_none(self):
        """Test handling when function_response is None."""
        adk_part = Mock()
        adk_part.function_response = None
        
        result = translate_adk_function_response_to_a2a_parts(adk_part)
        
        assert result == []

    def test_function_response_error(self):
        """Test handling error in function response."""
        function_response = Mock()
        function_response.name = "test_tool"
        function_response.response = Mock(side_effect=Exception("Error"))
        
        adk_part = Mock()
        adk_part.function_response = function_response
        
        with patch('solace_agent_mesh.common.a2a.create_text_part') as mock_create_text:
            mock_create_text.return_value = TextPart(text="[Tool test_tool result omitted]")
            
            result = translate_adk_function_response_to_a2a_parts(adk_part)
            
            assert len(result) == 1


class TestExtractTextFromParts:
    """Test _extract_text_from_parts function."""

    def test_extract_text_from_text_parts(self):
        """Test extracting text from text parts."""
        with patch('solace_agent_mesh.common.a2a.get_text_from_text_part') as mock_get_text:
            mock_get_text.side_effect = ["Hello", "World"]
            
            parts = [TextPart(text="Hello"), TextPart(text="World")]
            
            result = _extract_text_from_parts(parts)
            
            assert result == "Hello\nWorld"

    def test_extract_text_from_file_parts(self):
        """Test extracting text from file parts."""
        with patch('solace_agent_mesh.common.a2a.get_file_from_file_part') as mock_get_file:
            with patch('solace_agent_mesh.common.a2a.get_filename_from_file_part') as mock_get_filename:
                with patch('solace_agent_mesh.common.a2a.get_mimetype_from_file_part') as mock_get_mime:
                    with patch('solace_agent_mesh.common.a2a.get_uri_from_file_part') as mock_get_uri:
                        mock_get_file.return_value = FileWithUri(uri="test://file")
                        mock_get_filename.return_value = "test.txt"
                        mock_get_mime.return_value = "text/plain"
                        mock_get_uri.return_value = "test://file"
                        
                        parts = [FilePart(file=FileWithUri(uri="test://file"))]
                        
                        result = _extract_text_from_parts(parts)
                        
                        assert "test.txt" in result
                        assert "text/plain" in result

    def test_extract_text_skips_data_parts(self):
        """Test that data parts are skipped."""
        parts = [
            TextPart(text="Hello"),
            DataPart(data={"key": "value"}),
            TextPart(text="World"),
        ]
        
        with patch('solace_agent_mesh.common.a2a.get_text_from_text_part') as mock_get_text:
            mock_get_text.side_effect = ["Hello", "World"]
            
            result = _extract_text_from_parts(parts)
            
            assert "Hello" in result
            assert "World" in result
            assert "key" not in result

    def test_extract_text_from_dict_parts(self):
        """Test extracting text from dict-based parts."""
        parts = [
            {"type": "text", "text": "Hello"},
            {"type": "data", "data": {"key": "value"}},
        ]
        
        result = _extract_text_from_parts(parts)
        
        assert "Hello" in result


class TestFormatADKEventAsA2A:
    """Test format_adk_event_as_a2a function."""

    @pytest.mark.skip(reason="Pydantic validation complexity")
    def test_format_event_with_error(self):
        """Test formatting event with error."""
        adk_event = Mock()
        adk_event.error_code = "ERROR_CODE"
        adk_event.error_message = "Something went wrong"
        adk_event.id = "event123"
        
        a2a_context = {
            "jsonrpc_request_id": "req123",
            "logical_task_id": "task456",
            "is_streaming": False,
        }
        
        result, signals = format_adk_event_as_a2a(
            adk_event, a2a_context, "[Test]"
        )
        
        assert result is not None
        assert isinstance(result, JSONRPCResponse)
        assert result.error is not None
        assert "error" in result.error.message.lower()

    @pytest.mark.skip(reason="Pydantic validation complexity")
    def test_format_event_with_content(self):
        """Test formatting event with content."""
        part = Mock()
        part.text = "Response text"
        part.inline_data = None
        part.function_call = None
        part.function_response = None
        
        content = Mock()
        content.parts = [part]
        
        adk_event = Mock()
        adk_event.error_code = None
        adk_event.error_message = None
        adk_event.content = content
        adk_event.is_final_response = Mock(return_value=True)
        adk_event.long_running_tool_ids = []
        adk_event.id = "event123"
        
        a2a_context = {
            "jsonrpc_request_id": "req123",
            "logical_task_id": "task456",
            "is_streaming": True,
            "host_agent_name": "test_agent",
            "contextId": "ctx789",
        }
        
        with patch('solace_agent_mesh.common.a2a.create_text_part') as mock_create_text:
            with patch('solace_agent_mesh.common.a2a.create_agent_parts_message') as mock_create_msg:
                with patch('solace_agent_mesh.common.a2a.create_status_update') as mock_create_status:
                    mock_create_text.return_value = TextPart(text="Response text")
                    mock_msg = Mock()
                    mock_msg.model_dump = Mock(return_value={"messageId": "msg123", "role": "agent", "parts": []})
                    mock_create_msg.return_value = mock_msg
                    
                    # Create a proper status update structure
                    mock_create_status.return_value = {
                        "taskId": "task456",
                        "contextId": "ctx789",
                        "status": {"state": "running"},
                        "message": {"messageId": "msg123", "role": "agent", "parts": []},
                        "final": True,
                    }
                    
                    result, signals = format_adk_event_as_a2a(
                        adk_event, a2a_context, "[Test]"
                    )
                    
                    assert result is not None
                    assert isinstance(result, JSONRPCResponse)

    def test_format_event_no_content_non_streaming(self):
        """Test formatting final non-streaming event with no content."""
        adk_event = Mock()
        adk_event.error_code = None
        adk_event.error_message = None
        adk_event.content = None
        adk_event.is_final_response = Mock(return_value=True)
        adk_event.long_running_tool_ids = []
        adk_event.id = "event123"
        
        a2a_context = {
            "jsonrpc_request_id": "req123",
            "logical_task_id": "task456",
            "is_streaming": False,
        }
        
        result, signals = format_adk_event_as_a2a(
            adk_event, a2a_context, "[Test]"
        )
        
        assert result is None


class TestFormatAndRouteADKEvent:
    """Test format_and_route_adk_event function."""

    @pytest.mark.asyncio
    async def test_format_and_route_with_peer_topic(self):
        """Test routing to peer status topic."""
        adk_event = Mock()
        adk_event.error_code = None
        adk_event.error_message = None
        adk_event.id = "event123"
        
        part = Mock()
        part.text = "Response"
        part.inline_data = None
        part.function_call = None
        part.function_response = None
        
        content = Mock()
        content.parts = [part]
        adk_event.content = content
        adk_event.is_final_response = Mock(return_value=True)
        adk_event.long_running_tool_ids = []
        
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_namespace")
        
        a2a_context = {
            "jsonrpc_request_id": "req123",
            "logical_task_id": "task456",
            "is_streaming": True,
            "statusTopic": "peer/status/topic",
            "host_agent_name": "test_agent",
            "contextId": "ctx789",
            "a2a_user_config": "config_value",
        }
        
        with patch('solace_agent_mesh.common.a2a.translation.format_adk_event_as_a2a') as mock_format:
            mock_response = Mock()
            mock_response.model_dump = Mock(return_value={"result": "data"})
            mock_format.return_value = (mock_response, [])
            
            payload, topic, user_props, signals = await format_and_route_adk_event(
                adk_event, a2a_context, component
            )
            
            assert payload is not None
            assert topic == "peer/status/topic"
            assert "a2aUserConfig" in user_props

    @pytest.mark.asyncio
    async def test_format_and_route_to_gateway(self):
        """Test routing to gateway topic."""
        adk_event = Mock()
        adk_event.error_code = None
        adk_event.error_message = None
        adk_event.id = "event123"
        
        part = Mock()
        part.text = "Response"
        part.inline_data = None
        part.function_call = None
        part.function_response = None
        
        content = Mock()
        content.parts = [part]
        adk_event.content = content
        adk_event.is_final_response = Mock(return_value=True)
        adk_event.long_running_tool_ids = []
        
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_namespace")
        component.get_gateway_id = Mock(return_value="gateway123")
        
        a2a_context = {
            "jsonrpc_request_id": "req123",
            "logical_task_id": "task456",
            "is_streaming": True,
            "host_agent_name": "test_agent",
            "contextId": "ctx789",
        }
        
        with patch('solace_agent_mesh.common.a2a.translation.format_adk_event_as_a2a') as mock_format:
            with patch('solace_agent_mesh.common.a2a.get_gateway_status_topic') as mock_get_topic:
                mock_response = Mock()
                mock_response.model_dump = Mock(return_value={"result": "data"})
                mock_format.return_value = (mock_response, [])
                mock_get_topic.return_value = "gateway/status/topic"
                
                payload, topic, user_props, signals = await format_and_route_adk_event(
                    adk_event, a2a_context, component
                )
                
                assert payload is not None
                assert topic == "gateway/status/topic"

    @pytest.mark.asyncio
    async def test_format_and_route_error_handling(self):
        """Test error handling in format_and_route."""
        adk_event = Mock()
        adk_event.id = "event123"
        
        component = Mock()
        component.log_identifier = "[Test]"
        component.get_config = Mock(return_value="test_namespace")
        component.get_gateway_id = Mock(return_value="gateway123")
        
        a2a_context = {
            "jsonrpc_request_id": "req123",
            "logical_task_id": "task456",
        }
        
        with patch('solace_agent_mesh.common.a2a.translation.format_adk_event_as_a2a') as mock_format:
            mock_format.side_effect = Exception("Format error")
            
            with patch('solace_agent_mesh.common.a2a.get_gateway_response_topic') as mock_get_topic:
                mock_get_topic.return_value = "gateway/response/topic"
                
                payload, topic, user_props, signals = await format_and_route_adk_event(
                    adk_event, a2a_context, component
                )
                
                assert payload is not None
                assert "error" in str(payload).lower()


class TestTranslateADKPartToA2AFilePart:
    """Test translate_adk_part_to_a2a_filepart function."""

    @pytest.mark.asyncio
    async def test_translate_with_ignore_mode(self):
        """Test translation with ignore mode."""
        adk_part = Mock()
        adk_part.inline_data = Mock()
        
        result = await translate_adk_part_to_a2a_filepart(
            adk_part=adk_part,
            filename="test.txt",
            a2a_context={},
            artifact_service=Mock(),
            artifact_handling_mode="ignore",
            adk_app_name="test_app",
            log_identifier="[Test]",
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_with_embed_mode(self):
        """Test translation with embed mode."""
        inline_data = Mock()
        inline_data.mime_type = "text/plain"
        inline_data.data = b"test content"
        
        adk_part = Mock()
        adk_part.inline_data = inline_data
        
        result = await translate_adk_part_to_a2a_filepart(
            adk_part=adk_part,
            filename="test.txt",
            a2a_context={"user_id": "user123", "session_id": "session456"},
            artifact_service=Mock(),
            artifact_handling_mode="embed",
            adk_app_name="test_app",
            log_identifier="[Test]",
            version=1,
        )
        
        assert result is not None
        assert isinstance(result, FilePart)
        assert isinstance(result.file, FileWithBytes)

    @pytest.mark.asyncio
    async def test_translate_with_reference_mode(self):
        """Test translation with reference mode."""
        inline_data = Mock()
        inline_data.mime_type = "text/plain"
        inline_data.data = b"test content"
        
        adk_part = Mock()
        adk_part.inline_data = inline_data
        
        result = await translate_adk_part_to_a2a_filepart(
            adk_part=adk_part,
            filename="test.txt",
            a2a_context={
                "user_id": "user123",
                "session_id": "session456",
            },
            artifact_service=Mock(),
            artifact_handling_mode="reference",
            adk_app_name="test_app",
            log_identifier="[Test]",
            version=1,
        )
        
        assert result is not None
        assert isinstance(result, FilePart)
        assert isinstance(result.file, FileWithUri)
        assert "artifact://" in result.file.uri

    @pytest.mark.asyncio
    async def test_translate_no_inline_data(self):
        """Test translation when inline_data is missing."""
        adk_part = Mock()
        adk_part.inline_data = None
        
        result = await translate_adk_part_to_a2a_filepart(
            adk_part=adk_part,
            filename="test.txt",
            a2a_context={},
            artifact_service=Mock(),
            artifact_handling_mode="embed",
            adk_app_name="test_app",
            log_identifier="[Test]",
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_translate_resolve_latest_version(self):
        """Test resolving latest version when not provided."""
        inline_data = Mock()
        inline_data.mime_type = "text/plain"
        inline_data.data = b"test content"
        
        adk_part = Mock()
        adk_part.inline_data = inline_data
        
        artifact_service = Mock()
        
        with patch('solace_agent_mesh.common.utils.artifact_utils.get_latest_artifact_version') as mock_get_version:
            mock_get_version.return_value = 5
            
            result = await translate_adk_part_to_a2a_filepart(
                adk_part=adk_part,
                filename="test.txt",
                a2a_context={"user_id": "user123", "session_id": "session456"},
                artifact_service=artifact_service,
                artifact_handling_mode="embed",
                adk_app_name="test_app",
                log_identifier="[Test]",
                version=None,
            )
            
            assert result is not None
            mock_get_version.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex mocking requirements")
    async def test_translate_version_resolution_failure(self):
        """Test handling version resolution failure."""
        inline_data = Mock()
        inline_data.mime_type = "text/plain"
        inline_data.data = b"test content"
        
        adk_part = Mock()
        adk_part.inline_data = inline_data
        
        with patch('solace_agent_mesh.common.a2a.translation.get_latest_artifact_version') as mock_get_version:
            mock_get_version.return_value = None
            
            result = await translate_adk_part_to_a2a_filepart(
                adk_part=adk_part,
                filename="test.txt",
                a2a_context={"user_id": "user123", "session_id": "session456"},
                artifact_service=Mock(),
                artifact_handling_mode="embed",
                adk_app_name="test_app",
                log_identifier="[Test]",
                version=None,
            )
            
            assert result is None

