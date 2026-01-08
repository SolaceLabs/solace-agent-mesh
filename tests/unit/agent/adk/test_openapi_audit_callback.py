"""Tests for OpenAPI audit logging callbacks."""
import pytest
import json
import tempfile
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from solace_agent_mesh.agent.adk.openapi_audit_callback import (
    OpenAPIAuditLogger,
    audit_log_openapi_tool_invocation_start,
    audit_log_openapi_tool_execution_result,
    _extract_auth_method,
    _extract_base_url,
    _extract_http_method,
)


@pytest.fixture
def mock_component():
    """Create a mock SamAgentComponent."""
    component = Mock()
    component.agent_name = "TestAgent"
    component.namespace = "test"
    component.log_identifier = "[TestAgent]"
    component.get_config = Mock(side_effect=lambda key, default=None: {
        "openapi_audit_enabled": True,
        "openapi_audit_log_file": "/tmp/test_audit.jsonl",
    }.get(key, default))
    return component


@pytest.fixture
def mock_openapi_tool():
    """Create a mock OpenAPI tool."""
    tool = Mock()
    tool.__class__.__name__ = "OpenAPIToolset"
    tool.name = "TestAPI"
    tool.specification_url = "https://api.example.com/openapi.json"
    tool._auth = Mock(type="apikey")
    tool._base_url = "https://api.example.com"
    tool._config = {
        "auth": {"type": "apikey"},
        "base_url": "https://api.example.com"
    }
    return tool


@pytest.fixture
def mock_tool_context():
    """Create a mock ToolContext."""
    context = Mock()
    context.function_call_id = "fc_test123"
    context.state = {}

    # Mock invocation context
    invocation_context = Mock()
    session = Mock()
    session.id = "sess_abc123"
    session.user_id = "user_xyz789"
    invocation_context.session = session
    context._invocation_context = invocation_context

    return context


class TestExtractHelpers:
    """Test helper functions for extracting tool metadata."""

    def test_extract_auth_method_from_auth_attribute(self):
        """Test extracting auth method from _auth attribute."""
        tool = Mock()
        auth = Mock()
        auth.type = "bearer"
        tool._auth = auth

        result = _extract_auth_method(tool)
        assert result == "bearer"

    def test_extract_auth_method_from_class_name(self):
        """Test inferring auth method from class name."""
        tool = Mock()
        auth = Mock()
        auth.__class__.__name__ = "ApiKeyAuth"
        delattr(auth, 'type')
        tool._auth = auth

        result = _extract_auth_method(tool)
        assert result == "apikey"

    def test_extract_auth_method_from_config(self):
        """Test extracting auth method from _config."""
        tool = Mock()
        tool._auth = None
        tool._config = {"auth": {"type": "basic"}}

        result = _extract_auth_method(tool)
        assert result == "basic"

    def test_extract_auth_method_none(self):
        """Test returns None when no auth configured."""
        tool = Mock()
        tool._auth = None
        tool._config = {}

        result = _extract_auth_method(tool)
        assert result is None

    def test_extract_base_url_from_attribute(self):
        """Test extracting base URL from base_url attribute."""
        tool = Mock()
        tool.base_url = "https://api.example.com"

        result = _extract_base_url(tool)
        assert result == "https://api.example.com"

    def test_extract_base_url_from_private_attribute(self):
        """Test extracting base URL from _base_url attribute."""
        tool = Mock()
        delattr(tool, 'base_url')
        tool._base_url = "https://api.example.com"

        result = _extract_base_url(tool)
        assert result == "https://api.example.com"

    def test_extract_base_url_from_config(self):
        """Test extracting base URL from _config."""
        tool = Mock()
        delattr(tool, 'base_url')
        tool._base_url = None
        tool._config = {"base_url": "https://api.example.com"}

        result = _extract_base_url(tool)
        assert result == "https://api.example.com"

    def test_extract_http_method(self):
        """Test extracting HTTP method from args."""
        args = {"http_method": "POST"}
        assert _extract_http_method(args) == "POST"

        args = {"method": "GET"}
        assert _extract_http_method(args) == "GET"

        args = {"request_method": "PUT"}
        assert _extract_http_method(args) == "PUT"

        args = {}
        assert _extract_http_method(args) is None


