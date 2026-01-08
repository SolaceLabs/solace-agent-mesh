"""Unit tests for TaskLoggerService helper methods."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import copy

from solace_agent_mesh.gateway.http_sse.services.task_logger_service import TaskLoggerService


class TestTaskLoggerServiceInit:
    """Tests for TaskLoggerService initialization."""
    
    def test_init_with_session_factory(self):
        """Test initialization with session factory."""
        mock_session_factory = Mock()
        config = {"enabled": True}
        
        service = TaskLoggerService(mock_session_factory, config)
        
        assert service.session_factory == mock_session_factory
        assert service.config == config
        assert service.log_identifier == "[TaskLoggerService]"
    
    def test_init_without_session_factory(self):
        """Test initialization without session factory."""
        config = {"enabled": True}
        
        service = TaskLoggerService(None, config)
        
        assert service.session_factory is None
        assert service.config == config


class TestShouldLogEvent:
    """Tests for _should_log_event method."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(None, {})
    
    def test_should_log_event_default(self, service):
        """Test default behavior logs all events."""
        result = service._should_log_event("some/topic", Mock())
        assert result is True
    
    def test_should_not_log_status_when_disabled(self):
        """Test status events are not logged when disabled."""
        service = TaskLoggerService(None, {"log_status_updates": False})
        
        result = service._should_log_event("some/status/topic", Mock())
        assert result is False
    
    def test_should_log_status_when_enabled(self):
        """Test status events are logged when enabled."""
        service = TaskLoggerService(None, {"log_status_updates": True})
        
        result = service._should_log_event("some/status/topic", Mock())
        assert result is True
    
    def test_should_not_log_artifact_when_disabled(self):
        """Test artifact events are not logged when disabled."""
        from a2a.types import TaskArtifactUpdateEvent
        
        service = TaskLoggerService(None, {"log_artifact_events": False})
        mock_event = Mock(spec=TaskArtifactUpdateEvent)
        
        result = service._should_log_event("some/topic", mock_event)
        assert result is False
    
    def test_should_log_artifact_when_enabled(self):
        """Test artifact events are logged when enabled."""
        from a2a.types import TaskArtifactUpdateEvent
        
        service = TaskLoggerService(None, {"log_artifact_events": True})
        mock_event = Mock(spec=TaskArtifactUpdateEvent)
        
        result = service._should_log_event("some/topic", mock_event)
        assert result is True


class TestGetFinalStatus:
    """Tests for _get_final_status method."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(None, {})
    
    def test_get_final_status_from_task(self, service):
        """Test extracting final status from A2ATask."""
        from a2a.types import Task as A2ATask, TaskStatus, TaskState
        
        mock_task = Mock(spec=A2ATask)
        mock_task.status = Mock(spec=TaskStatus)
        mock_task.status.state = TaskState.completed
        
        result = service._get_final_status(mock_task)
        assert result == "completed"
    
    def test_get_final_status_from_error(self, service):
        """Test extracting final status from JSONRPCError."""
        from a2a.types import JSONRPCError
        
        mock_error = Mock(spec=JSONRPCError)
        
        result = service._get_final_status(mock_error)
        assert result == "failed"
    
    def test_get_final_status_from_other(self, service):
        """Test that other event types return None."""
        result = service._get_final_status(Mock())
        assert result is None


class TestExtractInitialText:
    """Tests for _extract_initial_text method."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(None, {})
    
    def test_extract_initial_text_from_request(self, service):
        """Test extracting initial text from A2ARequest."""
        from a2a.types import A2ARequest
        
        mock_request = Mock(spec=A2ARequest)
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.a2a') as mock_a2a:
            mock_message = Mock()
            mock_a2a.get_message_from_send_request.return_value = mock_message
            mock_a2a.get_text_from_message.return_value = "Hello, world!"
            
            result = service._extract_initial_text(mock_request)
            
            assert result == "Hello, world!"
            mock_a2a.get_message_from_send_request.assert_called_once_with(mock_request)
            mock_a2a.get_text_from_message.assert_called_once_with(mock_message)
    
    def test_extract_initial_text_no_message(self, service):
        """Test extracting initial text when no message is found."""
        from a2a.types import A2ARequest
        
        mock_request = Mock(spec=A2ARequest)
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.a2a') as mock_a2a:
            mock_a2a.get_message_from_send_request.return_value = None
            
            result = service._extract_initial_text(mock_request)
            
            assert result is None
    
    def test_extract_initial_text_non_request(self, service):
        """Test extracting initial text from non-request event."""
        result = service._extract_initial_text(Mock())
        assert result is None
    
    def test_extract_initial_text_exception(self, service):
        """Test extracting initial text handles exceptions."""
        from a2a.types import A2ARequest
        
        mock_request = Mock(spec=A2ARequest)
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.a2a') as mock_a2a:
            mock_a2a.get_message_from_send_request.side_effect = Exception("Parse error")
            
            result = service._extract_initial_text(mock_request)
            
            assert result is None


