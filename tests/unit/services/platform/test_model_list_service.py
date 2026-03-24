"""Unit tests for ModelListService provider-specific logic.

Tests auth header building, API base resolution, response parsing for different
providers, and error handling - all without hitting live APIs.
"""

import pytest
from unittest.mock import MagicMock, patch

from solace_agent_mesh.services.platform.services.model_list_service import ModelListService


class TestModelListServiceAuthHeaders:
    """Tests for _build_auth_headers provider-specific behavior."""

    def setup_method(self):
        self.service = ModelListService()

    def test_openai_uses_bearer_token(self):
        """OpenAI-compatible providers use Bearer token format."""
        headers = self.service._build_auth_headers("openai", "apikey", {"api_key": "sk-test"})
        assert headers["Authorization"] == "Bearer sk-test"

    def test_anthropic_uses_x_api_key_header(self):
        """Anthropic uses X-API-Key header instead of Bearer."""
        headers = self.service._build_auth_headers("anthropic", "apikey", {"api_key": "sk-test"})
        assert headers["X-API-Key"] == "sk-test"

    def test_anthropic_includes_version_header(self):
        """Anthropic response always includes version header."""
        headers = self.service._build_auth_headers("anthropic", "apikey", {"api_key": "sk-test"})
        assert headers["anthropic-version"] == "2023-06-01"

    def test_google_ai_studio_no_bearer_token(self):
        """Google AI Studio doesn't use Bearer (uses query params instead)."""
        headers = self.service._build_auth_headers("google_ai_studio", "apikey", {"api_key": "key"})
        assert "Authorization" not in headers

    def test_missing_api_key_no_header(self):
        """Missing api_key should not add Authorization header."""
        headers = self.service._build_auth_headers("openai", "apikey", {})
        assert "Authorization" not in headers

    def test_empty_string_api_key_no_header(self):
        """Empty api_key should not add Authorization header."""
        headers = self.service._build_auth_headers("openai", "apikey", {"api_key": ""})
        assert "Authorization" not in headers

    def test_none_auth_type_no_headers(self):
        """None auth type returns empty headers."""
        headers = self.service._build_auth_headers("openai", "none", {})
        assert headers == {}


class TestModelListServiceApiBase:
    """Tests for _get_provider_api_base."""

    def setup_method(self):
        self.service = ModelListService()

    def test_known_providers_return_correct_urls(self):
        """Each known provider returns its correct API base."""
        assert self.service._get_provider_api_base("openai") == "https://api.openai.com/v1"
        assert self.service._get_provider_api_base("anthropic") == "https://api.anthropic.com"
        assert self.service._get_provider_api_base("ollama") == "http://localhost:11434/api"
        assert self.service._get_provider_api_base("google_ai_studio") == "https://generativelanguage.googleapis.com/v1beta/models"

    def test_azure_returns_none(self):
        """Azure requires custom api_base, returns None."""
        assert self.service._get_provider_api_base("azure_openai") is None

    def test_unknown_provider_returns_none(self):
        """Unknown providers return None."""
        assert self.service._get_provider_api_base("unknown") is None


class TestModelListServiceResponseParsing:
    """Tests for response parsing from different providers."""

    def setup_method(self):
        self.service = ModelListService()

    def test_parse_anthropic_filters_by_type(self):
        """Anthropic response should filter items by type='model'."""
        with patch("solace_agent_mesh.services.platform.services.model_list_service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None

            # Mock response with both model and non-model items
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "data": [
                    {"id": "claude-3-opus", "type": "model"},
                    {"id": "some-tool", "type": "tool"},
                    {"id": "claude-3-sonnet", "type": "model"},
                ]
            }
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = self.service.get_models_by_provider_with_config(
                provider="anthropic",
                api_base="https://api.anthropic.com",
                auth_type="apikey",
                auth_config={"api_key": "key"},
            )

            # Should only include items with type="model"
            assert len(result) == 2
            assert result[0]["id"] == "claude-3-opus"
            assert result[1]["id"] == "claude-3-sonnet"

    def test_parse_ollama_strips_tag_suffix(self):
        """Ollama models should have tag suffix stripped (e.g., llama2:latest -> llama2)."""
        with patch("solace_agent_mesh.services.platform.services.model_list_service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {"name": "llama2:latest"},
                    {"name": "mistral:7b"},
                    {"name": "neural-chat"},  # No tag
                ]
            }
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = self.service.get_models_by_provider_with_config(
                provider="ollama",
                api_base="http://localhost:11434/api",
                auth_type="none",
                auth_config={},
            )

            assert len(result) == 3
            assert result[0]["id"] == "llama2"
            assert result[1]["id"] == "mistral"
            assert result[2]["id"] == "neural-chat"

    def test_parse_google_ai_studio_extracts_model_name(self):
        """Google AI Studio returns names like 'models/gemini-pro', should extract to 'gemini-pro'."""
        with patch("solace_agent_mesh.services.platform.services.model_list_service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {"name": "models/gemini-pro"},
                    {"name": "models/gemini-pro-vision"},
                    {"name": "models/text-bison"},
                ]
            }
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = self.service.get_models_by_provider_with_config(
                provider="google_ai_studio",
                api_base="https://generativelanguage.googleapis.com/v1beta/models",
                auth_type="apikey",
                auth_config={"api_key": "key"},
            )

            assert len(result) == 3
            assert result[0]["id"] == "gemini-pro"
            assert result[1]["id"] == "gemini-pro-vision"
            assert result[2]["id"] == "text-bison"

    def test_parse_google_with_missing_name_field(self):
        """Google response should skip items without name field."""
        with patch("solace_agent_mesh.services.platform.services.model_list_service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.__exit__.return_value = None

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {"name": "models/gemini-pro"},
                    {},  # No name field - will be skipped (empty string is falsy)
                    {"name": ""},  # Empty name - will be skipped
                ]
            }
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = self.service.get_models_by_provider_with_config(
                provider="google_ai_studio",
                api_base="https://generativelanguage.googleapis.com/v1beta/models",
                auth_type="apikey",
                auth_config={"api_key": "key"},
            )

            assert len(result) == 1
            assert result[0]["id"] == "gemini-pro"


