"""Unit tests for ModelConfigService methods.

Tests:
- get_by_alias with raw=True returns unredacted LiteLlm config
- get_by_alias_or_id delegates to repository and handles raw/response modes
- _to_raw_litellm_config builds correct unredacted config dicts
- _to_raw_litellm_config strips placeholder sentinel values

Note: are_default_models_configured, _to_response placeholder stripping, and
delete default model guard are covered by integration tests in
tests/integration/apis/platform/test_model_config_api.py.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from solace_agent_mesh.services.platform.services.model_config_service import (
    ModelConfigService,
    _resolve_litellm_model_name,
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
        """OAuth auth config is mapped to oauth_* prefixed keys for LiteLlm."""
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
        assert result["oauth_client_id"] == "my-client"
        assert result["oauth_client_secret"] == "super-secret"
        assert result["oauth_token_url"] == "https://auth.example.com/token"
        assert "type" not in result
        assert "client_id" not in result

    def test_model_name_gets_litellm_prefix(self):
        """Providers in the prefix map get model name prefixed for LiteLLM routing."""
        db_model = _make_db_model(
            provider="google_ai_studio", model_name="gemini-pro",
            api_base=None, model_auth_config=None, model_params=None,
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result["model"] == "gemini/gemini-pro"

    def test_model_name_not_double_prefixed(self):
        """Model name already containing a slash is not double-prefixed."""
        db_model = _make_db_model(
            provider="bedrock", model_name="bedrock/anthropic.claude-3",
            api_base=None, model_auth_config=None, model_params=None,
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result["model"] == "bedrock/anthropic.claude-3"

    def test_gcp_vertex_credentials_passed_through(self):
        """GCP vertex_credentials is passed through directly to LiteLLM config."""
        db_model = _make_db_model(
            provider="vertex_ai", model_name="gemini-pro", api_base=None,
            model_auth_config={
                "type": "gcp_service_account",
                "vertex_credentials": '{"project_id": "test"}',
                "vertex_project": "test",
            },
            model_params=None,
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        assert result["vertex_credentials"] == '{"project_id": "test"}'


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


def _mock_llm_success_response():
    """Create a mock async generator that yields a successful LLM response."""
    mock_response = Mock()
    mock_response.content = Mock()
    mock_response.content.parts = [Mock(text="OK")]

    async def _gen(*args, **kwargs):
        yield mock_response

    return _gen


def _mock_llm_error_response(error):
    """Create a mock LiteLlm that raises an error on generate_content_async."""
    async def _gen(*args, **kwargs):
        raise error
        yield  # noqa: unreachable — makes this an async generator

    return _gen


class TestTestConnection:
    """Tests for ModelConfigService.test_connection method."""

    @pytest.mark.asyncio
    async def test_test_connection_with_valid_apikey(self):
        """Test connection succeeds with valid API key credentials."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        request = ModelConfigurationTestRequest(
            provider="openai",
            model_name="gpt-4",
            auth_config={"type": "apikey", "api_key": "sk-test-key"},
        )

        with patch("solace_agent_mesh.services.platform.services.model_config_service.LiteLlm") as MockLiteLlm:
            mock_instance = MockLiteLlm.return_value
            mock_instance.generate_content_async = _mock_llm_success_response()

            success, message = await service.test_connection(mock_db, request)

            assert success is True
            assert "successful" in message.lower()
            # Verify LiteLlm was instantiated with model name only, then configured
            assert MockLiteLlm.call_args[1]["model"] == "gpt-4"
            configure_kwargs = mock_instance.configure_model.call_args[0][0]
            assert configure_kwargs["api_key"] == "sk-test-key"

    @pytest.mark.asyncio
    async def test_test_connection_uses_stored_config_as_fallback(self):
        """Test that stored config is used as fallback when model_id is provided."""
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
        service.repository.get_by_id.return_value = stored_config

        # Request with only model_id
        request = ModelConfigurationTestRequest(model_id="01234567-0123-0123-0123-0123456789ab")

        with patch("solace_agent_mesh.services.platform.services.model_config_service.LiteLlm") as MockLiteLlm:
            mock_instance = MockLiteLlm.return_value
            mock_instance.generate_content_async = _mock_llm_success_response()

            success, message = await service.test_connection(mock_db, request)

            assert success is True
            # Verify stored credentials were used via configure_model
            configure_kwargs = mock_instance.configure_model.call_args[0][0]
            assert configure_kwargs["api_key"] == "sk-stored-secret"

    @pytest.mark.asyncio
    async def test_test_connection_missing_required_fields(self):
        """Test connection fails when required fields are missing."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        # Request without provider
        request = ModelConfigurationTestRequest(
            model_name="gpt-4",
            auth_config={"type": "apikey", "api_key": "sk-test-key"},
        )

        success, message = await service.test_connection(mock_db, request)

        assert success is False
        assert "provider" in message.lower() or "required" in message.lower()

    @pytest.mark.asyncio
    async def test_test_connection_nonexistent_model_id(self):
        """Test connection fails when model_id is not found in database."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        service.repository.get_by_id.return_value = None
        mock_db = Mock()

        request = ModelConfigurationTestRequest(model_id="nonexistent-uuid")

        success, message = await service.test_connection(mock_db, request)

        assert success is False
        assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_test_connection_sanitizes_error_messages(self):
        """Test that error messages are sanitized to avoid leaking sensitive data."""
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationTestRequest

        service = ModelConfigService()
        service.repository = Mock()
        mock_db = Mock()

        request = ModelConfigurationTestRequest(
            provider="openai",
            model_name="gpt-4",
            auth_config={"type": "apikey", "api_key": "sk-very-secret-key-that-should-not-appear"},
        )

        with patch("solace_agent_mesh.services.platform.services.model_config_service.LiteLlm") as MockLiteLlm:
            mock_instance = MockLiteLlm.return_value
            mock_instance.generate_content_async = _mock_llm_error_response(
                Exception("A" * 600)  # Very long error message
            )

            success, message = await service.test_connection(mock_db, request)

            assert success is False
            # Check that the error is truncated
            assert "..." in message or len(message) < 600
            # Check that sensitive key doesn't appear
            assert "sk-very-secret-key" not in message


