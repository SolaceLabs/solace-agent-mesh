"""
Integration tests for Platform Service model configuration API endpoints.

Tests the HTTP layer behavior for model configuration endpoints including:
- Response shape and camelCase serialization
- 404 errors for non-existent aliases
- 501 errors when feature flag is disabled
- Credential filtering from HTTP responses
"""

import logging
import os
import uuid
import pytest
from unittest.mock import patch
from sqlalchemy.orm import Session

from solace_agent_mesh.services.platform.models import ModelConfiguration
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)


@pytest.fixture
def enable_model_config_feature_flag():
    """Enable the model_config_ui feature flag for testing."""
    with patch.dict(os.environ, {"SAM_FEATURE_MODEL_CONFIG_UI": "true"}):
        yield


class TestModelConfigurationAPI:
    """Tests for /api/v1/platform/models endpoints."""

    def test_get_model_response_shape_and_camel_case(self, platform_api_client, platform_db_session_factory, enable_model_config_feature_flag):
        """Test that GET /models/{alias} returns correct shape, camelCase fields, and non-secret data."""
        # Setup: Create a model configuration
        db = platform_db_session_factory()
        try:
            model_config = ModelConfiguration(
                id=str(uuid.uuid4()),
                alias="test-gpt-4",
                provider="openai",
                model_name="gpt-4",
                api_base="https://api.openai.com/v1",
                model_auth_type="apikey",
                model_auth_config={"api_key": "sk-test-key-12345", "type": "apikey"},
                model_params={"temperature": 0.7, "max_tokens": 2000},
                description="Test GPT-4 configuration",
                created_by="test_user",
                updated_by="test_user",
                created_time=now_epoch_ms(),
                updated_time=now_epoch_ms(),
            )
            db.add(model_config)
            db.commit()

            # Act: Fetch the model
            response = platform_api_client.get("/api/v1/platform/models/test-gpt-4")

            # Assert: Status code is 200
            assert response.status_code == 200

            # Capture response text and data for assertions
            response_text = response.text
            data = response.json()

            # Assert: All expected fields are present
            expected_fields = {
                "id", "alias", "provider", "modelName", "apiBase", "authType",
                "authConfig", "modelParams", "description", "createdBy",
                "updatedBy", "createdTime", "updatedTime"
            }
            assert set(data.keys()) == expected_fields

            # Assert: Field values are correct
            assert data["alias"] == "test-gpt-4"
            assert data["provider"] == "openai"
            assert data["modelName"] == "gpt-4"
            assert data["apiBase"] == "https://api.openai.com/v1"
            assert data["authType"] == "apikey"
            assert isinstance(data["authConfig"], dict)
            assert isinstance(data["modelParams"], dict)

            assert data["modelParams"]["temperature"] == 0.7
            assert data["modelParams"]["max_tokens"] == 2000

            assert data["description"] == "Test GPT-4 configuration"
            assert data["createdBy"] == "test_user"
            assert data["updatedBy"] == "test_user"

            # Assert: Secrets are redacted from authConfig
            assert "api_key" not in data["authConfig"]
            assert "sk-test-key-12345" not in response_text

        finally:
            db.close()

    @pytest.mark.parametrize("auth_type,secret_fields,stored_config,expected_secret_text,expected_config", [
        # API key auth - api_key should be redacted, type field also removed
        (
            "apikey",
            {"api_key"},
            {"api_key": "sk-secret-123", "type": "apikey"},
            "sk-secret-123",
            {}
        ),
        # OAuth2 - client_secret redacted, public fields preserved, type field removed
        (
            "oauth2",
            {"client_secret"},
            {
                "client_id": "public-id",
                "client_secret": "super-secret",
                "token_url": "https://auth.example.com/token",
                "ca_cert": "/etc/ssl/certs/custom-ca.pem",
                "type": "oauth2"
            },
            "super-secret",
            {
                "client_id": "public-id",
                "token_url": "https://auth.example.com/token",
                "ca_cert": "/etc/ssl/certs/custom-ca.pem",
            }
        ),
        # No auth - type field removed (empty authConfig)
        (
            "none",
            set(),
            {"type": "none"},
            None,
            {}
        ),
    ])
    def test_credential_filtering_by_auth_type(
        self, platform_api_client, platform_db_session_factory, enable_model_config_feature_flag,
        auth_type, secret_fields, stored_config, expected_secret_text, expected_config
    ):
        """Test that secrets are redacted based on auth type while public fields are preserved."""
        # Setup: Create a model with the specified auth type
        db = platform_db_session_factory()
        try:
            alias = f"test-{auth_type}"
            model_config = ModelConfiguration(
                id=str(uuid.uuid4()),
                alias=alias,
                provider="openai",
                model_name="gpt-4",
                api_base=None,
                model_auth_type=auth_type,
                model_auth_config=stored_config,
                model_params={},
                created_by="test_user",
                updated_by="test_user",
                created_time=now_epoch_ms(),
                updated_time=now_epoch_ms(),
            )
            db.add(model_config)
            db.commit()

            # Act: Fetch the model
            response = platform_api_client.get(f"/api/v1/platform/models/{alias}")

            # Assert: Status code is 200
            assert response.status_code == 200

            # Assert: Secret values are NOT in response text
            if expected_secret_text:
                assert expected_secret_text not in response.text

            # Assert: authConfig has only public/redacted fields
            data = response.json()
            assert data["authConfig"] == expected_config

        finally:
            db.close()

    def test_get_model_returns_404_for_nonexistent_alias(self, platform_api_client, enable_model_config_feature_flag):
        """Test that GET /models/{alias} returns 404 when alias doesn't exist."""
        # Act: Request a non-existent model
        response = platform_api_client.get("/api/v1/platform/models/nonexistent-model")

        # Assert: Status code is 404
        assert response.status_code == 404

        # Assert: Response contains error detail
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_list_models_returns_correct_structure(self, platform_api_client, platform_db_session_factory, enable_model_config_feature_flag):
        """Test that GET /models returns a list with correct structure and camelCase fields."""
        # Setup: Create multiple model configurations
        db = platform_db_session_factory()
        try:
            for i in range(3):
                model_config = ModelConfiguration(
                    id=str(uuid.uuid4()),
                    alias=f"model-{i}",
                    provider="openai",
                    model_name=f"gpt-{i}",
                    api_base=None,
                    model_auth_type="none",
                    model_auth_config={"type": "none"},
                    model_params={},
                    created_by="test_user",
                    updated_by="test_user",
                    created_time=now_epoch_ms(),
                    updated_time=now_epoch_ms(),
                )
                db.add(model_config)
            db.commit()

            # Act: Fetch all models
            response = platform_api_client.get("/api/v1/platform/models")

            # Assert: Status code is 200
            assert response.status_code == 200

            # Assert: Response has expected structure with camelCase
            data = response.json()
            assert "data" in data
            assert isinstance(data["data"], list)
            assert len(data["data"]) >= 3

            # Assert: Each configuration uses camelCase
            for config in data["data"]:
                assert "modelName" in config
                assert "model_name" not in config
                assert "authType" in config
                assert "createdTime" in config
                assert "updatedTime" in config

        finally:
            db.close()

    def test_feature_flag_disabled_returns_501(self, platform_api_client_factory):
        """Test that endpoints return 501 when model_config_ui feature flag is disabled."""
        from fastapi.testclient import TestClient

        app = platform_api_client_factory.app

        # Ensure the feature flag is disabled
        with patch.dict(os.environ, {"SAM_FEATURE_MODEL_CONFIG_UI": "false"}):
            client = TestClient(app)

            # Act: Try to get models with feature flag disabled
            response = client.get("/api/v1/platform/models")

            # Assert: Status code is 501
            assert response.status_code == 501

            # Assert: Response contains error detail
            data = response.json()
            assert "detail" in data
            assert "not enabled" in data["detail"].lower()
