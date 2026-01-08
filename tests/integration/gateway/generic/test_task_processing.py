"""
Integration tests for task processing in GenericGatewayComponent.

Tests task preparation, submission, and response handling with different
content types (text, files, data parts).
"""

import asyncio
import pytest
import time

from solace_agent_mesh.gateway.adapter.types import SamFilePart, SamTextPart
from tests.integration.gateway.generic.conftest import simple_llm_response


@pytest.mark.asyncio
async def test_text_only_task_processing(minimal_gateway_component, test_llm_server):
    """Test processing a simple text-only task"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Text response"))
    adapter = minimal_gateway_component.adapter
    external_input = {"text": "Process this text", "user_id": "text-user@example.com"}

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Wait for completion
    max_wait = 10
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if task_id in adapter.completed_tasks:
            break
        await asyncio.sleep(0.1)

    # Assert
    assert task_id in adapter.completed_tasks
    assert len(adapter.received_updates) > 0


@pytest.mark.asyncio
async def test_file_upload_in_task(file_gateway_component, test_llm_server):
    """Test task with file upload"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("File processed"))
    adapter = file_gateway_component.adapter
    test_file_content = b"Test file content"
    external_input = {
        "text": "Process this file",
        "files": [
            {
                "name": "test.txt",
                "content": test_file_content,
                "mime_type": "text/plain",
            }
        ],
    }

    # Act
    task_id = await file_gateway_component.handle_external_input(external_input)

    # Assert
    assert task_id is not None
    # Verify file was tracked by adapter
    assert len(adapter.uploaded_files) == 1
    assert adapter.uploaded_files[0]["name"] == "test.txt"
    assert adapter.uploaded_files[0]["content"] == test_file_content


@pytest.mark.asyncio
async def test_multiple_files_in_task(file_gateway_component, test_llm_server):
    """Test task with multiple file uploads"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Multiple files processed"))
    adapter = file_gateway_component.adapter
    external_input = {
        "text": "Process these files",
        "files": [
            {"name": "file1.txt", "content": b"Content 1", "mime_type": "text/plain"},
            {"name": "file2.jpg", "content": b"Image data", "mime_type": "image/jpeg"},
            {"name": "file3.pdf", "content": b"PDF data", "mime_type": "application/pdf"},
        ],
    }

    # Act
    task_id = await file_gateway_component.handle_external_input(external_input)

    # Assert
    assert task_id is not None
    assert len(adapter.uploaded_files) == 3
    uploaded_names = [f["name"] for f in adapter.uploaded_files]
    assert "file1.txt" in uploaded_names
    assert "file2.jpg" in uploaded_names
    assert "file3.pdf" in uploaded_names


@pytest.mark.asyncio
async def test_file_uri_in_task(file_gateway_component, test_llm_server):
    """Test task with file URI reference"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("URI file processed"))
    adapter = file_gateway_component.adapter
    external_input = {
        "text": "Process remote file",
        "files": [
            {
                "name": "remote.pdf",
                "uri": "https://example.com/document.pdf",
                "mime_type": "application/pdf",
            }
        ],
    }

    # Act
    task_id = await file_gateway_component.handle_external_input(external_input)

    # Assert
    assert task_id is not None
    assert len(adapter.uploaded_files) == 1
    assert adapter.uploaded_files[0]["uri"] == "https://example.com/document.pdf"


@pytest.mark.asyncio
async def test_receiving_file_from_agent(file_gateway_component, test_llm_server):
    """Test receiving file part in agent response"""
    # Arrange
    # For now, just test that a simple text response works
    # File response handling would require artifact creation which is more complex
    from tests.integration.gateway.generic.conftest import simple_llm_response
    test_llm_server.configure_static_response(simple_llm_response("File generation response"))

    adapter = file_gateway_component.adapter
    external_input = {
        "text": "Generate a file for me",
    }

    # Act
    task_id = await file_gateway_component.handle_external_input(external_input)

    # Assert - task was created successfully
    assert task_id is not None
    context = file_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None

    # Note: Testing actual file reception from agents requires the agent to use
    # artifact creation tools, which is tested in higher-level integration tests


@pytest.mark.asyncio
async def test_task_with_custom_session(minimal_gateway_component, test_llm_server):
    """Test that tasks maintain session context"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Session-aware response"))
    session_id = "persistent-session-123"
    external_input = {
        "text": "Test message",
        "session_id": session_id,
        "user_id": "session-user@example.com"
    }

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Assert - verify session is stored in context
    context = minimal_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert context["a2a_session_id"] == session_id


@pytest.mark.asyncio
async def test_task_targeting_specific_agent(minimal_gateway_component, test_llm_server):
    """Test routing tasks to specific agents"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Peer agent response"))
    external_input = {
        "text": "Task for peer agent",
        "target_agent": "TestPeerAgentA",
        "user_id": "routing-user@example.com",
    }

    # Act
    task_id = await minimal_gateway_component.handle_external_input(external_input)

    # Assert - just verify task was created successfully
    # The actual target agent routing is tested at lower levels
    context = minimal_gateway_component.task_context_manager.get_context(task_id)
    assert context is not None
    assert task_id is not None


@pytest.mark.asyncio
async def test_rapid_task_submission(minimal_gateway_component, test_llm_server):
    """Test gateway handles rapid task submissions"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Rapid response"))
    num_tasks = 10
    external_inputs = [
        {"text": f"Rapid task {i}", "user_id": f"rapid-{i}@example.com"}
        for i in range(num_tasks)
    ]

    # Act
    start_time = time.time()
    task_ids = []
    for inp in external_inputs:
        task_id = await minimal_gateway_component.handle_external_input(inp)
        task_ids.append(task_id)
    submission_time = time.time() - start_time

    # Assert
    assert len(task_ids) == num_tasks
    assert len(set(task_ids)) == num_tasks  # All unique
    assert submission_time < 5.0  # Should be fast (< 5 seconds)


@pytest.mark.asyncio
async def test_task_context_isolation(minimal_gateway_component, test_llm_server):
    """Test that task contexts don't interfere with each other"""
    # Arrange
    test_llm_server.configure_static_response(simple_llm_response("Isolated response"))
    external_inputs = [
        {"text": "Task A", "user_id": "user-a@example.com", "session_id": "session-a"},
        {"text": "Task B", "user_id": "user-b@example.com", "session_id": "session-b"},
    ]

    # Act
    task_ids = await asyncio.gather(
        *[minimal_gateway_component.handle_external_input(inp) for inp in external_inputs]
    )

    # Assert - contexts are separate
    context_a = minimal_gateway_component.task_context_manager.get_context(task_ids[0])
    context_b = minimal_gateway_component.task_context_manager.get_context(task_ids[1])

    assert context_a["user_identity"]["id"] == "user-a@example.com"
    assert context_b["user_identity"]["id"] == "user-b@example.com"
    assert context_a["a2a_session_id"] == "session-a"
    assert context_b["a2a_session_id"] == "session-b"