class TestSanitizePayload:
    """Tests for _sanitize_payload method."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(None, {})
    
    def test_sanitize_payload_no_file_parts(self, service):
        """Test sanitizing payload without file parts."""
        payload = {
            "method": "send",
            "params": {
                "message": {
                    "parts": [
                        {"kind": "text", "text": "Hello"}
                    ]
                }
            }
        }
        
        result = service._sanitize_payload(payload)
        
        assert result == payload
    
    def test_sanitize_payload_strips_large_file(self):
        """Test sanitizing payload strips large file content."""
        service = TaskLoggerService(None, {"max_file_part_size_bytes": 100})
        
        # Create a large base64 string (more than 100 bytes when decoded)
        large_content = "A" * 200  # ~150 bytes when decoded
        
        payload = {
            "params": {
                "message": {
                    "parts": [
                        {
                            "file": {
                                "bytes": large_content,
                                "name": "large_file.txt"
                            }
                        }
                    ]
                }
            }
        }
        
        result = service._sanitize_payload(payload)
        
        # The file bytes should be replaced with a message
        file_bytes = result["params"]["message"]["parts"][0]["file"]["bytes"]
        assert "Content stripped" in file_bytes
    
    def test_sanitize_payload_keeps_small_file(self):
        """Test sanitizing payload keeps small file content."""
        service = TaskLoggerService(None, {"max_file_part_size_bytes": 1000})
        
        small_content = "SGVsbG8="  # "Hello" in base64
        
        payload = {
            "params": {
                "message": {
                    "parts": [
                        {
                            "file": {
                                "bytes": small_content,
                                "name": "small_file.txt"
                            }
                        }
                    ]
                }
            }
        }
        
        result = service._sanitize_payload(payload)
        
        # The file bytes should be unchanged
        file_bytes = result["params"]["message"]["parts"][0]["file"]["bytes"]
        assert file_bytes == small_content
    
    def test_sanitize_payload_skips_file_parts_when_disabled(self):
        """Test sanitizing payload skips file parts when logging is disabled."""
        service = TaskLoggerService(None, {"log_file_parts": False})
        
        payload = {
            "params": {
                "message": {
                    "parts": [
                        {"kind": "text", "text": "Hello"},
                        {"file": {"bytes": "SGVsbG8=", "name": "file.txt"}}
                    ]
                }
            }
        }
        
        result = service._sanitize_payload(payload)
        
        # File part should be removed
        parts = result["params"]["message"]["parts"]
        assert len(parts) == 1
        assert parts[0]["kind"] == "text"
    
    def test_sanitize_payload_preserves_original(self, service):
        """Test that sanitizing doesn't modify the original payload."""
        payload = {
            "params": {
                "message": {
                    "parts": [
                        {"kind": "text", "text": "Hello"}
                    ]
                }
            }
        }
        original = copy.deepcopy(payload)
        
        service._sanitize_payload(payload)
        
        assert payload == original


