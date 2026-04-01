"""
Integration tests for Platform Service model configuration API endpoints.

Tests the HTTP layer behavior for model configuration endpoints including:
- Response shape and camelCase serialization
- CRUD operations across all supported providers and auth types
- Credential filtering from HTTP responses
- 404 errors for non-existent aliases
- 501 errors when feature flag is disabled
"""

import logging
import uuid
import pytest
from unittest.mock import patch, MagicMock

from solace_agent_mesh.services.platform.models import ModelConfiguration
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _make_model_config(**overrides) -> ModelConfiguration:
    """Build a ModelConfiguration with sensible defaults; override any field via kwargs."""
    defaults = dict(
        id=str(uuid.uuid4()),
        alias="test-model",
        provider="openai",
        model_name="gpt-4",
        api_base=None,
        model_auth_type="none",
        model_auth_config={"type": "none"},
        model_params={},
        description=None,
        created_by="test_user",
        updated_by="test_user",
        created_time=now_epoch_ms(),
        updated_time=now_epoch_ms(),
    )
    defaults.update(overrides)
    return ModelConfiguration(**defaults)


@pytest.fixture
def enable_model_config_feature_flag():
    """Enable the model_config_ui feature flag for testing."""
    with patch("openfeature.api.get_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        mock_client.get_boolean_value.return_value = True
        yield


@pytest.fixture
def disable_model_config_feature_flag():
    """Disable the model_config_ui feature flag for testing."""
    with patch("openfeature.api.get_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        mock_client.get_boolean_value.return_value = False
        yield


@pytest.fixture
def seed_model(platform_db_session_factory):
    """Insert a ModelConfiguration into the test DB. Returns the ORM instance."""
    def _seed(**overrides):
        db = platform_db_session_factory()
        model = _make_model_config(**overrides)
        db.add(model)
        db.commit()
        db.close()
        return model
    return _seed


# ---------------------------------------------------------------------------
# Feature flag guard — single parametrized test covers all gated endpoints
# ---------------------------------------------------------------------------


class TestFeatureFlagDisabled:
    """All gated endpoints must return 501 when the feature flag is off."""

    @pytest.mark.parametrize("method,path,json_body", [
        ("get", "/api/v1/platform/models", None),
        ("get", "/api/v1/platform/models/any-alias", None),
        ("post", "/api/v1/platform/models", {
            "alias": "x", "provider": "openai", "modelName": "gpt-4",
        }),
        ("put", "/api/v1/platform/models/any-alias", {"description": "x"}),
        ("delete", "/api/v1/platform/models/any-alias", None),
        ("post", "/api/v1/platform/supported-models", {
            "provider": "openai", "auth_type": "apikey", "api_key": "sk-x",
        }),
        ("post", "/api/v1/platform/models/test", {
            "provider": "openai", "model_name": "gpt-4",
            "auth_type": "apikey", "api_key": "sk-x",
        }),
    ])
    def test_returns_501_when_disabled(
        self, platform_api_client, disable_model_config_feature_flag,
        method, path, json_body,
    ):
        kwargs = {"json": json_body} if json_body is not None else {}
        response = getattr(platform_api_client, method)(path, **kwargs)

        assert response.status_code == 501
        data = response.json()
        assert "detail" in data
        assert "not enabled" in data["detail"].lower()


# ---------------------------------------------------------------------------
# CRUD & response shape tests
# ---------------------------------------------------------------------------


class TestModelConfigurationAPI:
    """Tests for /api/v1/platform/models endpoints."""

    def test_get_model_response_shape_and_camel_case(
        self, platform_api_client, seed_model, enable_model_config_feature_flag,
    ):
        """GET /models/{alias} returns correct shape, camelCase fields, and redacted secrets."""
        seed_model(
            alias="test-gpt-4",
            provider="openai",
            model_name="gpt-4",
            api_base="https://api.openai.com/v1",
            model_auth_type="apikey",
            model_auth_config={"api_key": "sk-test-key-12345", "type": "apikey"},
            model_params={"temperature": 0.7, "max_tokens": 2000},
            description="Test GPT-4 configuration",
        )

        response = platform_api_client.get("/api/v1/platform/models/test-gpt-4")
        assert response.status_code == 200

        data = response.json()["data"]

        expected_fields = {
            "id", "alias", "provider", "modelName", "apiBase", "authType",
            "authConfig", "modelParams", "description", "createdBy",
            "updatedBy", "createdTime", "updatedTime",
        }
        assert set(data.keys()) == expected_fields

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

        # Secrets must be redacted
        assert "api_key" not in data["authConfig"]
        assert "sk-test-key-12345" not in response.text

    # -- Credential filtering across all auth types ---------------------------

    @pytest.mark.parametrize(
        "auth_type,stored_config,expected_secret_text,expected_config",
        [
            # apikey — api_key redacted, type removed
            (
                "apikey",
                {"api_key": "sk-secret-123", "type": "apikey"},
                "sk-secret-123",
                {},
            ),
            # oauth2 — client_secret redacted, public fields preserved
            (
                "oauth2",
                {
                    "client_id": "public-id",
                    "client_secret": "super-secret",
                    "token_url": "https://auth.example.com/token",
                    "ca_cert": "/etc/ssl/certs/custom-ca.pem",
                    "type": "oauth2",
                },
                "super-secret",
                {
                    "client_id": "public-id",
                    "token_url": "https://auth.example.com/token",
                    "ca_cert": "/etc/ssl/certs/custom-ca.pem",
                },
            ),
            # aws_iam — secret_access_key and session_token redacted, access_key_id preserved
            (
                "aws_iam",
                {
                    "aws_access_key_id": "AKIA1234567890",
                    "aws_secret_access_key": "secret-aws-key",
                    "aws_session_token": "session-token-xyz",
                    "aws_region_name": "us-east-1",
                    "type": "aws_iam",
                },
                "secret-aws-key",
                {
                    "aws_access_key_id": "AKIA1234567890",
                    "aws_region_name": "us-east-1",
                },
            ),
            # gcp_service_account — service_account_json redacted, project/location preserved
            (
                "gcp_service_account",
                {
                    "service_account_json": '{"type":"service_account","private_key":"secret"}',
                    "vertex_project": "my-project",
                    "vertex_location": "us-central1",
                    "type": "gcp_service_account",
                },
                "secret",
                {
                    "vertex_project": "my-project",
                    "vertex_location": "us-central1",
                },
            ),
            # none — type removed, empty authConfig
            (
                "none",
                {"type": "none"},
                None,
                {},
            ),
        ],
    )
    def test_credential_filtering_by_auth_type(
        self, platform_api_client, seed_model, enable_model_config_feature_flag,
        auth_type, stored_config, expected_secret_text, expected_config,
    ):
        """Secrets are redacted based on auth type while public fields are preserved."""
        alias = f"test-cred-{auth_type}"
        seed_model(
            alias=alias,
            model_auth_type=auth_type,
            model_auth_config=stored_config,
        )

        response = platform_api_client.get(f"/api/v1/platform/models/{alias}")
        assert response.status_code == 200

        if expected_secret_text:
            assert expected_secret_text not in response.text

        data = response.json()["data"]
        assert data["authConfig"] == expected_config

    # -- 404 errors -----------------------------------------------------------

    def test_get_model_returns_404_for_nonexistent_alias(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        response = platform_api_client.get("/api/v1/platform/models/nonexistent-model")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "could not find" in data["detail"].lower()

    def test_update_model_not_found_returns_404(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        response = platform_api_client.put(
            "/api/v1/platform/models/nonexistent",
            json={"description": "Updated description"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "could not find" in data["detail"].lower()

    def test_delete_model_not_found_returns_404(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        response = platform_api_client.delete("/api/v1/platform/models/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "could not find" in data["detail"].lower()

    # -- List models ----------------------------------------------------------

    def test_list_models_returns_correct_structure(
        self, platform_api_client, seed_model, enable_model_config_feature_flag,
    ):
        """GET /models returns a list with correct structure and camelCase fields."""
        for i in range(3):
            seed_model(alias=f"list-model-{i}", model_name=f"gpt-{i}")

        response = platform_api_client.get("/api/v1/platform/models")
        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 3

        for config in data["data"]:
            assert "modelName" in config
            assert "model_name" not in config
            assert "authType" in config
            assert "createdTime" in config
            assert "updatedTime" in config

    # -- Create ---------------------------------------------------------------

    def test_create_model_success(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        """POST /models creates a new model configuration."""
        request_data = {
            "alias": "test-create-gpt4",
            "provider": "openai",
            "modelName": "gpt-4",
            "apiBase": "https://api.openai.com/v1",
            "authConfig": {"api_key": "sk-secret-key", "type": "apikey"},
            "modelParams": {"temperature": 0.8, "max_tokens": 4096},
            "description": "Test created model",
        }

        response = platform_api_client.post("/api/v1/platform/models", json=request_data)
        assert response.status_code == 201

        data = response.json()["data"]
        assert data["alias"] == "test-create-gpt4"
        assert data["provider"] == "openai"
        assert data["modelName"] == "gpt-4"
        assert data["apiBase"] == "https://api.openai.com/v1"
        assert data["authType"] == "apikey"
        assert data["modelParams"]["temperature"] == 0.8
        assert data["modelParams"]["max_tokens"] == 4096
        assert data["description"] == "Test created model"

        # Server-assigned fields
        for field in ("id", "createdBy", "updatedBy", "createdTime", "updatedTime"):
            assert field in data

        # Secret redacted
        assert "api_key" not in data["authConfig"]
        assert "sk-secret-key" not in response.text

    @pytest.mark.parametrize(
        "provider,model_name,auth_config,api_base",
        [
            ("openai", "gpt-4", {"api_key": "sk-test", "type": "apikey"}, None),
            ("anthropic", "claude-3-5-sonnet", {"api_key": "sk-ant", "type": "apikey"}, None),
            ("azure_openai", "azure/my-deploy", {"api_key": "az-key", "type": "apikey"}, "https://myresource.openai.azure.com/"),
            ("ollama", "ollama/llama2", {"type": "none"}, "http://localhost:11434"),
            (
                "bedrock",
                "bedrock/anthropic.claude-3",
                {
                    "aws_access_key_id": "AKIA1234",
                    "aws_secret_access_key": "secret",
                    "aws_region_name": "us-east-1",
                    "type": "aws_iam",
                },
                None,
            ),
            (
                "vertex_ai",
                "vertex_ai/gemini-1.5-pro",
                {
                    "service_account_json": '{"type":"service_account"}',
                    "vertex_project": "proj",
                    "vertex_location": "us-central1",
                    "type": "gcp_service_account",
                },
                None,
            ),
            ("custom", "my-custom-model", {"api_key": "sk-custom", "type": "apikey"}, "https://custom.example.com/v1"),
        ],
    )
    def test_create_model_with_various_providers(
        self, platform_api_client, enable_model_config_feature_flag,
        provider, model_name, auth_config, api_base,
    ):
        """POST /models succeeds for each supported provider + auth type combination."""
        alias = f"test-create-{provider}"
        request_data = {
            "alias": alias,
            "provider": provider,
            "modelName": model_name,
            "authConfig": auth_config,
        }
        if api_base:
            request_data["apiBase"] = api_base

        response = platform_api_client.post("/api/v1/platform/models", json=request_data)
        assert response.status_code == 201

        data = response.json()["data"]
        assert data["alias"] == alias
        assert data["provider"] == provider
        assert data["modelName"] == model_name

    def test_create_model_duplicate_alias_returns_409(
        self, platform_api_client, seed_model, enable_model_config_feature_flag,
    ):
        """POST /models returns 409 when alias already exists."""
        seed_model(alias="existing-model")

        request_data = {
            "alias": "existing-model",
            "provider": "openai",
            "modelName": "gpt-4",
        }
        response = platform_api_client.post("/api/v1/platform/models", json=request_data)

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower()

    # -- Update ---------------------------------------------------------------

    def test_update_model_success(
        self, platform_api_client, seed_model, enable_model_config_feature_flag,
    ):
        """PUT /models/{alias} updates an existing model configuration."""
        seed_model(
            alias="test-update-model",
            model_auth_type="apikey",
            model_auth_config={"api_key": "sk-old-key", "type": "apikey"},
            model_params={"temperature": 0.5},
            description="Original description",
        )

        request_data = {
            "description": "Updated description",
            "modelParams": {"temperature": 0.7, "max_tokens": 2000},
        }
        response = platform_api_client.put(
            "/api/v1/platform/models/test-update-model", json=request_data,
        )

        assert response.status_code == 200

        data = response.json()["data"]
        assert data["alias"] == "test-update-model"
        assert data["description"] == "Updated description"
        assert data["modelParams"]["temperature"] == 0.7
        assert data["modelParams"]["max_tokens"] == 2000
        assert data["provider"] == "openai"
        assert data["modelName"] == "gpt-4"

    # -- Delete ---------------------------------------------------------------

    def test_delete_model_success(
        self, platform_api_client, seed_model, platform_db_session_factory,
        enable_model_config_feature_flag,
    ):
        """DELETE /models/{alias} deletes a model configuration."""
        seed_model(alias="test-delete-model")

        response = platform_api_client.delete("/api/v1/platform/models/test-delete-model")
        assert response.status_code == 204
        assert response.text == ""

        # Verify deletion at DB level
        db = platform_db_session_factory()
        deleted = db.query(ModelConfiguration).filter(
            ModelConfiguration.alias == "test-delete-model"
        ).first()
        db.close()
        assert deleted is None


# ---------------------------------------------------------------------------
# Supported models listing
# ---------------------------------------------------------------------------


class TestSupportedModelsAPI:
    """Tests for /api/v1/platform/supported-models endpoints."""

    def test_list_supported_models_returns_correct_structure(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        """POST /supported-models returns models with required fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "gpt-4", "object": "model"},
                {"id": "gpt-3.5-turbo", "object": "model"},
            ],
        }
        mock_response.status_code = 200

        with patch(
            "solace_agent_mesh.services.platform.services.model_list_service.httpx.Client.get",
            return_value=mock_response,
        ):
            response = platform_api_client.post(
                "/api/v1/platform/supported-models",
                json={"provider": "openai", "auth_type": "apikey", "api_key": "sk-test-key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

        for model in data["data"]:
            assert "id" in model
            assert "label" in model
            assert "provider" in model
            assert model["provider"] == "openai"

    @pytest.mark.parametrize("provider", ["openai", "anthropic"])
    def test_list_supported_models_accepts_various_providers(
        self, platform_api_client, enable_model_config_feature_flag, provider,
    ):
        """POST /supported-models works for different provider IDs."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.status_code = 200

        with patch(
            "solace_agent_mesh.services.platform.services.model_list_service.httpx.Client.get",
            return_value=mock_response,
        ):
            response = platform_api_client.post(
                "/api/v1/platform/supported-models",
                json={"provider": provider, "auth_type": "apikey", "api_key": "sk-test-key"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


class TestModelConnectionAPI:
    """Tests for /api/v1/platform/models/test endpoint."""

    def test_connection_with_valid_apikey_returns_success(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm") as mock_litellm:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_litellm.completion.return_value = mock_response

            response = platform_api_client.post(
                "/api/v1/platform/models/test",
                json={
                    "provider": "openai",
                    "model_name": "gpt-4",
                    "auth_type": "apikey",
                    "api_key": "sk-test-key-valid",
                },
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is True
        assert "successful" in data["message"].lower()

    def test_connection_with_stored_credentials_via_alias(
        self, platform_api_client, seed_model, enable_model_config_feature_flag,
    ):
        """test_connection uses stored credentials when alias is provided."""
        seed_model(
            alias="test-gpt4-stored",
            api_base="https://api.openai.com/v1",
            model_auth_type="apikey",
            model_auth_config={"api_key": "sk-stored-key-12345", "type": "apikey"},
            description="Test model with stored credentials",
        )

        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm") as mock_litellm:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_litellm.completion.return_value = mock_response

            response = platform_api_client.post(
                "/api/v1/platform/models/test",
                json={"alias": "test-gpt4-stored"},
            )

            assert response.status_code == 200
            assert response.json()["data"]["success"] is True

            call_kwargs = mock_litellm.completion.call_args[1]
            assert call_kwargs["api_key"] == "sk-stored-key-12345"

    def test_connection_missing_alias_and_auth_returns_error(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        response = platform_api_client.post(
            "/api/v1/platform/models/test",
            json={"provider": "openai", "model_name": "gpt-4"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is False
        assert "failed" in data["message"].lower()

    def test_connection_nonexistent_alias_returns_error(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        response = platform_api_client.post(
            "/api/v1/platform/models/test",
            json={"alias": "nonexistent-model-alias"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is False
        assert "not found" in data["message"].lower()

    def test_connection_with_litellm_unavailable(
        self, platform_api_client, enable_model_config_feature_flag,
    ):
        with patch("solace_agent_mesh.services.platform.services.model_config_service.litellm", None):
            response = platform_api_client.post(
                "/api/v1/platform/models/test",
                json={
                    "provider": "openai",
                    "model_name": "gpt-4",
                    "auth_type": "apikey",
                    "api_key": "sk-test-key",
                },
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["success"] is False
        assert "litellm" in data["message"].lower()
