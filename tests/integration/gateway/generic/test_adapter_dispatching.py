"""
Integration tests for base class handle_update() dispatching logic.

These tests verify that the default GatewayAdapter.handle_update() implementation
correctly dispatches different part types to their respective handlers.
"""

import asyncio
import pytest
import time

from solace_agent_mesh.gateway.adapter.types import SamDataPart, SamFilePart, SamTextPart
from tests.integration.gateway.generic.conftest import simple_llm_response


@pytest.mark.asyncio
async def test_text_part_dispatches_to_handle_text_chunk(dispatching_gateway_component, test_llm_server):
    """Test that text parts are dispatched to handle_text_chunk()"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Hello from agent"))
    adapter = dispatching_gateway_component.adapter
    external_input = {
        "text": "Send me a text response",
        "user_id": "dispatch-test@example.com"
    }

    # Act
    task_id = await dispatching_gateway_component.handle_external_input(external_input)

    # Wait for response
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if len(adapter.text_chunks) > 0:
            break
        await asyncio.sleep(0.1)

    # Assert
    assert len(adapter.text_chunks) > 0, "Text chunk not dispatched to handle_text_chunk()"
    text, context = adapter.text_chunks[0]
    assert text == "Hello from agent"
    assert context.task_id == task_id


@pytest.mark.asyncio
async def test_multiple_text_parts_dispatched(dispatching_gateway_component, test_llm_server):
    """Test that multiple text updates are all dispatched"""
    # Arrange - use prime_responses to simulate streaming
    test_llm_server.prime_responses([
        simple_llm_response("First chunk"),
        simple_llm_response("Second chunk"),
        simple_llm_response("Third chunk"),
    ])
    adapter = dispatching_gateway_component.adapter
    external_inputs = [
        {"text": f"Request {i}", "user_id": "dispatch-test@example.com"}
        for i in range(3)
    ]

    # Act
    for inp in external_inputs:
        await dispatching_gateway_component.handle_external_input(inp)
        await asyncio.sleep(0.2)

    # Wait for all responses
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if len(adapter.text_chunks) >= 3:
            break
        await asyncio.sleep(0.1)

    # Assert
    assert len(adapter.text_chunks) >= 3, f"Expected at least 3 text chunks, got {len(adapter.text_chunks)}"
    texts = [text for text, _ in adapter.text_chunks]
    assert "First chunk" in texts
    assert "Second chunk" in texts
    assert "Third chunk" in texts


@pytest.mark.asyncio
async def test_agent_progress_update_dispatches_to_handle_status_update(dispatching_gateway_component):
    """Test that agent_progress_update data parts dispatch to handle_status_update()"""
    # This test directly calls the adapter to verify dispatching logic
    # since we don't have a way to make the agent send progress updates in the test environment
    from solace_agent_mesh.gateway.adapter.types import ResponseContext, SamUpdate

    # Arrange
    adapter = dispatching_gateway_component.adapter
    progress_update = SamUpdate(parts=[
        SamDataPart(data={
            "type": "agent_progress_update",
            "status_text": "Processing your request..."
        })
    ])
    context = ResponseContext(
        task_id="test-task-123",
        session_id="test-session",
        user_id="test@example.com",
        platform_context={}
    )

    # Act - call handle_update directly (which uses base class default)
    await adapter.handle_update(progress_update, context)

    # Assert
    assert len(adapter.status_updates) == 1, "Status update not dispatched to handle_status_update()"
    status_text, received_context = adapter.status_updates[0]
    assert status_text == "Processing your request..."
    assert received_context.task_id == "test-task-123"


@pytest.mark.asyncio
async def test_generic_data_part_dispatches_to_handle_data_part(dispatching_gateway_component):
    """Test that non-special data parts dispatch to handle_data_part()"""
    from solace_agent_mesh.gateway.adapter.types import ResponseContext, SamUpdate

    # Arrange
    adapter = dispatching_gateway_component.adapter
    data_update = SamUpdate(parts=[
        SamDataPart(data={
            "type": "custom_data",
            "value": 42,
            "metadata": {"source": "test"}
        })
    ])
    context = ResponseContext(
        task_id="test-task-456",
        session_id="test-session",
        user_id="test@example.com",
        platform_context={}
    )

    # Act
    await adapter.handle_update(data_update, context)

    # Assert
    assert len(adapter.data_parts) == 1, "Data part not dispatched to handle_data_part()"
    data_part, received_context = adapter.data_parts[0]
    assert data_part.data["type"] == "custom_data"
    assert data_part.data["value"] == 42
    assert received_context.task_id == "test-task-456"


@pytest.mark.asyncio
async def test_file_part_dispatches_to_handle_file(dispatching_gateway_component):
    """Test that file parts dispatch to handle_file()"""
    from solace_agent_mesh.gateway.adapter.types import ResponseContext, SamUpdate

    # Arrange
    adapter = dispatching_gateway_component.adapter
    file_update = SamUpdate(parts=[
        SamFilePart(
            name="test.txt",
            content_bytes=b"Test file content",
            mime_type="text/plain"
        )
    ])
    context = ResponseContext(
        task_id="test-task-789",
        session_id="test-session",
        user_id="test@example.com",
        platform_context={}
    )

    # Act
    await adapter.handle_update(file_update, context)

    # Assert
    assert len(adapter.files) == 1, "File part not dispatched to handle_file()"
    file_part, received_context = adapter.files[0]
    assert file_part.name == "test.txt"
    assert file_part.content_bytes == b"Test file content"
    assert file_part.mime_type == "text/plain"
    assert received_context.task_id == "test-task-789"


@pytest.mark.asyncio
async def test_mixed_update_dispatches_to_all_handlers(dispatching_gateway_component):
    """Test that an update with multiple part types dispatches correctly"""
    from solace_agent_mesh.gateway.adapter.types import ResponseContext, SamUpdate

    # Arrange
    adapter = dispatching_gateway_component.adapter
    mixed_update = SamUpdate(parts=[
        SamTextPart(text="Here is your file:"),
        SamFilePart(name="result.json", content_bytes=b'{"result": "success"}', mime_type="application/json"),
        SamDataPart(data={"type": "metadata", "count": 1}),
        SamDataPart(data={"type": "agent_progress_update", "status_text": "Done!"}),
    ])
    context = ResponseContext(
        task_id="mixed-task-001",
        session_id="test-session",
        user_id="test@example.com",
        platform_context={}
    )

    # Act
    await adapter.handle_update(mixed_update, context)

    # Assert - verify each part was dispatched to correct handler
    assert len(adapter.text_chunks) == 1, "Text part not dispatched"
    assert adapter.text_chunks[0][0] == "Here is your file:"

    assert len(adapter.files) == 1, "File part not dispatched"
    assert adapter.files[0][0].name == "result.json"

    assert len(adapter.data_parts) == 1, "Generic data part not dispatched"
    assert adapter.data_parts[0][0].data["type"] == "metadata"

    assert len(adapter.status_updates) == 1, "Status update not dispatched"
    assert adapter.status_updates[0][0] == "Done!"


@pytest.mark.asyncio
async def test_empty_update_handled_gracefully(dispatching_gateway_component):
    """Test that empty updates don't cause errors"""
    from solace_agent_mesh.gateway.adapter.types import ResponseContext, SamUpdate

    # Arrange
    adapter = dispatching_gateway_component.adapter
    empty_update = SamUpdate(parts=[])
    context = ResponseContext(
        task_id="empty-task-001",
        session_id="test-session",
        user_id="test@example.com",
        platform_context={}
    )

    # Act - should not raise any errors
    await adapter.handle_update(empty_update, context)

    # Assert - no handlers should have been called
    assert len(adapter.text_chunks) == 0
    assert len(adapter.files) == 0
    assert len(adapter.data_parts) == 0
    assert len(adapter.status_updates) == 0


@pytest.mark.asyncio
async def test_dispatching_maintains_context(dispatching_gateway_component, test_llm_server):
    """Test that ResponseContext is properly passed to all handlers"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Context test"))
    adapter = dispatching_gateway_component.adapter
    test_user = "context-test@example.com"
    external_input = {
        "text": "Test context",
        "user_id": test_user
    }

    # Act
    task_id = await dispatching_gateway_component.handle_external_input(external_input)

    # Wait for response
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if len(adapter.text_chunks) > 0:
            break
        await asyncio.sleep(0.1)

    # Assert - verify context was passed correctly
    assert len(adapter.text_chunks) > 0
    _, context = adapter.text_chunks[0]
    assert context.task_id == task_id
    assert context.user_id == test_user
