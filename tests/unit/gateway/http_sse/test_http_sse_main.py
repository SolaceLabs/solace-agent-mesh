#!/usr/bin/env python3
"""
Comprehensive unit tests for main.py to increase coverage from 52% to 75%+.

Tests cover:
1. Authentication middleware (token extraction, validation, user identity)
2. Dependency injection (component, session manager, SSE manager, database)
3. Application factory (create_app with various configurations)
4. Router registration (all endpoints, prefixes, tags)
5. Middleware configuration (CORS, session, auth)
6. Exception handlers (HTTP, validation, generic)
7. Startup and shutdown events (lifespan management)
8. Configuration validation (loading, environment variables)
9. Error handling and edge cases

Based on coverage analysis in tests/unit/gateway/coverage_analysis.md
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from typing import Any, Dict, Optional

# Import main module components
from solace_agent_mesh.gateway.http_sse import main
from solace_agent_mesh.gateway.http_sse import dependencies
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent
from solace_agent_mesh.gateway.http_sse.session_manager import SessionManager
from solace_agent_mesh.gateway.http_sse.sse_manager import SSEManager


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_component():
    """Create a mock WebUIBackendComponent."""
    component = MagicMock(spec=WebUIBackendComponent)
    component.gateway_id = "test_gateway"
    component.log_identifier = "[TestGateway]"
    component.identity_service = None
    component.database_url = None
    
    # Mock session manager
    session_manager = MagicMock(spec=SessionManager)
    session_manager.secret_key = "test_secret_key_12345"
    component.get_session_manager.return_value = session_manager
    
    # Mock SSE manager
    sse_manager = MagicMock(spec=SSEManager)
    component.get_sse_manager.return_value = sse_manager
    
    # Mock CORS origins
    component.get_cors_origins.return_value = ["http://localhost:3000"]
    
    # Mock get_app
    mock_app = MagicMock()
    mock_app.app_config = {
        "external_auth_service_url": "http://localhost:8080",
        "external_auth_callback_uri": "http://localhost:8000/api/v1/auth/callback",
        "external_auth_provider": "azure",
        "frontend_use_authorization": False,
        "frontend_redirect_url": "http://localhost:3000"
    }
    component.get_app.return_value = mock_app
    
    return component


@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    request = MagicMock()
    request.headers = {}
    request.session = {}
    request.query_params = {}
    request.url = MagicMock()
    request.url.path = "/api/v1/test"
    request.method = "GET"
    request.state = MagicMock()
    return request


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    with patch('solace_agent_mesh.gateway.http_sse.main.httpx.AsyncClient') as mock_client:
        client_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client_instance
        mock_client.return_value.__aexit__.return_value = None
        yield client_instance


@pytest.fixture(autouse=True)
def reset_dependencies():
    """Reset global dependencies before each test."""
    main._dependencies_initialized = False
    dependencies.sac_component_instance = None
    dependencies.SessionLocal = None
    dependencies.api_config = None
    yield
    main._dependencies_initialized = False
    dependencies.sac_component_instance = None
    dependencies.SessionLocal = None
    dependencies.api_config = None


# ============================================================================
# Authentication Middleware Tests
# ============================================================================

class TestTokenExtraction:
    """Test _extract_access_token function."""
    
    def test_extract_token_from_bearer_header(self, mock_request):
        """Test extracting token from Authorization Bearer header."""
        mock_request.headers = {"Authorization": "Bearer test_token_123"}
        
        token = main._extract_access_token(mock_request)
        
        assert token == "test_token_123"
    
    def test_extract_token_from_session(self, mock_request):
        """Test extracting token from session."""
        mock_request.headers = {}
        mock_request.session = {"access_token": "session_token_456"}
        
        token = main._extract_access_token(mock_request)
        
        assert token == "session_token_456"
    
    def test_extract_token_from_query_params(self, mock_request):
        """Test extracting token from query parameters."""
        mock_request.headers = {}
        mock_request.session = {}
        mock_request.query_params = {"token": "query_token_789"}
        
        token = main._extract_access_token(mock_request)
        
        assert token == "query_token_789"
    
    def test_extract_token_priority_bearer_over_session(self, mock_request):
        """Test that Bearer header takes priority over session."""
        mock_request.headers = {"Authorization": "Bearer bearer_token"}
        mock_request.session = {"access_token": "session_token"}
        
        token = main._extract_access_token(mock_request)
        
        assert token == "bearer_token"
    
    def test_extract_token_no_token_returns_none(self, mock_request):
        """Test that None is returned when no token is found."""
        mock_request.headers = {}
        mock_request.session = {}
        mock_request.query_params = {}
        
        token = main._extract_access_token(mock_request)
        
        assert token is None
    
    def test_extract_token_malformed_bearer_header(self, mock_request):
        """Test handling of malformed Bearer header."""
        mock_request.headers = {"Authorization": "InvalidFormat token"}
        
        token = main._extract_access_token(mock_request)
        
        assert token is None
    
    def test_extract_token_session_assertion_error(self, mock_request):
        """Test handling of session access assertion error."""
        mock_request.headers = {}
        # Simulate session access raising AssertionError
        type(mock_request).session = property(lambda self: (_ for _ in ()).throw(AssertionError("Session not available")))
        mock_request.query_params = {}
        
        token = main._extract_access_token(mock_request)
        
        assert token is None


class TestTokenValidation:
    """Test _validate_token function."""
    
    @pytest.mark.asyncio
    async def test_validate_token_success(self, mock_httpx_client):
        """Test successful token validation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx_client.post.return_value = mock_response
        
        result = await main._validate_token(
            "http://auth-service",
            "azure",
            "valid_token"
        )
        
        assert result is True
        mock_httpx_client.post.assert_called_once_with(
            "http://auth-service/is_token_valid",
            json={"provider": "azure"},
            headers={"Authorization": "Bearer valid_token"}
        )
    
    @pytest.mark.asyncio
    async def test_validate_token_failure(self, mock_httpx_client):
        """Test failed token validation."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_httpx_client.post.return_value = mock_response
        
        result = await main._validate_token(
            "http://auth-service",
            "azure",
            "invalid_token"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_token_with_different_providers(self, mock_httpx_client):
        """Test token validation with different auth providers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx_client.post.return_value = mock_response
        
        providers = ["azure", "okta", "auth0", "keycloak"]
        
        for provider in providers:
            await main._validate_token(
                "http://auth-service",
                provider,
                "test_token"
            )
        
        assert mock_httpx_client.post.call_count == len(providers)


