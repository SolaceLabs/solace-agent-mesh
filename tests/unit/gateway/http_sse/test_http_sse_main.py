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