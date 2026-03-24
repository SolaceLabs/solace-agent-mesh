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
