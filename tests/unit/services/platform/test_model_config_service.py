"""Unit tests for ModelConfigService new methods.

Tests:
- get_by_alias with raw=True returns unredacted LiteLlm config
- get_by_alias_or_id delegates to repository and handles raw/response modes
- _to_raw_litellm_config builds correct unredacted config dicts
"""

from unittest.mock import Mock, patch

from solace_agent_mesh.services.platform.services.model_config_service import (
    ModelConfigService,
)


def _make_db_model(**overrides):
    """Create a mock ModelConfiguration with sensible defaults."""
    m = Mock()
    m.id = overrides.get("id", "01234567-0123-0123-0123-0123456789ab")
    m.alias = overrides.get("alias", "my-model")
    m.provider = overrides.get("provider", "openai")
    m.model_name = overrides.get("model_name", "gpt-4")
    m.api_base = overrides.get("api_base", "https://api.openai.com/v1")
    m.model_auth_type = overrides.get("model_auth_type", "apikey")
    m.model_auth_config = overrides.get(
        "model_auth_config", {"type": "apikey", "api_key": "sk-secret"}
    )
    m.model_params = overrides.get("model_params", {"temperature": 0.7})
    m.description = overrides.get("description", "Test model")
    m.created_by = overrides.get("created_by", "admin")
    m.updated_by = overrides.get("updated_by", "admin")
    m.created_time = overrides.get("created_time", 1700000000000)
    m.updated_time = overrides.get("updated_time", 1700000000000)
    return m


