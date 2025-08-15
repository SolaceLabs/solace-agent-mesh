import pytest
from pytest_httpx import HTTPXMock
import uuid
import json

from solace_agent_mesh.common.client.card_resolver import A2ACardResolver
from solace_agent_mesh.common.client.client import A2AClient
from a2a.types import (
    AgentCard,
    AgentSkill,
    CancelTaskResponse,
    GetTaskPushNotificationConfigResponse,
    GetTaskResponse,
    SendMessageResponse,
    SendStreamingMessageResponse,
    SetTaskPushNotificationConfigResponse,
    Task,
    TaskState,
    TextPart,
    SendMessageSuccessResponse,
    SendStreamingMessageSuccessResponse,
    TaskStatusUpdateEvent,
    GetTaskSuccessResponse,
    CancelTaskSuccessResponse,
    SetTaskPushNotificationConfigSuccessResponse,
    GetTaskPushNotificationConfigSuccessResponse,
)

pytestmark = [pytest.mark.all, pytest.mark.asyncio]


def test_mock_agent_skills(mock_agent_skills: AgentSkill):
    assert isinstance(mock_agent_skills, AgentSkill)
    assert mock_agent_skills.id == "skill-1"
    assert mock_agent_skills.name == "Skill 1"
    assert mock_agent_skills.description == "Description for Skill 1"
    assert "tag1" in mock_agent_skills.tags
    assert "tag2" in mock_agent_skills.tags
    assert "Example 1" in mock_agent_skills.examples
    assert "text/plain" in mock_agent_skills.input_modes
    assert "text/plain" in mock_agent_skills.output_modes


def test_card_resolver(
    mock_agent_card: AgentCard,
    mock_card_resolver: A2ACardResolver,
    httpx_mock: HTTPXMock,
):
    assert mock_card_resolver.base_url == "http://test.com"
    assert mock_card_resolver.agent_card_path == "test_path/agent.json"
    assert isinstance(mock_card_resolver, A2ACardResolver)

    httpx_mock.add_response(
        method="GET",
        url="http://test.com/test_path/agent.json",
        json=mock_agent_card.model_dump(by_alias=True, exclude_none=True),
        status_code=200,
    )

    agent_card = mock_card_resolver.get_agent_card()
    assert isinstance(
        agent_card, AgentCard
    ), f"returned agent card is not an instance of AgentCard: {type(agent_card)}"
    assert agent_card.name == mock_agent_card.name
    assert agent_card.description == mock_agent_card.description
    assert agent_card.url == mock_agent_card.url
    assert agent_card.version == mock_agent_card.version
    assert agent_card.capabilities == mock_agent_card.capabilities
    assert agent_card.skills == mock_agent_card.skills


@pytest.mark.asyncio
async def test_a2a_client_send_task_response(
    mock_a2a_client: A2AClient, mock_task_response: dict, httpx_mock: HTTPXMock
):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    # mock post request send task
    httpx_mock.add_response(
        status_code=200,
        json={"jsonrpc": "2.0", "id": "task-123", "result": mock_task_response},
        method="POST",
        url="http://test.com/test_path/agent.json",
    )

    payload = {
        "id": "task-123",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello, World!"}],
                "contextId": "session-456",
                "messageId": "msg-user-1",
                "kind": "message",
            }
        },
    }

    response = await mock_a2a_client.send_task(payload)

    assert isinstance(response.root, SendMessageSuccessResponse)
    assert response.root.result is not None
    assert isinstance(response.root.result, Task)
    assert response.root.result.id == "task-123"
    assert response.root.result.context_id == "session-456"
    assert response.root.result.status.state == TaskState.completed