class TestGetModelsFromProviderById:
    """Tests for get_models_from_provider_by_id with override logic."""

    def _make_service(self, db_model=None):
        service = ModelConfigService()
        service.repository = Mock()
        service.repository.get_by_id.return_value = db_model
        return service

    def test_not_found_raises(self):
        from solace_agent_mesh.shared.exceptions.exceptions import EntityNotFoundError
        service = self._make_service(db_model=None)
        try:
            service.get_models_from_provider_by_id(Mock(), "missing", Mock())
            assert False, "Expected EntityNotFoundError"
        except EntityNotFoundError:
            pass

    def test_no_overrides_uses_stored_config(self):
        db_model = _make_db_model(
            provider="openai", api_base="https://api.openai.com/v1",
            model_auth_type="apikey",
            model_auth_config={"type": "apikey", "api_key": "sk-stored"},
            model_params={"temperature": 0.5},
        )
        service = self._make_service(db_model)
        mock_list_svc = Mock()
        service.get_models_from_provider_by_id(Mock(), "id", mock_list_svc)
        mock_list_svc.get_models_by_provider_with_config.assert_called_once_with(
            provider="openai", api_base="https://api.openai.com/v1",
            auth_type="apikey",
            auth_config={"type": "apikey", "api_key": "sk-stored"},
            model_params={"temperature": 0.5},
        )

    def test_provider_changed_discards_stored_credentials(self):
        db_model = _make_db_model(
            provider="openai",
            model_auth_config={"type": "apikey", "api_key": "sk-old"},
            model_params={"temperature": 0.7},
        )
        service = self._make_service(db_model)
        mock_list_svc = Mock()
        service.get_models_from_provider_by_id(
            Mock(), "id", mock_list_svc,
            provider_override="anthropic",
            auth_config_overrides={"type": "apikey", "api_key": "sk-new"},
            api_base_override="https://api.anthropic.com/v1",
        )
        call_kwargs = mock_list_svc.get_models_by_provider_with_config.call_args[1]
        assert call_kwargs["provider"] == "anthropic"
        assert call_kwargs["auth_config"]["api_key"] == "sk-new"
        assert "sk-old" not in str(call_kwargs)
        assert call_kwargs["model_params"] == {"temperature": 0.7}

    def test_same_provider_merges_auth_overrides(self):
        db_model = _make_db_model(
            provider="openai", model_auth_type="apikey",
            model_auth_config={"type": "apikey", "api_key": "sk-stored", "org_id": "org-123"},
        )
        service = self._make_service(db_model)
        mock_list_svc = Mock()
        service.get_models_from_provider_by_id(
            Mock(), "id", mock_list_svc,
            provider_override="openai",
            auth_config_overrides={"type": "apikey", "api_key": "sk-new"},
        )
        call_kwargs = mock_list_svc.get_models_by_provider_with_config.call_args[1]
        assert call_kwargs["auth_config"]["api_key"] == "sk-new"
        assert call_kwargs["auth_config"]["org_id"] == "org-123"

    def test_same_provider_auth_type_changed_replaces(self):
        db_model = _make_db_model(
            provider="openai", model_auth_type="apikey",
            model_auth_config={"type": "apikey", "api_key": "sk-old"},
        )
        service = self._make_service(db_model)
        mock_list_svc = Mock()
        service.get_models_from_provider_by_id(
            Mock(), "id", mock_list_svc,
            provider_override="openai",
            auth_config_overrides={"type": "oauth2", "client_id": "my-client"},
        )
        call_kwargs = mock_list_svc.get_models_by_provider_with_config.call_args[1]
        assert call_kwargs["auth_type"] == "oauth2"
        assert "api_key" not in call_kwargs["auth_config"]

    def test_api_base_override(self):
        db_model = _make_db_model(
            provider="openai", api_base="https://old.api.com/v1",
            model_auth_type="apikey",
            model_auth_config={"type": "apikey", "api_key": "sk-key"},
        )
        service = self._make_service(db_model)
        mock_list_svc = Mock()
        service.get_models_from_provider_by_id(
            Mock(), "id", mock_list_svc, api_base_override="https://new.api.com/v1",
        )
        call_kwargs = mock_list_svc.get_models_by_provider_with_config.call_args[1]
        assert call_kwargs["api_base"] == "https://new.api.com/v1"