class TestModelListServiceValidation:
    """Tests for credential validation in get_models_with_new_credentials."""

    def setup_method(self):
        self.service = ModelListService()

    def test_apikey_auth_missing_api_key(self):
        """Missing api_key should raise ValidationError."""
        from solace_agent_mesh.shared.exceptions.exceptions import ValidationError
        with pytest.raises(ValidationError) as exc_info:
            self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="apikey",
                api_key=None,
            )
        assert "API key is required" in str(exc_info.value)

    def test_oauth2_auth_missing_credentials(self):
        """Missing oauth2 credentials should raise ValidationError."""
        from solace_agent_mesh.shared.exceptions.exceptions import ValidationError
        with pytest.raises(ValidationError):
            self.service.get_models_with_new_credentials(
                provider="google",
                api_base=None,
                auth_type="oauth2",
                client_id=None,
                client_secret="secret",
                token_url="https://example.com/token",
            )

    def test_aws_iam_auth_missing_credentials(self):
        """Missing AWS credentials should raise ValidationError."""
        from solace_agent_mesh.shared.exceptions.exceptions import ValidationError
        with pytest.raises(ValidationError):
            self.service.get_models_with_new_credentials(
                provider="bedrock",
                api_base=None,
                auth_type="aws_iam",
                aws_access_key_id=None,
                aws_secret_access_key="secret",
            )

    def test_gcp_service_account_missing_json(self):
        """Missing gcp_service_account_json should raise ValidationError."""
        from solace_agent_mesh.shared.exceptions.exceptions import ValidationError
        with pytest.raises(ValidationError):
            self.service.get_models_with_new_credentials(
                provider="vertex_ai",
                api_base=None,
                auth_type="gcp_service_account",
                gcp_service_account_json=None,
            )

    def test_unsupported_auth_type(self):
        """Unsupported auth_type should raise ValidationError."""
        from solace_agent_mesh.shared.exceptions.exceptions import ValidationError
        with pytest.raises(ValidationError):
            self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="invalid_auth",
            )

    def test_none_auth_type_valid(self):
        """None auth type should pass validation."""
        with patch.object(
            self.service, 'get_models_by_provider_with_config',
            return_value=[{"id": "model-1", "label": "model-1", "provider": "openai"}]
        ):
            result = self.service.get_models_with_new_credentials(
                provider="openai",
                api_base="https://api.openai.com/v1",
                auth_type="none",
            )
            assert len(result) == 1

    def test_aws_iam_with_session_token(self):
        """AWS session token should be included when provided."""
        with patch.object(
            self.service, 'get_models_by_provider_with_config',
            return_value=[]
        ) as mock_get:
            self.service.get_models_with_new_credentials(
                provider="bedrock",
                api_base=None,
                auth_type="aws_iam",
                aws_access_key_id="access",
                aws_secret_access_key="secret",
                aws_session_token="token",
            )
            # Verify session token was included
            call_args = mock_get.call_args[1]
            assert call_args["auth_config"]["aws_session_token"] == "token"


class TestModelListServiceMissingApiBase:
    """Tests for error handling when API base is missing."""

    def setup_method(self):
        self.service = ModelListService()

    def test_custom_provider_missing_api_base(self):
        """Custom provider should fail if api_base is not provided."""
        with pytest.raises(RuntimeError) as exc_info:
            self.service.get_models_by_provider_with_config(
                provider="custom",
                api_base=None,
                auth_type="apikey",
                auth_config={"api_key": "key"},
            )
        assert "API base URL not configured" in str(exc_info.value)

    def test_unsupported_provider(self):
        """Unsupported provider should raise RuntimeError."""
        with pytest.raises(RuntimeError) as exc_info:
            self.service.get_models_by_provider_with_config(
                provider="unknown_provider",
                api_base="https://example.com",
                auth_type="apikey",
                auth_config={"api_key": "key"},
            )
        assert "Unsupported provider" in str(exc_info.value)
