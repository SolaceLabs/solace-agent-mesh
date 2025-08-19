import pytest
from pytest_httpx import HTTPXMock

from solace_agent_mesh.common.client.card_resolver import A2ACardResolver
from solace_agent_mesh.common.client.client import A2AClient
from solace_agent_mesh.common.types import (
    AgentCard,
    AgentSkill,
    CancelTaskResponse,
    GetTaskPushNotificationResponse,
    GetTaskResponse,
    SendTaskResponse,
    SendTaskStreamingResponse,
    SetTaskPushNotificationResponse,
    Task,
    TaskState,
    TextPart,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio
]

def test_mock_agent_skills(mock_agent_skills: AgentSkill):
    assert isinstance(mock_agent_skills, AgentSkill)
    assert mock_agent_skills.id == "skill-1"
    assert mock_agent_skills.name == "Skill 1"
    assert mock_agent_skills.description == "Description for Skill 1"
    assert "tag1" in mock_agent_skills.tags
    assert "tag2" in mock_agent_skills.tags
    assert "Example 1" in mock_agent_skills.examples
    assert "Example 2" in mock_agent_skills.examples
    assert "text/plain" in mock_agent_skills.inputModes
    assert "text/plain" in mock_agent_skills.outputModes

def test_card_resolver(mock_agent_card: AgentCard, mock_card_resolver: A2ACardResolver, httpx_mock: HTTPXMock):
    assert mock_card_resolver.base_url == "http://test.com"
    assert mock_card_resolver.agent_card_path == "test_path/agent.json"
    assert isinstance(mock_card_resolver, A2ACardResolver)

    httpx_mock.add_response(
        method="GET",
        url="http://test.com/test_path/agent.json",
        json=mock_agent_card.model_dump(),
        status_code=200
    )

    agent_card = mock_card_resolver.get_agent_card()
    assert isinstance(agent_card, AgentCard), f"returned agent card is not an instance of AgentCard: {type(agent_card)}"
    assert agent_card.name == mock_agent_card.name
    assert agent_card.display_name == mock_agent_card.display_name
    assert agent_card.description == mock_agent_card.description
    assert agent_card.url == mock_agent_card.url
    assert agent_card.version == mock_agent_card.version
    assert agent_card.capabilities == mock_agent_card.capabilities
    assert agent_card.skills == mock_agent_card.skills
    assert agent_card.peer_agents == mock_agent_card.peer_agents

@pytest.mark.asyncio
async def test_a2a_client_send_task_response(mock_a2a_client: A2AClient, mock_task_response: dict, httpx_mock: HTTPXMock):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    # mock post request send task
    httpx_mock.add_response(
        status_code=200,
        json={"result": mock_task_response},
        method="POST",
        url="http://test.com/test_path/agent.json"
    )

    payload = {
        "id": "task-123",
        "sessionId": "session-456",
        "message": {
            "role": "user",
            "parts": [TextPart(text="Hello, World!")]
        }
    }

    response = await mock_a2a_client.send_task(payload)

    assert isinstance(response, SendTaskResponse)
    assert response.result is not None
    assert isinstance(response.result, Task)
    assert response.result.id == "task-123"
    assert response.result.sessionId == "session-456"
    assert response.result.status.state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_a2a_client_send_task_streaming_response(mock_a2a_client: A2AClient, mock_sse_task_response: dict, httpx_mock: HTTPXMock):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    # Mock the SSE post response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"result": mock_sse_task_response},
        headers={"Content-Type": "text/event-stream"}
    )

    payload = {
        "id": "task-123",
        "sessionId": "session-456",
        "message": {
            "role": "user",
            "parts": [TextPart(text="Hello, World!")]
        }
    }

    async for response in mock_a2a_client.send_task_streaming(payload=payload):
        assert isinstance(response, SendTaskStreamingResponse)
        assert response.id == "task-123"
        assert response.sessionId == "session-456"
        assert response.status.state == TaskState.WORKING

@pytest.mark.asyncio
async def test_a2a_client_get_task_response(mock_a2a_client: A2AClient, mock_task_response: dict, httpx_mock: HTTPXMock):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {
        "id": "task-123",
        "historyLength": 10
    }

    # Mock the GET task response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"result": mock_task_response},
        status_code=200
    )
    response = await mock_a2a_client.get_task(payload=payload)

    assert isinstance(response, GetTaskResponse)
    assert response.result is not None
    assert isinstance(response.result, Task)
    assert response.result.id == "task-123"
    assert response.result.sessionId == "session-456"
    assert response.result.status.state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_a2a_client_cancel_task_response(mock_a2a_client: A2AClient, mock_task_response_cancel: dict, httpx_mock: HTTPXMock):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {
        "id": "task-123",
        "sessionId": "session-456"
    }

    # Mock the cancel task response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"result": mock_task_response_cancel},
        status_code=200
    )

    response = await mock_a2a_client.cancel_task(payload=payload)

    assert isinstance(response, CancelTaskResponse)
    assert response.result is not None
    assert isinstance(response.result, Task)
    assert response.result.id == "task-123"
    assert response.result.sessionId == "session-456"
    assert response.result.status.state == TaskState.CANCELED
    assert response.result.status.message.parts[0].text == "Task canceled successfully"
    assert response.result.status.message.role == "agent"

@pytest.mark.asyncio
async def test_a2a_client_set_task_callback_response(mock_a2a_client: A2AClient, mock_task_callback_response: dict, httpx_mock: HTTPXMock):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {
        "id": "task-123",
        "pushNotificationConfig": {
            "url": "http://test.com/notify",
            "token": "test-token"
        }
    }

    # Mock the set task callback response
    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"result": mock_task_callback_response},
        status_code=200
    )

    response = await mock_a2a_client.set_task_callback(payload=payload)

    assert isinstance(response, SetTaskPushNotificationResponse)
    assert response.result is not None
    assert response.result.id == "task-123"
    assert response.result.pushNotificationConfig.url == "http://test.com/notify"
    assert response.result.pushNotificationConfig.token == "test-token"

@pytest.mark.asyncio
async def test_a2a_client_get_task_callback_response(mock_a2a_client: A2AClient, mock_task_callback_response: dict, httpx_mock: HTTPXMock):
    assert mock_a2a_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_a2a_client, A2AClient)

    payload = {
        "id": "task-123",
    }

    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"result": mock_task_callback_response},
        status_code=200
    )
    response = await mock_a2a_client.get_task_callback(payload=payload)

    assert isinstance(response, GetTaskPushNotificationResponse)
    assert response.result is not None
    assert response.result.id == "task-123"
    assert response.result.pushNotificationConfig.url == "http://test.com/notify"
    assert response.result.pushNotificationConfig.token == "test-token"
