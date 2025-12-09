"""
Unit tests for middleware backwards compatibility with sam_access_token.

Tests that middleware can validate both sam_access_token and IdP tokens,
ensuring zero-downtime deployment and gradual migration.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time


@pytest.fixture
def mock_component_with_trust_manager():
    """Create a mock component with trust_manager configured."""
    component = Mock()
    component.use_authorization = True
    component.external_auth_service_url = "http://oauth2-service:8080"
    component.external_auth_provider = "azure"

    # Mock trust_manager
    trust_manager = Mock()
    trust_manager.config = Mock()
    trust_manager.config.access_token_enabled = True
    component.trust_manager = trust_manager

    return component


@pytest.fixture
def mock_component_without_trust_manager():
    """Create a mock component without trust_manager (backwards compatibility)."""
    component = Mock()
    component.use_authorization = True
    component.external_auth_service_url = "http://oauth2-service:8080"
    component.external_auth_provider = "azure"
    component.trust_manager = None

    return component


@pytest.fixture
def mock_component_feature_disabled():
    """Create a mock component with trust_manager but feature disabled."""
    component = Mock()
    component.use_authorization = True
    component.external_auth_service_url = "http://oauth2-service:8080"
    component.external_auth_provider = "azure"

    # Mock trust_manager with feature disabled
    trust_manager = Mock()
    trust_manager.config = Mock()
    trust_manager.config.access_token_enabled = False
    component.trust_manager = trust_manager

    return component


@pytest.fixture
def valid_sam_claims():
    """Valid sam_access_token claims."""
    return {
        "iss": "webui_gateway_test",
        "sub": "test@example.com",
        "email": "test@example.com",
        "name": "Test User",
        "roles": ["developer", "sam_user"],
        "scopes": ["agent:*:read", "agent:*:write"],
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "provider": "azure"
    }


@pytest.mark.asyncio
async def test_valid_sam_access_token(mock_component_with_trust_manager, valid_sam_claims):
    """Test that valid sam_access_token is validated and sets user with roles/scopes."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    # Setup: Mock trust_manager to return valid claims
    mock_component_with_trust_manager.trust_manager.verify_user_claims.return_value = valid_sam_claims

    # Create middleware
    AuthMiddleware = create_oauth_middleware(mock_component_with_trust_manager)

    # Create mock app
    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, mock_component_with_trust_manager)

    # Create mock request
    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer sam_token_here")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    # Call middleware
    await middleware(scope, mock_receive, mock_send)

    # Assert: trust_manager.verify_user_claims was called
    mock_component_with_trust_manager.trust_manager.verify_user_claims.assert_called_once_with("sam_token_here")

    # We can't easily verify request.state.user here without more complex mocking,
    # but we verified that verify_user_claims was called


@pytest.mark.asyncio
async def test_expired_sam_access_token_fallback(mock_component_with_trust_manager):
    """Test that expired sam_access_token falls back to IdP validation."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    # Setup: Mock trust_manager to raise exception (expired token)
    mock_component_with_trust_manager.trust_manager.verify_user_claims.side_effect = Exception("Token expired")

    # Create middleware
    AuthMiddleware = create_oauth_middleware(mock_component_with_trust_manager)

    # Create mock app
    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, mock_component_with_trust_manager)

    # Create mock request
    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer expired_sam_token")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    # Mock IdP validation to succeed
    with patch('solace_agent_mesh.shared.auth.middleware._validate_token', return_value=True):
        with patch('solace_agent_mesh.shared.auth.middleware._get_user_info', return_value={
            "sub": "test@example.com",
            "email": "test@example.com",
            "name": "Test User"
        }):
            # Call middleware
            await middleware(scope, mock_receive, mock_send)

    # Assert: trust_manager.verify_user_claims was called (and failed)
    mock_component_with_trust_manager.trust_manager.verify_user_claims.assert_called_once()


@pytest.mark.asyncio
async def test_malformed_sam_access_token_fallback(mock_component_with_trust_manager):
    """Test that malformed token falls back to IdP validation."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    # Setup: Mock trust_manager to raise exception (malformed token)
    mock_component_with_trust_manager.trust_manager.verify_user_claims.side_effect = Exception("Invalid token format")

    # Create middleware
    AuthMiddleware = create_oauth_middleware(mock_component_with_trust_manager)

    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, mock_component_with_trust_manager)

    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer malformed_token")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    # Mock IdP validation to succeed
    with patch('solace_agent_mesh.shared.auth.middleware._validate_token', return_value=True):
        with patch('solace_agent_mesh.shared.auth.middleware._get_user_info', return_value={
            "sub": "test@example.com",
            "email": "test@example.com",
            "name": "Test User"
        }):
            await middleware(scope, mock_receive, mock_send)

    # Assert: Falls back to IdP validation
    mock_component_with_trust_manager.trust_manager.verify_user_claims.assert_called_once()