@pytest.mark.asyncio
async def test_a2a_client_send_task_streaming_response(
    mock_a2a_client: A2AClient, mock_sse_task_response: dict, httpx_mock: HTTPXMock
):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    # Mock the SSE post response
    sse_data = {
        "jsonrpc": "2.0",
        "id": "task-123",
        "result": mock_sse_task_response,
    }
    sse_content = f"data: {json.dumps(sse_data)}\n\n"

    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        content=sse_content,
        headers={"Content-Type": "text/event-stream"},
    )

    payload = {
        "id": "task-123",
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": "Hello, World!"}],
                "contextId": "session-456",
                "messageId": "msg-user-stream-1",
                "kind": "message",
            }
        },
    }

    async for response in mock_a2a_client.send_task_streaming(payload=payload):
        assert isinstance(response.root, SendStreamingMessageSuccessResponse)
        assert isinstance(response.root.result, TaskStatusUpdateEvent)
        assert response.root.result.task_id == "task-123"
        assert response.root.result.context_id == "session-456"
        assert response.root.result.status.state == TaskState.working


@pytest.mark.asyncio
async def test_a2a_client_get_task_response(
    mock_a2a_client: A2AClient, mock_task_response: dict, httpx_mock: HTTPXMock
):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {"id": "task-123", "historyLength": 10}

    # Mock the GET task response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"jsonrpc": "2.0", "id": "req-get-1", "result": mock_task_response},
        status_code=200,
    )
    response = await mock_a2a_client.get_task(payload=payload)

    assert isinstance(response.root, GetTaskSuccessResponse)
    assert response.root.result is not None
    assert isinstance(response.root.result, Task)
    assert response.root.result.id == "task-123"
    assert response.root.result.context_id == "session-456"
    assert response.root.result.status.state == TaskState.completed


@pytest.mark.asyncio
async def test_a2a_client_cancel_task_response(
    mock_a2a_client: A2AClient, mock_task_response_cancel: dict, httpx_mock: HTTPXMock
):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {"id": "task-123"}

    # Mock the cancel task response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"jsonrpc": "2.0", "id": "req-cancel-1", "result": mock_task_response_cancel},
        status_code=200,
    )

    response = await mock_a2a_client.cancel_task(payload=payload)

    assert isinstance(response.root, CancelTaskSuccessResponse)
    assert response.root.result is not None
    assert isinstance(response.root.result, Task)
    assert response.root.result.id == "task-123"
    assert response.root.result.context_id == "session-456"
    assert response.root.result.status.state == TaskState.canceled
    assert response.root.result.status.message.parts[0].text == "Task canceled successfully"
    assert response.root.result.status.message.role == "agent"


@pytest.mark.asyncio
async def test_a2a_client_set_task_callback_response(
    mock_a2a_client: A2AClient, mock_task_callback_response: dict, httpx_mock: HTTPXMock
):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {
        "taskId": "task-123",
        "pushNotificationConfig": {
            "id": "config-1",
            "url": "http://test.com/notify",
            "token": "test-token",
        },
    }

    # Mock the set task callback response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"jsonrpc": "2.0", "id": "req-set-cb-1", "result": mock_task_callback_response},
        status_code=200,
    )

    response = await mock_a2a_client.set_task_callback(payload=payload)

    assert isinstance(response.root, SetTaskPushNotificationConfigSuccessResponse)
    assert response.root.result is not None
    assert response.root.result.task_id == "task-123"
    assert response.root.result.push_notification_config.url == "http://test.com/notify"
    assert response.root.result.push_notification_config.token == "test-token"


@pytest.mark.asyncio
async def test_a2a_client_get_task_callback_response(
    mock_a2a_client: A2AClient, mock_task_callback_response: dict, httpx_mock: HTTPXMock
):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {
        "id": "task-123",
    }

    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"jsonrpc": "2.0", "id": "req-get-cb-1", "result": mock_task_callback_response},
        status_code=200,
    )
    response = await mock_a2a_client.get_task_callback(payload=payload)

    assert isinstance(response.root, GetTaskPushNotificationConfigSuccessResponse)
    assert response.root.result is not None
    assert response.root.result.task_id == "task-123"
    assert response.root.result.push_notification_config.url == "http://test.com/notify"
    assert response.root.result.push_notification_config.token == "test-token"
