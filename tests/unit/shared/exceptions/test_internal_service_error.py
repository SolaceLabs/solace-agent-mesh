"""
Unit tests for InternalServiceError exception and handler.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import status

from solace_agent_mesh.shared.exceptions import InternalServiceError
from solace_agent_mesh.shared.exceptions.exception_handlers import (
    internal_service_error_handler,
)


class TestInternalServiceError:
    """Test InternalServiceError exception."""

    def test_init_with_default_message(self):
        """Test initialization with default error message."""
        error = InternalServiceError()

        assert error.message == "An unexpected error occurred"
        assert str(error) == "An unexpected error occurred"

    def test_init_with_custom_message(self):
        """Test initialization with custom error message."""
        custom_message = "Database connection failed unexpectedly"

        error = InternalServiceError(custom_message)

        assert error.message == custom_message
        assert str(error) == custom_message

    def test_exception_can_be_raised(self):
        """Test that the exception can be raised and caught."""
        with pytest.raises(InternalServiceError) as exc_info:
            raise InternalServiceError("Test error")

        assert exc_info.value.message == "Test error"

    def test_exception_inherits_from_webui_backend_exception(self):
        """Test that InternalServiceError inherits from WebUIBackendException."""
        from solace_agent_mesh.shared.exceptions.exceptions import (
            WebUIBackendException,
        )

        error = InternalServiceError()
        assert isinstance(error, WebUIBackendException)
        assert isinstance(error, Exception)


class TestInternalServiceErrorHandler:
    """Test internal_service_error_handler."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock()
        request.url.path = "/api/test"
        request.method = "GET"
        return request

    @pytest.mark.asyncio
    async def test_handler_returns_500_status(self, mock_request):
        """Test that handler returns 500 Internal Server Error."""
        exc = InternalServiceError("Test internal error")

        with patch(
            "solace_agent_mesh.shared.exceptions.exception_handlers.log"
        ) as mock_log:
            response = await internal_service_error_handler(mock_request, exc)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_handler_returns_generic_message(self, mock_request):
        """Test that handler returns generic message without internal details."""
        exc = InternalServiceError("Sensitive internal details here")

        with patch(
            "solace_agent_mesh.shared.exceptions.exception_handlers.log"
        ):
            response = await internal_service_error_handler(mock_request, exc)

        import json

        body = json.loads(response.body)
        assert body["message"] == "An unexpected error occurred."
        assert "Sensitive" not in body["message"]

    @pytest.mark.asyncio
    async def test_handler_logs_error_with_context(self, mock_request):
        """Test that handler logs error with request context."""
        exc = InternalServiceError("Database connection failed")

        with patch(
            "solace_agent_mesh.shared.exceptions.exception_handlers.log"
        ) as mock_log:
            await internal_service_error_handler(mock_request, exc)

            mock_log.error.assert_called_once()
            call_args = mock_log.error.call_args
            assert "InternalServiceError: %s" in call_args[0]
            assert call_args[0][1] == "Database connection failed"
            assert call_args[1]["extra"]["path"] == "/api/test"
            assert call_args[1]["extra"]["method"] == "GET"
            assert call_args[1]["exc_info"] is True

    @pytest.mark.asyncio
    async def test_handler_with_default_message(self, mock_request):
        """Test handler with default exception message."""
        exc = InternalServiceError()

        with patch(
            "solace_agent_mesh.shared.exceptions.exception_handlers.log"
        ) as mock_log:
            response = await internal_service_error_handler(mock_request, exc)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        call_args = mock_log.error.call_args
        assert call_args[0][1] == "An unexpected error occurred"
