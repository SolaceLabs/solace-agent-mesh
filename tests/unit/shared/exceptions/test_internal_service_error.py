"""
Integration tests for InternalServiceError with FastAPI.
"""

import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from solace_agent_mesh.shared.exceptions import InternalServiceError
from solace_agent_mesh.shared.exceptions.exception_handlers import (
    register_exception_handlers,
)


class TestInternalServiceErrorFastAPIIntegration:
    """Integration tests for InternalServiceError with FastAPI."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with exception handlers registered."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/trigger-error")
        def trigger_error():
            raise InternalServiceError("Database connection lost")

        @app.post("/trigger-default-error")
        def trigger_default_error():
            raise InternalServiceError()

        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app, raise_server_exceptions=False)

    def test_fastapi_returns_500_on_internal_error(self, client):
        """Test that FastAPI returns 500 when InternalServiceError is raised."""
        response = client.get("/trigger-error")

        assert response.status_code == 500

    def test_fastapi_returns_generic_message(self, client):
        """Test that response contains generic message, not internal details."""
        response = client.get("/trigger-error")

        body = response.json()
        assert body["message"] == "An unexpected error occurred."
        assert "Database" not in body["message"]

    def test_fastapi_logs_error_details(self, client):
        """Test that error details are logged when exception is raised."""
        with patch(
            "solace_agent_mesh.shared.exceptions.exception_handlers.log"
        ) as mock_log:
            client.get("/trigger-error")

            mock_log.error.assert_called_once()
            call_args = mock_log.error.call_args
            assert call_args[0][1] == "Database connection lost"
            assert call_args[1]["extra"]["path"] == "/trigger-error"
            assert call_args[1]["extra"]["method"] == "GET"
            assert call_args[1]["exc_info"] is True

    def test_fastapi_post_method_logged_correctly(self, client):
        """Test that POST method is logged correctly."""
        with patch(
            "solace_agent_mesh.shared.exceptions.exception_handlers.log"
        ) as mock_log:
            client.post("/trigger-default-error")

            call_args = mock_log.error.call_args
            assert call_args[1]["extra"]["method"] == "POST"
            assert call_args[1]["extra"]["path"] == "/trigger-default-error"