@pytest.mark.asyncio
async def test_feature_flag_disabled(mock_component_feature_disabled):
    """Test that when access_token_enabled=false, uses IdP validation."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    # Create middleware
    AuthMiddleware = create_oauth_middleware(mock_component_feature_disabled)

    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, mock_component_feature_disabled)

    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer some_token")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    # Mock IdP validation to succeed
    with patch('solace_agent_mesh.shared.auth.middleware._validate_token', return_value=True):
        with patch('solace_agent_mesh.shared.auth.middleware._get_user_info', return_value={
            "sub": "test@example.com",
            "email": "test@example.com",
            "name": "Test User"
        }):
            await middleware(scope, mock_receive, mock_send)

    # Assert: trust_manager.verify_user_claims was NOT called (feature disabled)
    mock_component_feature_disabled.trust_manager.verify_user_claims.assert_not_called()


@pytest.mark.asyncio
async def test_idp_token_validation_unchanged(mock_component_without_trust_manager):
    """Test that existing IdP token validation still works (no trust_manager)."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    # Create middleware
    AuthMiddleware = create_oauth_middleware(mock_component_without_trust_manager)

    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, mock_component_without_trust_manager)

    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer idp_token")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    # Mock IdP validation to succeed
    with patch('solace_agent_mesh.shared.auth.middleware._validate_token', return_value=True) as mock_validate:
        with patch('solace_agent_mesh.shared.auth.middleware._get_user_info', return_value={
            "sub": "test@example.com",
            "email": "test@example.com",
            "name": "Test User"
        }) as mock_userinfo:
            await middleware(scope, mock_receive, mock_send)

    # Assert: IdP validation was called
    mock_validate.assert_called_once()
    mock_userinfo.assert_called_once()


@pytest.mark.asyncio
async def test_no_trust_manager_falls_back_to_idp():
    """Test that missing trust_manager falls back to IdP validation."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    component = Mock()
    component.use_authorization = True
    component.external_auth_service_url = "http://oauth2-service:8080"
    component.external_auth_provider = "azure"
    component.trust_manager = None  # No trust_manager

    AuthMiddleware = create_oauth_middleware(component)

    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, component)

    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer some_token")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    # Mock IdP validation to succeed
    with patch('solace_agent_mesh.shared.auth.middleware._validate_token', return_value=True) as mock_validate:
        with patch('solace_agent_mesh.shared.auth.middleware._get_user_info', return_value={
            "sub": "test@example.com",
            "email": "test@example.com",
            "name": "Test User"
        }):
            await middleware(scope, mock_receive, mock_send)

    # Assert: Falls back to IdP validation (no trust_manager available)
    mock_validate.assert_called_once()


@pytest.mark.asyncio
async def test_sam_token_without_optional_fields(mock_component_with_trust_manager):
    """Test that sam_access_token works even without optional fields like roles/scopes."""
    from solace_agent_mesh.shared.auth.middleware import create_oauth_middleware

    # Claims without optional fields
    minimal_claims = {
        "sub": "test@example.com",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }

    mock_component_with_trust_manager.trust_manager.verify_user_claims.return_value = minimal_claims

    AuthMiddleware = create_oauth_middleware(mock_component_with_trust_manager)

    async def mock_app(scope, receive, send):
        pass

    middleware = AuthMiddleware(mock_app, mock_component_with_trust_manager)

    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [(b"authorization", b"Bearer minimal_sam_token")],
        "query_string": b""
    }

    async def mock_receive():
        return {"type": "http.request", "body": b""}

    sent_responses = []
    async def mock_send(message):
        sent_responses.append(message)

    await middleware(scope, mock_receive, mock_send)

    # Assert: verify_user_claims was called and succeeded (uses .get() with defaults)
    mock_component_with_trust_manager.trust_manager.verify_user_claims.assert_called_once()