class TestOpenAPIAuditLogger:
    """Test OpenAPIAuditLogger class."""

    def test_init(self, mock_component):
        """Test logger initialization."""
        logger = OpenAPIAuditLogger(mock_component)

        assert logger.component == mock_component
        assert logger.log_identifier == "[OpenAPIConnectorAudit]"

    def test_log_audit_event_creates_entry(self, mock_component, tmp_path):
        """Test that log_audit_event creates properly formatted entry."""
        # Use temp file for testing
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        logger = OpenAPIAuditLogger(mock_component)

        logger.log_audit_event(
            event_type="openapi_invocation_start",
            tool_name="TestAPI",
            operation_id="testOperation",
            tool_uri="https://api.test.com",
            http_method="POST",
            actor="user@example.com",
            correlation_id="corr123",
            auth_method="apikey",
        )

        # Verify file was created and contains entry
        assert audit_file.exists()
        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "openapi_invocation_start"
        assert entry["tool_name"] == "TestAPI"
        assert entry["operation_id"] == "testOperation"
        assert entry["tool_uri"] == "https://api.test.com"
        assert entry["action"] == "POST: testOperation"
        assert entry["actor"] == "user@example.com"
        assert entry["correlation_id"] == "corr123"
        assert entry["auth_method"] == "apikey"
        assert entry["agent_name"] == "TestAgent"
        assert entry["namespace"] == "test"

    def test_log_audit_event_with_latency(self, mock_component, tmp_path):
        """Test logging with latency and status code."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        logger = OpenAPIAuditLogger(mock_component)

        logger.log_audit_event(
            event_type="openapi_execution_complete",
            tool_name="TestAPI",
            operation_id="testOp",
            tool_uri="https://api.test.com",
            http_method="GET",
            actor="user@example.com",
            correlation_id="corr123",
            status_code=200,
            latency_ms=450,
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["status_code"] == 200
        assert entry["latency_ms"] == 450
        assert entry["request_status"] == "success"

    def test_log_audit_event_with_error(self, mock_component, tmp_path):
        """Test logging with error details."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        logger = OpenAPIAuditLogger(mock_component)

        logger.log_audit_event(
            event_type="openapi_execution_complete",
            tool_name="TestAPI",
            operation_id="failOp",
            tool_uri="https://api.test.com",
            http_method="POST",
            actor="user@example.com",
            correlation_id="corr123",
            error_type="api_error",
            error_message="Connection timeout",
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["error_type"] == "api_error"
        assert entry["error_message"] == "Connection timeout"
        assert entry["request_status"] == "failure"

    def test_request_status_determination(self, mock_component, tmp_path):
        """Test request_status is determined correctly based on status_code."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        logger = OpenAPIAuditLogger(mock_component)

        # Test success (2xx)
        logger.log_audit_event(
            event_type="openapi_execution_complete",
            tool_name="API",
            operation_id="op",
            tool_uri="https://api.test.com",
            http_method="GET",
            actor="user",
            correlation_id="c1",
            status_code=201,
        )

        # Test error (4xx/5xx)
        logger.log_audit_event(
            event_type="openapi_execution_complete",
            tool_name="API",
            operation_id="op",
            tool_uri="https://api.test.com",
            http_method="GET",
            actor="user",
            correlation_id="c2",
            status_code=404,
        )

        # Test failure (error_type present)
        logger.log_audit_event(
            event_type="openapi_execution_complete",
            tool_name="API",
            operation_id="op",
            tool_uri="https://api.test.com",
            http_method="GET",
            actor="user",
            correlation_id="c3",
            error_type="timeout",
        )

        with open(audit_file) as f:
            entries = [json.loads(line) for line in f]

        assert entries[0]["request_status"] == "success"
        assert entries[1]["request_status"] == "error"
        assert entries[2]["request_status"] == "failure"


class TestAuditCallbacks:
    """Test audit callback functions."""

    def test_invocation_start_callback_non_openapi_tool(self, mock_component, mock_tool_context):
        """Test callback skips non-OpenAPI tools."""
        tool = Mock()
        tool.__class__.__name__ = "RegularTool"
        delattr(tool, 'specification_url')

        # Should not raise, just return early
        audit_log_openapi_tool_invocation_start(
            tool, {}, mock_tool_context, mock_component
        )

        # Verify no audit log was created
        mock_component.get_config.assert_not_called()

    def test_invocation_start_callback_disabled(self, mock_component, mock_openapi_tool, mock_tool_context):
        """Test callback skips when audit is disabled."""
        mock_component.get_config = Mock(return_value=False)

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, {}, mock_tool_context, mock_component
        )

        # Verify get_config was called to check if enabled
        mock_component.get_config.assert_called_once_with("openapi_audit_enabled", False)

    def test_invocation_start_callback_logs_metadata(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test callback logs invocation start metadata."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {
            "operation_id": "testOperation",
            "http_method": "POST",
        }

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, args, mock_tool_context, mock_component
        )

        # Verify audit log was created
        assert audit_file.exists()
        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "openapi_invocation_start"
        assert entry["tool_name"] == "TestAPI"
        assert entry["operation_id"] == "testOperation"
        assert entry["action"] == "POST: testOperation"
        assert entry["actor"] == "user_xyz789"
        assert entry["correlation_id"] == "sess_abc123"

        # Verify start time was stored for latency calculation
        assert "audit_start_time_ms" in mock_tool_context.state

    @pytest.mark.asyncio
    async def test_execution_result_callback_non_openapi_tool(self, mock_component, mock_tool_context):
        """Test callback skips non-OpenAPI tools."""
        tool = Mock()
        tool.__class__.__name__ = "RegularTool"
        delattr(tool, 'specification_url')

        result = await audit_log_openapi_tool_execution_result(
            tool, {}, mock_tool_context, {}, mock_component
        )

        assert result is None
        mock_component.get_config.assert_not_called()

    @pytest.mark.asyncio
    async def test_execution_result_callback_disabled(self, mock_component, mock_openapi_tool, mock_tool_context):
        """Test callback skips when audit is disabled."""
        mock_component.get_config = Mock(return_value=False)

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, {}, mock_tool_context, {}, mock_component
        )

        assert result is None
        mock_component.get_config.assert_called_once_with("openapi_audit_enabled", False)

    @pytest.mark.asyncio
    async def test_execution_result_callback_logs_success(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test callback logs successful execution metadata."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        # Simulate start time was recorded
        mock_tool_context.state["audit_start_time_ms"] = 1000000

        args = {"operation_id": "testOp", "http_method": "GET"}
        response = {"status_code": 200, "content": {"result": "success"}}

        with patch('time.time', return_value=1000.450):  # 450ms later
            result = await audit_log_openapi_tool_execution_result(
                mock_openapi_tool, args, mock_tool_context, response, mock_component
            )

        assert result is None

        # Verify audit log
        assert audit_file.exists()
        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["event_type"] == "openapi_execution_complete"
        assert entry["status_code"] == 200
        assert entry["latency_ms"] == 450
        assert entry["request_status"] == "success"

    @pytest.mark.asyncio
    async def test_execution_result_callback_logs_error(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test callback logs error metadata."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {"operation_id": "failOp"}
        response = {
            "status_code": 500,
            "error": "Internal server error occurred during processing"
        }

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        assert result is None

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["status_code"] == 500
        assert entry["request_status"] == "error"
        assert entry["error_type"] == "api_error"
        # Error message should be truncated to 100 chars
        assert len(entry["error_message"]) <= 100

    @pytest.mark.asyncio
    async def test_execution_result_callback_truncates_long_error(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that long error messages are truncated."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        # Create very long error message
        long_error = "A" * 200

        args = {"operation_id": "failOp"}
        response = {"error": long_error}

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        # Error message should be truncated to 100 chars
        assert len(entry["error_message"]) == 100
        assert entry["error_message"] == "A" * 100


class TestSecurityRequirements:
    """Test that sensitive data is NEVER logged."""

    def test_no_request_args_logged(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that request arguments are NEVER logged."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        # Include sensitive data in args
        args = {
            "operation_id": "testOp",
            "password": "secret123",
            "api_key": "sk_test_12345",
            "credit_card": "4111111111111111",
        }

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, args, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            content = f.read()

        # Verify NO sensitive data appears in log
        assert "secret123" not in content
        assert "sk_test_12345" not in content
        assert "4111111111111111" not in content
        assert "password" not in content.lower()
        assert "api_key" not in content.lower()

    @pytest.mark.asyncio
    async def test_no_response_data_logged(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that response data is NEVER logged."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {"operation_id": "testOp"}
        response = {
            "status_code": 200,
            "content": {
                "user_data": {
                    "password": "secret",
                    "credit_card": "4111111111111111",
                    "ssn": "123-45-6789"
                }
            }
        }

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        with open(audit_file) as f:
            content = f.read()

        # Verify NO sensitive data from response appears in log
        assert "secret" not in content
        assert "4111111111111111" not in content
        assert "123-45-6789" not in content
        assert "user_data" not in content

    @pytest.mark.asyncio
    async def test_no_headers_logged(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that HTTP headers are NEVER logged."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {"operation_id": "testOp"}
        response = {
            "status_code": 200,
            "headers": {
                "Authorization": "Bearer secret_token_12345",
                "X-API-Key": "sk_live_abcdefg",
                "Content-Type": "application/json",
            }
        }

        result = await audit_log_openapi_tool_execution_result(
            mock_openapi_tool, args, mock_tool_context, response, mock_component
        )

        with open(audit_file) as f:
            content = f.read()

        # Verify NO headers or header values appear in log
        assert "secret_token_12345" not in content
        assert "sk_live_abcdefg" not in content
        assert "Authorization" not in content
        assert "X-API-Key" not in content

    def test_auth_method_type_only_logged(self, mock_component, tmp_path):
        """Test that only auth method TYPE is logged, not credentials."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        logger = OpenAPIAuditLogger(mock_component)

        logger.log_audit_event(
            event_type="openapi_invocation_start",
            tool_name="API",
            operation_id="op",
            tool_uri="https://api.test.com",
            http_method="GET",
            actor="user",
            correlation_id="c1",
            auth_method="apikey",  # Type only, not the actual key
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        # Should have auth method type
        assert entry["auth_method"] == "apikey"

        # Should NOT have any actual credentials
        content = json.dumps(entry)
        assert "sk_" not in content  # No API keys
        assert "Bearer " not in content  # No bearer tokens


class TestExternalAuditService:
    """Test external audit service integration."""

    @patch('httpx.Client')
    def test_send_to_external_service(self, mock_httpx_client, mock_component):
        """Test sending audit events to external HTTP service."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_client_instance = Mock()
        mock_client_instance.post = Mock(return_value=mock_response)
        mock_client_instance.__enter__ = Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = Mock(return_value=False)
        mock_httpx_client.return_value = mock_client_instance

        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": "/tmp/test.jsonl",
            "openapi_audit_service_url": "https://audit.example.com/api/v1/events",
        }.get(key, default))

        logger = OpenAPIAuditLogger(mock_component)

        logger.log_audit_event(
            event_type="openapi_invocation_start",
            tool_name="TestAPI",
            operation_id="testOp",
            tool_uri="https://api.test.com",
            http_method="POST",
            actor="user@example.com",
            correlation_id="corr123",
        )

        # Verify HTTP POST was called
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert call_args[0][0] == "https://audit.example.com/api/v1/events"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

    def test_external_service_failure_does_not_break_logging(self, mock_component, tmp_path):
        """Test that external service failures don't prevent file logging."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
            "openapi_audit_service_url": "https://unreachable.example.com",
        }.get(key, default))

        with patch('httpx.Client') as mock_httpx:
            mock_httpx.side_effect = Exception("Connection failed")

            logger = OpenAPIAuditLogger(mock_component)
            logger.log_audit_event(
                event_type="openapi_invocation_start",
                tool_name="TestAPI",
                operation_id="testOp",
                tool_uri="https://api.test.com",
                http_method="GET",
                actor="user",
                correlation_id="c1",
            )

        # File logging should still work
        assert audit_file.exists()
        with open(audit_file) as f:
            entry = json.loads(f.readline())
        assert entry["tool_name"] == "TestAPI"


