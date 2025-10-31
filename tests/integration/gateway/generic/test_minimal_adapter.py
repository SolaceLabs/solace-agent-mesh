"""
Integration tests for GenericGatewayComponent with MinimalAdapter.

These tests verify basic gateway functionality using a simple adapter,
testing the full integration without mocking internal components.
"""

import asyncio
import pytest
import time

from solace_agent_mesh.gateway.generic.component import GenericGatewayComponent
from tests.integration.gateway.generic.fixtures.mock_adapters import MinimalAdapter
from tests.integration.gateway.generic.conftest import simple_llm_response


@pytest.mark.asyncio
async def test_minimal_adapter_initialization(minimal_gateway_component):
    """Test that MinimalAdapter initializes correctly"""
    # Arrange & Act - component is already initialized by fixture

    # Assert
    assert minimal_gateway_component is not None
    assert isinstance(minimal_gateway_component, GenericGatewayComponent)
    assert isinstance(minimal_gateway_component.adapter, MinimalAdapter)
    assert minimal_gateway_component.adapter.context is not None


@pytest.mark.asyncio
async def test_simple_text_input_submission(minimal_gateway_component, test_llm_server):
    """Test submitting a simple text input through the gateway"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Test agent response"))
    external_input = {
        "text": "Hello, agent!",
        "user_id": "test-user@example.com",
    }

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Assert - task was created
    assert task_id is not None
    assert isinstance(task_id, str)

    # Verify task context was created
    context = minimal_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert context["user_identity"]["id"] == "test-user@example.com"


@pytest.mark.asyncio
async def test_adapter_receives_task_completion(
    minimal_gateway_component, test_llm_server
):
    """Test that adapter's handle_task_complete is called"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Completed successfully"))
    adapter = minimal_gateway_component.adapter
    external_input = {"text": "Complete this task", "user_id": "completion-test@example.com"}

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Wait for task completion
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if task_id in adapter.completed_tasks:
            break
        await asyncio.sleep(0.1)

    # Assert
    assert task_id in adapter.completed_tasks, f"Task {task_id} not completed within {max_wait}s"


@pytest.mark.asyncio
async def test_adapter_receives_updates(minimal_gateway_component, test_llm_server):
    """Test that adapter receives streaming updates"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Agent response text"))
    adapter = minimal_gateway_component.adapter
    external_input = {"text": "Send me updates", "user_id": "updates-test@example.com"}

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Wait for updates
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if len(adapter.received_updates) > 0:
            break
        await asyncio.sleep(0.1)

    # Assert - adapter received at least one update
    assert len(adapter.received_updates) > 0, "Adapter did not receive any updates"

    # Verify update structure
    update, context = adapter.received_updates[0]
    assert update is not None
    assert context is not None
    assert context.task_id == task_id
    assert context.user_id == "updates-test@example.com"


@pytest.mark.asyncio
async def test_custom_session_id(minimal_gateway_component, test_llm_server):
    """Test that custom session_id is preserved"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Session test response"))
    custom_session = "custom-session-123"
    external_input = {
        "text": "Test with custom session",
        "session_id": custom_session,
        "user_id": "session-test@example.com",
    }

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Assert
    context = minimal_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert context["a2a_session_id"] == custom_session


@pytest.mark.asyncio
async def test_custom_target_agent(minimal_gateway_component, test_llm_server):
    """Test that custom target_agent is used"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Response from custom agent"))
    external_input = {
        "text": "Route to specific agent",
        "target_agent": "TestPeerAgentA",
        "user_id": "routing-test@example.com",
    }

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Assert - just verify task was created successfully
    # The actual target agent routing is tested at lower levels
    context = minimal_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert task_id is not None


@pytest.mark.asyncio
async def test_fallback_to_default_user(minimal_gateway_component, test_llm_server):
    """Test fallback when no auth claims are provided"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Default user response"))
    # Don't provide user_id - should fall back to default
    external_input = {"text": "Test with default user"}

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Assert
    context = minimal_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    # Should use the adapter's default_user_id
    assert context["user_identity"]["id"] == "minimal-user@example.com"


@pytest.mark.asyncio
async def test_platform_context_preservation(minimal_gateway_component, test_llm_server):
    """Test that platform_context is preserved through the flow"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Context preservation test"))
    adapter = minimal_gateway_component.adapter
    external_input = {
        "text": "Test context preservation",
        "user_id": "context-test@example.com",
    }

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

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
    assert response_context.platform_context is not None
    # Should have the platform context from the adapter's prepare_task
    assert response_context.platform_context.get("source") == "minimal_adapter"


@pytest.mark.asyncio
async def test_concurrent_tasks(minimal_gateway_component, test_llm_server):
    """Test that gateway can handle multiple concurrent tasks"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Concurrent response"))
    tasks_count = 3
    external_inputs = [
        {"text": f"Task {i}", "user_id": f"user-{i}@example.com"}
        for i in range(tasks_count)
    ]

    # Act - submit multiple tasks concurrently
    task_ids = await asyncio.gather(
        *[minimal_gateway_component.handle_external_input(inp) for inp in external_inputs]
    )

    # Assert - all tasks were created
    assert len(task_ids) == tasks_count
    assert len(set(task_ids)) == tasks_count  # All unique

    # Wait for all completions
    adapter = minimal_gateway_component.adapter
    max_wait = 15
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if len(adapter.completed_tasks) >= tasks_count:
            break
        await asyncio.sleep(0.1)

    # All tasks should complete
    assert len(adapter.completed_tasks) >= tasks_count


@pytest.mark.asyncio
async def test_empty_text_handling(minimal_gateway_component, test_llm_server):
    """Test handling of empty text input"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Empty text response"))
    external_input = {"text": "", "user_id": "empty-test@example.com"}

    # Act & Assert - should not raise an error
    task_id = await minimal_gateway_component.handle_external_input(external_input)
    assert task_id is not None


@pytest.mark.asyncio
async def test_adapter_config_accessible(minimal_gateway_component):
    """Test that adapter can access its configuration"""
    # Arrange & Act
    adapter = minimal_gateway_component.adapter
    config = adapter.context.adapter_config

    # Assert
    assert config is not None
    assert config.default_user_id == "minimal-user@example.com"
    assert config.default_target_agent == "TestAgent"
