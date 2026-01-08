"""
Integration tests for authentication flows in GenericGatewayComponent.

Tests various authentication scenarios including token-based auth,
email-based auth, platform IDs, and fallback mechanisms.
"""

import asyncio
import pytest
import time

from tests.integration.gateway.generic.fixtures.mock_adapters import AuthTestAdapter
from tests.integration.gateway.generic.conftest import simple_llm_response


@pytest.mark.asyncio
async def test_email_based_authentication(auth_gateway_component, test_llm_server):
    """Test authentication with email address"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Email auth response"))
    external_input = {
        "auth_type": "email",
        "email": "john.doe@company.com",
        "text": "Test email auth",
    }

    # Act
    task_id = await auth_gateway_component.handle_external_input(external_input)

    # Assert
    context = auth_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert context["user_identity"]["id"] == "john.doe@company.com"
    assert context["user_identity"]["email"] == "john.doe@company.com"
    assert context["user_identity"]["source"] == "email_auth"


@pytest.mark.asyncio
async def test_token_based_authentication(auth_gateway_component, test_llm_server):
    """Test authentication with bearer token"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Token auth response"))
    external_input = {
        "auth_type": "token",
        "token": "valid-test-token",
        "user_id": "token-user-123",
        "text": "Test token auth",
    }

    # Act
    task_id = await auth_gateway_component.handle_external_input(external_input)

    # Assert
    context = auth_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert context["user_identity"]["id"] == "token-user-123"
    assert context["user_identity"]["token"] == "valid-test-token"
    assert context["user_identity"]["token_type"] == "bearer"
    assert context["user_identity"]["source"] == "token_auth"


@pytest.mark.asyncio
async def test_platform_id_authentication(auth_gateway_component, test_llm_server):
    """Test authentication with platform-specific ID (no email)"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Platform auth response"))
    external_input = {
        "auth_type": "platform_id",
        "platform_user_id": "SLACK_U123456",
        "text": "Test platform auth",
    }

    # Act
    task_id = await auth_gateway_component.handle_external_input(external_input)

    # Assert
    context = auth_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert context["user_identity"]["id"] == "platform:SLACK_U123456"
    assert context["user_identity"]["source"] == "platform_auth"
    assert context["user_identity"]["raw_context"]["platform_id"] == "SLACK_U123456"


@pytest.mark.asyncio
async def test_no_auth_claims_fallback(auth_gateway_component, test_llm_server):
    """Test fallback to default_user_identity when no auth claims"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Fallback auth response"))
    external_input = {
        "auth_type": "none",  # Adapter returns None
        "text": "Test fallback auth",
    }

    # Act
    task_id = await auth_gateway_component.handle_external_input(external_input)

    # Assert
    context = auth_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    # Should use default_user_identity from config
    assert context["user_identity"]["id"] == "fallback-user@example.com"


@pytest.mark.asyncio
async def test_invalid_token_rejected(auth_gateway_component):
    """Test that invalid token causes authentication failure"""
    # Arrange
    # Enable token requirement
    auth_gateway_component.adapter.context.adapter_config.require_token = True
    external_input = {
        "auth_type": "token",
        "token": "invalid-token",
        "user_id": "hacker@malicious.com",
        "text": "Attempt with bad token",
    }

    # Act & Assert - should raise PermissionError
    with pytest.raises(PermissionError, match="Invalid token"):
        await auth_gateway_component.handle_external_input(external_input)


@pytest.mark.asyncio
async def test_auth_attempts_tracking(auth_gateway_component, test_llm_server):
    """Test that adapter can track authentication attempts"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Tracking test response"))
    adapter = auth_gateway_component.adapter
    initial_count = len(adapter.auth_attempts)

    external_inputs = [
        {"auth_type": "email", "email": "user1@example.com", "text": "Test 1"},
        {"auth_type": "token", "token": "token123", "user_id": "user2", "text": "Test 2"},
        {"auth_type": "platform_id", "platform_user_id": "P123", "text": "Test 3"},
    ]

    # Act
    for inp in external_inputs:
        await auth_gateway_component.handle_external_input(inp)

    # Assert
    assert len(adapter.auth_attempts) == initial_count + 3
    # Verify different auth types were captured
    auth_types = [attempt["auth_type"] for attempt in adapter.auth_attempts[-3:]]
    assert "email" in auth_types
    assert "token" in auth_types
    assert "platform_id" in auth_types


@pytest.mark.asyncio
async def test_auth_claims_preserved_in_response_context(
    auth_gateway_component, test_llm_server
):
    """Test that auth claims are available in response context"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Response with auth context"))
    adapter = auth_gateway_component.adapter
    external_input = {
        "auth_type": "email",
        "email": "authenticated@example.com",
        "text": "Test auth in response",
    }

    # Act
    task_id = await auth_gateway_component.handle_external_input(external_input)

    # Wait for updates
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if len(adapter.received_updates) > 0:
            break
        await asyncio.sleep(0.1)

    # Assert
    assert len(adapter.received_updates) > 0
    _, response_context = adapter.received_updates[0]
    assert response_context.user_id == "authenticated@example.com"


@pytest.mark.asyncio
async def test_multiple_users_concurrent_auth(auth_gateway_component, test_llm_server):
    """Test concurrent authentication for different users"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Concurrent auth response"))
    external_inputs = [
        {"auth_type": "email", "email": f"user{i}@example.com", "text": f"Task {i}"}
        for i in range(5)
    ]

    # Act
    task_ids = await asyncio.gather(
        *[auth_gateway_component.handle_external_input(inp) for inp in external_inputs]
    )

    # Assert - all tasks created with different users
    assert len(task_ids) == 5
    user_ids = []
    for task_id in task_ids:
        context = auth_gateway_component.task_context_manager.get_context(task_id)
        user_ids.append(context["user_identity"]["id"])

    assert len(set(user_ids)) == 5  # All unique users
    for i in range(5):
        assert f"user{i}@example.com" in user_ids


@pytest.mark.asyncio
async def test_auth_source_propagation(auth_gateway_component, test_llm_server):
    """Test that auth source is correctly propagated"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Source propagation test"))
    test_cases = [
        ("email", "email_auth"),
        ("token", "token_auth"),
        ("platform_id", "platform_auth"),
    ]

    for auth_type, expected_source in test_cases:
        # Act
        external_input = {
            "auth_type": auth_type,
            "email": "test@example.com",
            "token": "test-token",
            "user_id": "test-user",
            "platform_user_id": "P123",
            "text": f"Test {auth_type}",
        }
        task_id = await auth_gateway_component.handle_external_input(external_input)

        # Assert
        context = auth_gateway_component.task_context_manager.get_context(task_id)
        assert context["user_identity"]["source"] == expected_source, (
            f"Auth source mismatch for {auth_type}"
        )