class TestUpdateAuthHandling:
    """Tests for update method's auth merging and api_base clearing."""

    def _make_service_with_stored(self, **db_overrides):
        service = ModelConfigService()
        service.repository = Mock()
        db_model = _make_db_model(**db_overrides)
        service.repository.get_by_id.return_value = db_model
        service.repository.get_by_alias.return_value = None
        service.repository.update.return_value = None
        return service, db_model

    def test_empty_api_base_clears_to_none(self):
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationUpdateRequest
        service, db_model = self._make_service_with_stored(api_base="https://old.api.com/v1")
        request = ModelConfigurationUpdateRequest(api_base="")
        service.update(Mock(), db_model.id, request, "admin")
        assert db_model.api_base is None

    def test_auth_type_changed_replaces_entirely(self):
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationUpdateRequest
        service, db_model = self._make_service_with_stored(
            model_auth_config={"type": "apikey", "api_key": "sk-old"},
            model_auth_type="apikey",
        )
        request = ModelConfigurationUpdateRequest(
            auth_config={"type": "oauth2", "client_id": "new-client"},
        )
        service.update(Mock(), db_model.id, request, "admin")
        assert db_model.model_auth_config == {"type": "oauth2", "client_id": "new-client"}
        assert db_model.model_auth_type == "oauth2"
        assert "api_key" not in db_model.model_auth_config

    def test_same_auth_type_merges(self):
        from solace_agent_mesh.services.platform.api.routers.dto.requests import ModelConfigurationUpdateRequest
        service, db_model = self._make_service_with_stored(
            model_auth_config={"type": "apikey", "api_key": "sk-stored", "org_id": "org-1"},
            model_auth_type="apikey",
        )
        request = ModelConfigurationUpdateRequest(
            auth_config={"type": "apikey", "api_key": "sk-updated"},
        )
        service.update(Mock(), db_model.id, request, "admin")
        assert db_model.model_auth_config["api_key"] == "sk-updated"
        assert db_model.model_auth_config["org_id"] == "org-1"


class TestToRawLitellmConfigPlaceholderStripping:
    """Tests for _to_raw_litellm_config stripping placeholder sentinel values."""

    def test_placeholder_values_stripped(self):
        """Placeholder provider and model_name are stripped to None before LiteLLM config."""
        db_model = _make_db_model(
            provider="undefined", model_name="undefined",
            api_base=None, model_auth_config=None, model_params=None,
        )
        result = ModelConfigService._to_raw_litellm_config(db_model)
        # _resolve_litellm_model_name(None, None) returns None
        assert result["model"] is None


