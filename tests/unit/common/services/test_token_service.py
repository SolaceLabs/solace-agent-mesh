#!/usr/bin/env python3

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solace_agent_mesh.common.services.token_service import (
    TokenService,
    TokenServiceRegistry,
)


@pytest.fixture
def mock_component():
    component = MagicMock()
    component.log_identifier = "[TestComponent]"
    return component


@pytest.fixture
def token_service(mock_component):
    return TokenService(mock_component)


@pytest.fixture
def mock_httpx_client():
    with patch('solace_agent_mesh.common.services.token_service.httpx.AsyncClient') as mock_client:
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        mock_client.return_value.__aexit__.return_value = None
        yield client_instance


class TestValidateTokenWithFallback:
    @pytest.mark.asyncio
    async def test_validate_idp_token_success(self, token_service, mock_httpx_client):
        validation_response = MagicMock()
        validation_response.status_code = 200

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "sub": "user123",
            "email": "user@example.com",
            "name": "Test User"
        }

        mock_httpx_client.post.return_value = validation_response
        mock_httpx_client.get.return_value = userinfo_response

        result = await token_service.validate_token_with_fallback(
            token="valid_token",
            auth_service_url="http://auth-service",
            auth_provider="azure"
        )

        assert result is not None
        assert result["sub"] == "user123"
        assert result["email"] == "user@example.com"
        assert result["name"] == "Test User"

        mock_httpx_client.post.assert_called_once_with(
            "http://auth-service/is_token_valid",
            json={"provider": "azure"},
            headers={"Authorization": "Bearer valid_token"}
        )
        mock_httpx_client.get.assert_called_once_with(
            "http://auth-service/user_info?provider=azure",
            headers={"Authorization": "Bearer valid_token"}
        )

    @pytest.mark.asyncio
    async def test_validate_token_validation_failed(self, token_service, mock_httpx_client):
        validation_response = MagicMock()
        validation_response.status_code = 401
        mock_httpx_client.post.return_value = validation_response

        result = await token_service.validate_token_with_fallback(
            token="invalid_token",
            auth_service_url="http://auth-service",
            auth_provider="azure"
        )

        assert result is None
        assert mock_httpx_client.get.call_count == 0

    @pytest.mark.asyncio
    async def test_validate_token_userinfo_failed(self, token_service, mock_httpx_client):
        validation_response = MagicMock()
        validation_response.status_code = 200

        userinfo_response = MagicMock()
        userinfo_response.status_code = 500

        mock_httpx_client.post.return_value = validation_response
        mock_httpx_client.get.return_value = userinfo_response

        result = await token_service.validate_token_with_fallback(
            token="valid_token",
            auth_service_url="http://auth-service",
            auth_provider="azure"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_missing_auth_service_url(self, token_service):
        result = await token_service.validate_token_with_fallback(
            token="test_token",
            auth_service_url=None,
            auth_provider="azure"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_missing_auth_provider(self, token_service):
        result = await token_service.validate_token_with_fallback(
            token="test_token",
            auth_service_url="http://auth-service",
            auth_provider=None
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_http_request_error(self, token_service, mock_httpx_client):
        import httpx
        mock_httpx_client.post.side_effect = httpx.RequestError("Connection failed")

        result = await token_service.validate_token_with_fallback(
            token="test_token",
            auth_service_url="http://auth-service",
            auth_provider="azure"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_token_unexpected_error(self, token_service, mock_httpx_client):
        mock_httpx_client.post.side_effect = Exception("Unexpected error")

        result = await token_service.validate_token_with_fallback(
            token="test_token",
            auth_service_url="http://auth-service",
            auth_provider="azure"
        )

        assert result is None

def test_is_sam_token_base_implementation(token_service):
    """Base implementation doesn't mint SAM tokens."""
    assert token_service.is_sam_token("any_token") is False
    assert token_service.is_sam_token("idp_token_123") is False
    assert token_service.is_sam_token("") is False


@pytest.mark.asyncio
async def test_get_access_token_passthrough(token_service):
    """Base implementation returns IdP token unchanged."""
    idp_token = "idp_access_token_123"
    user_claims = {"sub": "user123", "email": "user@example.com"}

    result = await token_service.get_access_token(
        idp_access_token=idp_token,
        user_claims=user_claims
    )

    assert result == idp_token


@pytest.mark.asyncio
async def test_get_access_token_without_claims(token_service):
    idp_token = "idp_access_token_456"

    result = await token_service.get_access_token(
        idp_access_token=idp_token,
        user_claims=None
    )

    assert result == idp_token


@pytest.mark.asyncio
async def test_get_access_token_empty_claims(token_service):
    idp_token = "idp_access_token_789"

    result = await token_service.get_access_token(
        idp_access_token=idp_token,
        user_claims={}
    )

    assert result == idp_token


def test_extract_claims_full(token_service):
    verified_claims = {
        "sub": "user123",
        "email": "user@example.com",
        "name": "Test User",
        "roles": ["admin", "developer"],
        "scopes": ["read", "write"]
    }

    result = token_service.extract_token_claims(verified_claims)

    assert result["sub"] == "user123"
    assert result["email"] == "user@example.com"
    assert result["name"] == "Test User"
    assert result["roles"] == ["admin", "developer"]
    assert result["scopes"] == ["read", "write"]


def test_extract_claims_minimal(token_service):
    verified_claims = {"sub": "user123"}

    result = token_service.extract_token_claims(verified_claims)

    assert result["sub"] == "user123"
    assert result["email"] is None
    assert result["name"] is None
    assert result["roles"] == []
    assert result["scopes"] == []


def test_extract_claims_empty(token_service):
    verified_claims = {}

    result = token_service.extract_token_claims(verified_claims)

    assert result["sub"] is None
    assert result["email"] is None
    assert result["name"] is None
    assert result["roles"] == []
    assert result["scopes"] == []


class TestTokenServiceRegistry:
    def test_default_service_class(self):
        service_class = TokenServiceRegistry.get_token_service_class()
        assert service_class == TokenService

    def test_bind_custom_service(self):
        class CustomTokenService(TokenService):
            pass

        TokenServiceRegistry.bind_token_service(CustomTokenService)
        service_class = TokenServiceRegistry.get_token_service_class()

        assert service_class == CustomTokenService

        TokenServiceRegistry.bind_token_service(TokenService)

    def test_registry_persistence(self):
        class AnotherCustomService(TokenService):
            pass

        TokenServiceRegistry.bind_token_service(AnotherCustomService)

        assert TokenServiceRegistry.get_token_service_class() == AnotherCustomService
        assert TokenServiceRegistry.get_token_service_class() == AnotherCustomService

        TokenServiceRegistry.bind_token_service(TokenService)


def test_init_with_component(mock_component):
    service = TokenService(mock_component)

    assert service.component == mock_component
    assert service.log_identifier == "[TestComponent]"


def test_init_with_component_no_log_identifier():
    component = MagicMock()
    del component.log_identifier

    service = TokenService(component)

    assert service.component == component
    assert service.log_identifier == "TokenService"