class TestCorrelationAndActor:
    """Test correlation_id and actor field population."""

    def test_correlation_id_uses_session_id(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that correlation_id is set to session_id."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, {}, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["correlation_id"] == "sess_abc123"

    def test_correlation_id_fallback_to_function_call_id(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that correlation_id falls back to function_call_id if no session."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        # Remove session
        mock_tool_context._invocation_context.session = None

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, {}, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["correlation_id"] == "fc_test123"

    def test_actor_uses_user_id(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test that actor is set to user_id."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, {}, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["actor"] == "user_xyz789"


class TestActionField:
    """Test action field formatting."""

    def test_action_with_method_and_operation(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test action field combines HTTP method and operation ID."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {
            "operation_id": "createUser",
            "http_method": "POST",
        }

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, args, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["action"] == "POST: createUser"

    def test_action_with_operation_only(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test action field when only operation ID is available."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {"operation_id": "getUser"}

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, args, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["action"] == "getUser"

    def test_action_none_when_no_operation(self, mock_component, mock_openapi_tool, mock_tool_context, tmp_path):
        """Test action field is None when no operation ID."""
        audit_file = tmp_path / "test_audit.jsonl"
        mock_component.get_config = Mock(side_effect=lambda key, default=None: {
            "openapi_audit_enabled": True,
            "openapi_audit_log_file": str(audit_file),
        }.get(key, default))

        args = {}

        audit_log_openapi_tool_invocation_start(
            mock_openapi_tool, args, mock_tool_context, mock_component
        )

        with open(audit_file) as f:
            entry = json.loads(f.readline())

        assert entry["action"] is None