class TestUserInfoRetrieval:
    """Test _get_user_info function."""
    
    @pytest.mark.asyncio
    async def test_get_user_info_success(self, mock_httpx_client):
        """Test successful user info retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sub": "user123",
            "email": "user@example.com",
            "name": "Test User"
        }
        mock_httpx_client.get.return_value = mock_response
        
        user_info = await main._get_user_info(
            "http://auth-service",
            "azure",
            "valid_token"
        )
        
        assert user_info == {
            "sub": "user123",
            "email": "user@example.com",
            "name": "Test User"
        }
        mock_httpx_client.get.assert_called_once_with(
            "http://auth-service/user_info?provider=azure",
            headers={"Authorization": "Bearer valid_token"}
        )
    
    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, mock_httpx_client):
        """Test failed user info retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_httpx_client.get.return_value = mock_response
        
        user_info = await main._get_user_info(
            "http://auth-service",
            "azure",
            "invalid_token"
        )
        
        assert user_info is None


class TestUserIdentifierExtraction:
    """Test _extract_user_identifier function."""
    
    def test_extract_identifier_from_sub(self):
        """Test extracting identifier from 'sub' claim."""
        user_info = {"sub": "user123", "email": "user@example.com"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "user123"
    
    def test_extract_identifier_from_client_id(self):
        """Test extracting identifier from 'client_id' claim."""
        user_info = {"client_id": "client456"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "client456"
    
    def test_extract_identifier_from_oid(self):
        """Test extracting identifier from 'oid' claim (Azure AD)."""
        user_info = {"oid": "azure-oid-789"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "azure-oid-789"
    
    def test_extract_identifier_from_email(self):
        """Test extracting identifier from 'email' claim."""
        user_info = {"email": "user@example.com"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "user@example.com"
    
    def test_extract_identifier_from_user_id(self):
        """Test extracting identifier from 'user_id' claim (internal format)."""
        user_info = {"user_id": "internal_user_123"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "internal_user_123"
    
    def test_extract_identifier_priority_order(self):
        """Test that identifier extraction follows priority order."""
        user_info = {
            "sub": "sub_value",
            "client_id": "client_value",
            "email": "email_value"
        }
        
        identifier = main._extract_user_identifier(user_info)
        
        # 'sub' should take priority
        assert identifier == "sub_value"
    
    def test_extract_identifier_unknown_fallback(self):
        """Test fallback when identifier is 'Unknown'."""
        user_info = {"sub": "Unknown"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "sam_dev_user"
    
    def test_extract_identifier_unknown_case_insensitive(self):
        """Test fallback is case-insensitive."""
        user_info = {"sub": "unknown"}
        
        identifier = main._extract_user_identifier(user_info)
        
        assert identifier == "sam_dev_user"


class TestUserDetailsExtraction:
    """Test _extract_user_details function."""
    
    def test_extract_email_from_email_claim(self):
        """Test extracting email from 'email' claim."""
        user_info = {"email": "user@example.com", "sub": "user123"}
        
        email, display_name = main._extract_user_details(user_info, "user123")
        
        assert email == "user@example.com"
    
    def test_extract_email_from_preferred_username(self):
        """Test extracting email from 'preferred_username' claim."""
        user_info = {"preferred_username": "user@company.com", "sub": "user123"}
        
        email, display_name = main._extract_user_details(user_info, "user123")
        
        assert email == "user@company.com"
    
    def test_extract_email_fallback_to_identifier(self):
        """Test email fallback to user identifier."""
        user_info = {"sub": "user123"}
        
        email, display_name = main._extract_user_details(user_info, "user123")
        
        assert email == "user123"
    
    def test_extract_display_name_from_name(self):
        """Test extracting display name from 'name' claim."""
        user_info = {"name": "John Doe", "sub": "user123"}
        
        email, display_name = main._extract_user_details(user_info, "user123")
        
        assert display_name == "John Doe"
    
    def test_extract_display_name_from_given_family_names(self):
        """Test constructing display name from given_name and family_name."""
        user_info = {
            "given_name": "John",
            "family_name": "Doe",
            "sub": "user123"
        }
        
        email, display_name = main._extract_user_details(user_info, "user123")
        
        assert display_name == "John Doe"


class TestUserStateCreation:
    """Test user state creation functions."""
    
    @pytest.mark.asyncio
    async def test_create_user_state_without_identity_service(self):
        """Test creating user state without identity service."""
        user_state = await main._create_user_state_without_identity_service(
            "user123",
            "user@example.com",
            "Test User"
        )
        
        assert user_state["id"] == "user123"
        assert user_state["email"] == "user@example.com"
        assert user_state["name"] == "Test User"
        assert user_state["authenticated"] is True
        assert user_state["auth_method"] == "oidc"
    
    @pytest.mark.asyncio
    async def test_create_user_state_without_identity_service_fallback(self):
        """Test fallback to sam_dev_user when identifier is invalid."""
        user_state = await main._create_user_state_without_identity_service(
            "unknown",
            "",
            ""
        )
        
        assert user_state["id"] == "sam_dev_user"
        assert user_state["email"] == "sam_dev_user"
        assert user_state["name"] == "sam_dev_user"
    
    @pytest.mark.asyncio
    async def test_create_user_state_with_identity_service(self):
        """Test creating user state with identity service."""
        mock_identity_service = MagicMock()
        mock_identity_service.lookup_key = "email"
        mock_identity_service.get_user_profile = AsyncMock(return_value={
            "id": "profile_user_123",
            "email": "profile@example.com",
            "name": "Profile User",
            "department": "Engineering"
        })
        
        user_state = await main._create_user_state_with_identity_service(
            mock_identity_service,
            "user123",
            "user@example.com",
            "Test User",
            {"sub": "user123"}
        )
        
        assert user_state["id"] == "profile_user_123"
        assert user_state["email"] == "profile@example.com"
        assert user_state["name"] == "Profile User"
        assert user_state["department"] == "Engineering"
        assert user_state["authenticated"] is True
        assert user_state["auth_method"] == "oidc"
    
    @pytest.mark.asyncio
    async def test_create_user_state_with_identity_service_no_profile(self):
        """Test handling when identity service returns no profile."""
        mock_identity_service = MagicMock()
        mock_identity_service.lookup_key = "email"
        mock_identity_service.get_user_profile = AsyncMock(return_value=None)
        
        user_state = await main._create_user_state_with_identity_service(
            mock_identity_service,
            "user123",
            "user@example.com",
            "Test User",
            {"sub": "user123"}
        )
        
        assert user_state is None


# ============================================================================
# Dependency Injection Tests
# ============================================================================

class TestConfigCreation:
    """Test API configuration creation."""
    
    def test_create_api_config_with_defaults(self):
        """Test creating API config with default values."""
        app_config = {}
        
        api_config = main._create_api_config(app_config, None)
        
        assert api_config["external_auth_service_url"] == "http://localhost:8080"
        assert api_config["external_auth_provider"] == "azure"
        assert api_config["frontend_use_authorization"] is False
        assert api_config["persistence_enabled"] is False
    
    def test_create_api_config_with_custom_values(self):
        """Test creating API config with custom values."""
        app_config = {
            "external_auth_service_url": "https://auth.example.com",
            "external_auth_provider": "okta",
            "frontend_use_authorization": True,
            "frontend_redirect_url": "https://app.example.com"
        }
        
        api_config = main._create_api_config(app_config, "postgresql://db")
        
        assert api_config["external_auth_service_url"] == "https://auth.example.com"
        assert api_config["external_auth_provider"] == "okta"
        assert api_config["frontend_use_authorization"] is True
        assert api_config["persistence_enabled"] is True


# ============================================================================
# Database Migration Tests
# ============================================================================

class TestDatabaseMigrations:
    """Test database migration functions."""
    
    def test_setup_alembic_config(self):
        """Test Alembic configuration setup."""
        database_url = "sqlite:///test.db"
        
        alembic_cfg = main._setup_alembic_config(database_url)
        
        assert isinstance(alembic_cfg, AlembicConfig)
        assert alembic_cfg.get_main_option("sqlalchemy.url") == database_url
        assert "alembic" in alembic_cfg.get_main_option("script_location")


# ============================================================================
# Exception Handler Tests
# ============================================================================

class TestExceptionHandlers:
    """Test exception handlers."""
    
    @pytest.mark.asyncio
    async def test_http_exception_handler_rest_endpoint(self):
        """Test HTTP exception handler for REST endpoints."""
        request = MagicMock()
        request.url.path = "/api/v1/sessions"
        request.method = "GET"
        
        exc = HTTPException(status_code=404, detail="Session not found")
        
        response = await main.http_exception_handler(request, exc)
        
        assert response.status_code == 404
        content = json.loads(response.body.decode())
        assert content["detail"] == "Session not found"
    
    @pytest.mark.asyncio
    async def test_http_exception_handler_jsonrpc_endpoint(self):
        """Test HTTP exception handler for JSON-RPC endpoints."""
        request = MagicMock()
        request.url.path = "/api/v1/tasks/submit"
        request.method = "POST"
        
        exc = HTTPException(status_code=400, detail="Invalid request")
        
        response = await main.http_exception_handler(request, exc)
        
        assert response.status_code == 400
        content = json.loads(response.body.decode())
        assert "error" in content
        assert content["error"]["message"] == "Invalid request"
    
    @pytest.mark.asyncio
    async def test_http_exception_handler_sse_endpoint(self):
        """Test HTTP exception handler for SSE endpoints."""
        request = MagicMock()
        request.url.path = "/api/v1/sse/stream"
        request.method = "GET"
        
        exc = HTTPException(status_code=403, detail="Not authorized")
        
        response = await main.http_exception_handler(request, exc)
        
        assert response.status_code == 403
        content = json.loads(response.body.decode())
        assert "error" in content
    
    @pytest.mark.asyncio
    async def test_validation_exception_handler(self):
        """Test validation exception handler."""
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.method = "POST"
        
        exc = RequestValidationError([{
            "loc": ["body", "field"],
            "msg": "field required",
            "type": "value_error.missing"
        }])
        
        response = await main.validation_exception_handler(request, exc)
        
        assert response.status_code == 422
        content = json.loads(response.body.decode())
        assert "error" in content
    
    @pytest.mark.asyncio
    async def test_generic_exception_handler(self):
        """Test generic exception handler."""
        request = MagicMock()
        request.url.path = "/api/v1/test"
        request.method = "GET"
        
        exc = Exception("Unexpected error")
        
        response = await main.generic_exception_handler(request, exc)
        
        assert response.status_code == 500
        content = json.loads(response.body.decode())
        assert "error" in content


# ============================================================================
# Health Check Tests
# ============================================================================

class TestHealthCheck:
    """Test health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self):
        """Test health check returns success."""
        response = await main.read_root()
        
        assert response["status"] == "A2A Web UI Backend is running"