class TestInferEventDetails:
    """Tests for _infer_event_details method."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(None, {})
    
    def test_infer_details_from_request(self, service):
        """Test inferring details from A2ARequest."""
        from a2a.types import A2ARequest
        
        mock_request = Mock(spec=A2ARequest)
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.a2a') as mock_a2a:
            mock_a2a.get_request_id.return_value = "task-123"
            
            direction, task_id, user_id = service._infer_event_details(
                "some/topic", mock_request, {"userId": "user-456"}
            )
            
            assert direction == "request"
            assert task_id == "task-123"
            assert user_id == "user-456"
    
    def test_infer_details_from_task(self, service):
        """Test inferring details from A2ATask."""
        from a2a.types import Task as A2ATask
        
        mock_task = Mock(spec=A2ATask)
        mock_task.id = "task-789"
        
        direction, task_id, user_id = service._infer_event_details(
            "some/topic", mock_task, {"userId": "user-123"}
        )
        
        assert direction == "response"
        assert task_id == "task-789"
        assert user_id == "user-123"
    
    def test_infer_details_from_status_update(self, service):
        """Test inferring details from TaskStatusUpdateEvent."""
        from a2a.types import TaskStatusUpdateEvent
        
        mock_event = Mock(spec=TaskStatusUpdateEvent)
        mock_event.task_id = "task-status-123"
        
        direction, task_id, user_id = service._infer_event_details(
            "some/topic", mock_event, {}
        )
        
        assert direction == "status"
        assert task_id == "task-status-123"
    
    def test_infer_details_from_error(self, service):
        """Test inferring details from JSONRPCError."""
        from a2a.types import JSONRPCError
        
        mock_error = Mock(spec=JSONRPCError)
        mock_error.data = {"taskId": "task-error-123"}
        
        direction, task_id, user_id = service._infer_event_details(
            "some/topic", mock_error, {}
        )
        
        assert direction == "error"
        assert task_id == "task-error-123"
    
    def test_infer_details_user_id_from_a2a_config(self, service):
        """Test inferring user_id from a2aUserConfig."""
        from a2a.types import A2ARequest
        
        mock_request = Mock(spec=A2ARequest)
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.a2a') as mock_a2a:
            mock_a2a.get_request_id.return_value = "task-123"
            
            user_props = {
                "a2aUserConfig": {
                    "user_profile": {
                        "id": "user-from-config"
                    }
                }
            }
            
            direction, task_id, user_id = service._infer_event_details(
                "some/topic", mock_request, user_props
            )
            
            assert user_id == "user-from-config"
    
    def test_infer_details_with_none_user_props(self, service):
        """Test inferring details with None user_props."""
        from a2a.types import A2ARequest
        
        mock_request = Mock(spec=A2ARequest)
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.a2a') as mock_a2a:
            mock_a2a.get_request_id.return_value = "task-123"
            
            direction, task_id, user_id = service._infer_event_details(
                "some/topic", mock_request, None
            )
            
            assert direction == "request"
            assert task_id == "task-123"
            assert user_id is None


class TestParseA2AEvent:
    """Tests for _parse_a2a_event method."""
    
    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(None, {})
    
    def test_parse_discovery_topic_returns_none(self, service):
        """Test that discovery topics return None."""
        result = service._parse_a2a_event("/discovery/agentcards", {})
        assert result is None
    
    def test_parse_trust_topic_returns_none(self, service):
        """Test that trust topics return None."""
        result = service._parse_a2a_event("/trust/something", {})
        assert result is None
    
    def test_parse_request_payload(self, service):
        """Test parsing a request payload."""
        payload = {
            "jsonrpc": "2.0",
            "id": "123",
            "method": "message/send",
            "params": {
                "message": {
                    "messageId": "msg-123",
                    "role": "user",
                    "parts": [
                        {"kind": "text", "text": "Hello"}
                    ]
                }
            }
        }
        
        result = service._parse_a2a_event("some/topic", payload)
        
        from a2a.types import A2ARequest
        assert isinstance(result, A2ARequest)
    
    def test_parse_invalid_payload_returns_none(self, service):
        """Test that invalid payloads return None."""
        payload = {"invalid": "data"}
        
        result = service._parse_a2a_event("some/topic", payload)
        
        assert result is None
    
    def test_parse_malformed_payload_returns_none(self, service):
        """Test that malformed payloads return None."""
        payload = {"method": "invalid", "params": "not_a_dict"}
        
        result = service._parse_a2a_event("some/topic", payload)
        
        assert result is None


class TestLogEventDisabled:
    """Tests for log_event when logging is disabled."""
    
    def test_log_event_disabled_returns_early(self):
        """Test that log_event returns early when disabled."""
        service = TaskLoggerService(Mock(), {"enabled": False})
        
        # Should not raise any errors
        service.log_event({"topic": "test", "payload": {}})
    
    def test_log_event_no_session_factory_logs_warning(self):
        """Test that log_event logs warning when no session factory."""
        service = TaskLoggerService(None, {"enabled": True})
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.log') as mock_log:
            service.log_event({"topic": "test", "payload": {}})
            
            mock_log.warning.assert_called()
    
    def test_log_event_missing_topic_or_payload(self):
        """Test that log_event handles missing topic or payload."""
        service = TaskLoggerService(Mock(), {"enabled": True})
        
        with patch('solace_agent_mesh.gateway.http_sse.services.task_logger_service.log') as mock_log:
            service.log_event({"topic": None, "payload": {}})
            mock_log.warning.assert_called()
            
            service.log_event({"topic": "test", "payload": None})
            assert mock_log.warning.call_count >= 2
    
    def test_log_event_discovery_topic_ignored(self):
        """Test that discovery topics are ignored."""
        mock_session_factory = Mock()
        service = TaskLoggerService(mock_session_factory, {"enabled": True})
        
        service.log_event({"topic": "/discovery/agentcards", "payload": {}})
        
        # Session factory should not be called
        mock_session_factory.assert_not_called()