class TestToRawLitellmConfig:
    """Tests for ModelConfigService._to_raw_litellm_config."""

    def test_basic_config(self):
        """Returns model name and api_base."""
        db_model = _make_db_model(
            model_auth_config=None,
            model_params=None,
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result == {
            "model": "gpt-4",
            "api_base": "https://api.openai.com/v1",
        }

    def test_includes_auth_credentials_unredacted(self):
        """Auth config is merged without redaction, and 'type' key is stripped."""
        db_model = _make_db_model(
            model_auth_config={"type": "apikey", "api_key": "sk-secret-123"},
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result["api_key"] == "sk-secret-123"
        assert "type" not in result

    def test_includes_model_params(self):
        """Model params are merged into the config dict."""
        db_model = _make_db_model(
            model_params={"temperature": 0.5, "max_tokens": 1024},
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result["temperature"] == 0.5
        assert result["max_tokens"] == 1024

    def test_no_api_base(self):
        """api_base is omitted when None."""
        db_model = _make_db_model(api_base=None, model_auth_config=None, model_params=None)
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert "api_base" not in result
        assert result == {"model": "gpt-4"}

    def test_empty_api_base_is_omitted(self):
        """api_base is omitted when empty string (falsy)."""
        db_model = _make_db_model(api_base="", model_auth_config=None, model_params=None)
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert "api_base" not in result

    def test_full_config_with_all_fields(self):
        """Full config merges model_name, api_base, auth (minus type), and params."""
        db_model = _make_db_model(
            model_name="claude-3-opus",
            api_base="https://api.anthropic.com/v1",
            model_auth_config={"type": "apikey", "api_key": "sk-ant-123"},
            model_params={"max_tokens": 4096},
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result == {
            "model": "claude-3-opus",
            "api_base": "https://api.anthropic.com/v1",
            "api_key": "sk-ant-123",
            "max_tokens": 4096,
        }

    def test_oauth_auth_config(self):
        """OAuth auth config merges all fields except 'type'."""
        db_model = _make_db_model(
            model_auth_config={
                "type": "oauth2",
                "client_id": "my-client",
                "client_secret": "super-secret",
                "token_url": "https://auth.example.com/token",
            },
            model_params=None,
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result["client_id"] == "my-client"
        assert result["client_secret"] == "super-secret"
        assert result["token_url"] == "https://auth.example.com/token"
        assert "type" not in result


class TestGetByAlias:
    """Tests for get_by_alias with the new raw parameter."""

    def test_raw_true_returns_litellm_config(self):
        """When raw=True, returns unredacted LiteLlm config dict."""
        service = ModelConfigService()
        db_model = _make_db_model()
        service.repository = Mock()
        service.repository.get_by_alias.return_value = db_model
        mock_db = Mock()

        result = service.get_by_alias(mock_db, "my-model", raw=True)

        assert isinstance(result, dict)
        assert result["model"] == "gpt-4"
        assert result["api_key"] == "sk-secret"  # unredacted

    def test_raw_false_returns_response_model(self):
        """When raw=False (default), returns ModelConfigurationResponse."""
        service = ModelConfigService()
        db_model = _make_db_model()
        service.repository = Mock()
        service.repository.get_by_alias.return_value = db_model
        mock_db = Mock()

        result = service.get_by_alias(mock_db, "my-model", raw=False)

        # Should be a response object, not a dict
        assert hasattr(result, "alias")
        assert result.alias == "my-model"

    def test_not_found_raises_entity_not_found(self):
        """Raises EntityNotFoundError when alias not found."""
        from solace_agent_mesh.shared.exceptions.exceptions import EntityNotFoundError

        service = ModelConfigService()
        service.repository = Mock()
        service.repository.get_by_alias.return_value = None
        mock_db = Mock()

        raised = False
        try:
            service.get_by_alias(mock_db, "nonexistent", raw=True)
        except EntityNotFoundError:
            raised = True
        assert raised, "Expected EntityNotFoundError for raw=True"

        raised = False
        try:
            service.get_by_alias(mock_db, "nonexistent", raw=False)
        except EntityNotFoundError:
            raised = True
        assert raised, "Expected EntityNotFoundError for raw=False"


class TestGetByAliasOrId:
    """Tests for get_by_alias_or_id method."""

    def test_found_with_raw_true(self):
        """Returns raw LiteLlm config when found and raw=True."""
        service = ModelConfigService()
        db_model = _make_db_model()
        service.repository = Mock()
        service.repository.get_by_alias_or_id.return_value = db_model
        mock_db = Mock()

        result = service.get_by_alias_or_id(mock_db, "my-model", raw=True)

        assert isinstance(result, dict)
        assert result["model"] == "gpt-4"
        service.repository.get_by_alias_or_id.assert_called_once_with(mock_db, "my-model")

    def test_found_with_raw_false(self):
        """Returns ModelConfigurationResponse when found and raw=False."""
        service = ModelConfigService()
        db_model = _make_db_model()
        service.repository = Mock()
        service.repository.get_by_alias_or_id.return_value = db_model
        mock_db = Mock()

        result = service.get_by_alias_or_id(mock_db, "my-model", raw=False)

        assert hasattr(result, "alias")
        assert result.alias == "my-model"

    def test_not_found_returns_none(self):
        """Returns None when model not found."""
        service = ModelConfigService()
        service.repository = Mock()
        service.repository.get_by_alias_or_id.return_value = None
        mock_db = Mock()

        assert service.get_by_alias_or_id(mock_db, "unknown", raw=True) is None
        assert service.get_by_alias_or_id(mock_db, "unknown", raw=False) is None

    def test_delegates_to_repository(self):
        """Calls repository.get_by_alias_or_id with correct arguments."""
        service = ModelConfigService()
        service.repository = Mock()
        service.repository.get_by_alias_or_id.return_value = None
        mock_db = Mock()

        service.get_by_alias_or_id(mock_db, "some-id-or-alias")

        service.repository.get_by_alias_or_id.assert_called_once_with(mock_db, "some-id-or-alias")


class TestTestConnection:
    """Tests for ModelConfigService.test_connection method."""

    def test_test_connection_with_valid_apikey(self):
        """Test connection succeeds with valid API key credentials."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        request = ModelConfigurationTestRequest(
            provider="openai",
            model_name="gpt-4",
            auth_type="apikey",
            api_key="sk-test-key",
        )

        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm") as mock_litellm:
            # Mock successful response
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_litellm.completion.return_value = mock_response

            success, message = service.test_connection(mock_db, request)

            assert success is True
            assert "successful" in message.lower()
            mock_litellm.completion.assert_called_once()

    def test_test_connection_fails_without_litellm(self):
        """Test connection fails gracefully when litellm is not available."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        request = ModelConfigurationTestRequest(
            provider="openai",
            model_name="gpt-4",
            auth_type="apikey",
            api_key="sk-test-key",
        )

        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm", None):
            success, message = service.test_connection(mock_db, request)

            assert success is False
            assert "litellm" in message.lower()

    def test_test_connection_uses_stored_config_as_fallback(self):
        """Test that stored config is used as fallback when alias is provided."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        # Create stored config
        stored_config = _make_db_model(
            provider="openai",
            model_name="gpt-4",
            model_auth_config={"type": "apikey", "api_key": "sk-stored-secret"},
        )
        service.repository.get_by_alias.return_value = stored_config

        # Request with only alias
        request = ModelConfigurationTestRequest(alias="my-model")

        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm") as mock_litellm:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_litellm.completion.return_value = mock_response

            success, message = service.test_connection(mock_db, request)

            assert success is True
            # Verify stored credentials were used
            call_kwargs = mock_litellm.completion.call_args[1]
            assert call_kwargs["api_key"] == "sk-stored-secret"

    def test_test_connection_missing_required_fields(self):
        """Test connection fails when required fields are missing."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        # Request without provider
        request = ModelConfigurationTestRequest(
            model_name="gpt-4",
            auth_type="apikey",
            api_key="sk-test-key",
        )

        success, message = service.test_connection(mock_db, request)

        assert success is False
        assert "provider" in message.lower() or "required" in message.lower()

    def test_test_connection_nonexistent_alias(self):
        """Test connection fails when alias is not found in database."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        service.repository.get_by_alias.return_value = None
        mock_db = Mock()

        request = ModelConfigurationTestRequest(alias="nonexistent-model")

        success, message = service.test_connection(mock_db, request)

        assert success is False
        assert "not found" in message.lower()

    def test_test_connection_sanitizes_error_messages(self):
        """Test that error messages are sanitized to avoid leaking sensitive data."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        request = ModelConfigurationTestRequest(
            provider="openai",
            model_name="gpt-4",
            auth_type="apikey",
            api_key="sk-very-secret-key-that-should-not-appear",
        )

        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm") as mock_litellm:
            # Simulate a long error message
            mock_litellm.completion.side_effect = Exception(
                "A" * 600  # Very long error message
            )

            success, message = service.test_connection(mock_db, request)

            assert success is False
            # Check that the error is truncated
            assert "..." in message or len(message) < 600
            # Check that sensitive key doesn't appear
            assert "sk-very-secret-key" not in message
