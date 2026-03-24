"""Unit tests for ModelListService validation logic.

Tests the credential validation paths that raise ValidationError
for missing required authentication fields.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from solace_agent_mesh.services.platform.services.model_list_service import ModelListService
from solace_agent_mesh.shared.exceptions.exceptions import ValidationError


class TestModelListServiceValidation:
    """Tests for credential validation in get_models_with_new_credentials."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ModelListService()

    def test_apikey_auth_missing_api_key(self):
        """Missing api_key for apikey auth should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="apikey",
                api_key=None,
            )
        assert "API key is required" in str(exc_info.value)

    def test_oauth2_auth_missing_client_id(self):
        """Missing client_id for oauth2 auth should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="google",
                api_base=None,
                auth_type="oauth2",
                client_id=None,
                client_secret="secret",
                token_url="https://example.com/token",
            )
        assert "client_id, client_secret, and token_url are required" in str(exc_info.value)

    def test_oauth2_auth_missing_client_secret(self):
        """Missing client_secret for oauth2 auth should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="google",
                api_base=None,
                auth_type="oauth2",
                client_id="id",
                client_secret=None,
                token_url="https://example.com/token",
            )
        assert "client_id, client_secret, and token_url are required" in str(exc_info.value)

    def test_oauth2_auth_missing_token_url(self):
        """Missing token_url for oauth2 auth should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="google",
                api_base=None,
                auth_type="oauth2",
                client_id="id",
                client_secret="secret",
                token_url=None,
            )
        assert "client_id, client_secret, and token_url are required" in str(exc_info.value)

    def test_aws_iam_auth_missing_access_key(self):
        """Missing aws_access_key_id for aws_iam auth should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="bedrock",
                api_base=None,
                auth_type="aws_iam",
                aws_access_key_id=None,
                aws_secret_access_key="secret",
            )
        assert "aws_access_key_id and aws_secret_access_key are required" in str(exc_info.value)

    def test_aws_iam_auth_missing_secret_key(self):
        """Missing aws_secret_access_key for aws_iam auth should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="bedrock",
                api_base=None,
                auth_type="aws_iam",
                aws_access_key_id="access",
                aws_secret_access_key=None,
            )
        assert "aws_access_key_id and aws_secret_access_key are required" in str(exc_info.value)

    def test_gcp_service_account_auth_missing_json(self):
        """Missing gcp_service_account_json should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="vertex_ai",
                api_base=None,
                auth_type="gcp_service_account",
                gcp_service_account_json=None,
            )
        assert "gcp_service_account_json is required" in str(exc_info.value)

    def test_unsupported_auth_type(self):
        """Unsupported auth_type should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="invalid_auth_type",
            )
        assert "Unsupported auth_type: invalid_auth_type" in str(exc_info.value)

    def test_none_auth_type_succeeds_without_credentials(self):
        """None auth type should not require credentials and delegate to get_models_by_provider_with_config."""
        with patch.object(
            self.service, 'get_models_by_provider_with_config',
            return_value=[{"id": "model-1", "label": "model-1", "provider": "openai"}]
        ) as mock_get_models:
            result = self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="none",
            )
            assert len(result) == 1
            assert result[0]["id"] == "model-1"
            # Verify it delegated with correct auth_config
            mock_get_models.assert_called_once()
            call_kwargs = mock_get_models.call_args[1]
            assert call_kwargs["auth_config"] == {}

    def test_apikey_auth_valid_credentials_delegates(self):
        """Valid apikey credentials should delegate to get_models_by_provider_with_config."""
        with patch.object(
            self.service, 'get_models_by_provider_with_config',
            return_value=[{"id": "gpt-4", "label": "GPT-4", "provider": "openai"}]
        ) as mock_get_models:
            result = self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="apikey",
                api_key="sk-test-key",
            )
            assert len(result) == 1
            assert result[0]["id"] == "gpt-4"
            # Verify it delegated with correct auth_config
            mock_get_models.assert_called_once()
            call_kwargs = mock_get_models.call_args[1]
            assert call_kwargs["auth_config"]["api_key"] == "sk-test-key"

    def test_aws_iam_auth_with_session_token(self):
        """AWS IAM auth with optional session token should include it in auth_config."""
        with patch.object(
            self.service, 'get_models_by_provider_with_config',
            return_value=[]
        ) as mock_get_models:
            self.service.get_models_with_new_credentials(
                provider="bedrock",
                api_base=None,
                auth_type="aws_iam",
                aws_access_key_id="access",
                aws_secret_access_key="secret",
                aws_session_token="token123",
            )
            # Verify session token was included
            call_kwargs = mock_get_models.call_args[1]
            assert call_kwargs["auth_config"]["aws_session_token"] == "token123"

    def test_oauth2_auth_valid_credentials_delegates(self):
        """Valid oauth2 credentials should delegate to get_models_by_provider_with_config."""
        with patch.object(
            self.service, 'get_models_by_provider_with_config',
            return_value=[{"id": "claude-3", "label": "Claude 3", "provider": "anthropic"}]
        ) as mock_get_models:
            result = self.service.get_models_with_new_credentials(
                provider="anthropic",
                api_base=None,
                auth_type="oauth2",
                client_id="client-id",
                client_secret="client-secret",
                token_url="https://oauth.example.com/token",
            )
            assert len(result) == 1
            # Verify all oauth2 fields were included
            call_kwargs = mock_get_models.call_args[1]
            auth_config = call_kwargs["auth_config"]
            assert auth_config["client_id"] == "client-id"
            assert auth_config["client_secret"] == "client-secret"
            assert auth_config["token_url"] == "https://oauth.example.com/token"
