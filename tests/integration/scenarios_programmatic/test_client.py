import pytest
from pytest_httpx import HTTPXMock

from solace_agent_mesh.common.client.card_resolver import A2ACardResolver
from solace_agent_mesh.common.client.client import A2AClient
from solace_agent_mesh.common.types import (
    AgentCard,
    CancelTaskResponse,
    GetTaskPushNotificationResponse,
    GetTaskResponse,
    PushNotificationConfig,
    SendTaskResponse,
    SendTaskStreamingResponse,
    SetTaskPushNotificationResponse,
    Task,
    TaskState,
    TextPart,
)

mock_test_agent_skills = {
        "id": "skill-1",
        "name": "Skill 1",
        "description": "Description for Skill 1",
        "tags": ["tag1", "tag2"],
        "examples": ["Example 1", "Example 2"],
        "inputModes": ["text/plain"],
        "outputModes": ["text/plain"]
    }

mock_agent_card = AgentCard(
    name="test_agent",
    display_name="Test Agent_Display",
    description="Test Agent Description",
    url="http://test.com/test_path/agent.json",
    version="1.0.0",
    capabilities={
        "streaming": True,
        "pushNotifications": False,
        "stateTransitionHistory": True
    },
    skills=[mock_test_agent_skills],
    peer_agents={}
)

mock_task_response = {
    "id": "task-123",
    "sessionId": "session-456",
    "status": {
        "state": "completed",
        "message": {
            "role": "agent",
            "parts": [{"type": "text", "text": "Task completed successfully"}]
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
}

mock_task_response_cancel = {
    "id": "task-123",
    "sessionId": "session-456",
    "status": {
        "state": "canceled",
        "message": {
            "role": "agent",
            "parts": [{"type": "text", "text": "Task canceled successfully"}]
        },
        "timestamp": "2023-01-01T00:00:00Z"
    }
}

mock_sse_task_response = {
    "id": "task-123",
    "sessionId": "session-456",
    "status": {
        "state": "working",
        "message": {
            "role": "agent",
            "parts": [{"type": "text", "text": "Processing..."}]
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
}

mock_task_callback_response =  {
    "id": "task-123",
    "pushNotificationConfig": PushNotificationConfig(
        url="http://test.com/notify",
        token= "test-token"
    ).model_dump()
}

mock_client = A2AClient(agent_card=mock_agent_card)
resolver = A2ACardResolver("http://test.com", agent_card_path="/test_path/agent.json")

def test_card_resolver(httpx_mock: HTTPXMock):
    assert resolver.base_url == "http://test.com"
    assert resolver.agent_card_path == "test_path/agent.json"
    assert isinstance(resolver, A2ACardResolver)

    httpx_mock.add_response(
        method="GET",
        url="http://test.com/test_path/agent.json",
        json=mock_agent_card.model_dump(),
        status_code=200
    )

    agent_card = resolver.get_agent_card()
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
async def test_a2a_client_send_task_response(httpx_mock: HTTPXMock):
    assert mock_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_client, A2AClient)

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

    response = await mock_client.send_task(payload)

    assert isinstance(response, SendTaskResponse)
    assert response.result is not None
    assert isinstance(response.result, Task)
    assert response.result.id == "task-123"
    assert response.result.sessionId == "session-456"
    assert response.result.status.state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_a2a_client_send_task_streaming_response(httpx_mock: HTTPXMock):
    assert mock_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_client, A2AClient)

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

    async for response in mock_client.send_task_streaming(payload=payload):
        assert isinstance(response, SendTaskStreamingResponse)
        assert response.id == "task-123"
        assert response.sessionId == "session-456"
        assert response.status.state == TaskState.WORKING

@pytest.mark.asyncio
async def test_a2a_client_get_task_response(httpx_mock: HTTPXMock):
    assert mock_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_client, A2AClient)

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
    response = await mock_client.get_task(payload=payload)

    assert isinstance(response, GetTaskResponse)
    assert response.result is not None
    assert isinstance(response.result, Task)
    assert response.result.id == "task-123"
    assert response.result.sessionId == "session-456"
    assert response.result.status.state == TaskState.COMPLETED

@pytest.mark.asyncio
async def test_a2a_client_cancel_task_response(httpx_mock: HTTPXMock):
    assert mock_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_client, A2AClient)

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

    response = await mock_client.cancel_task(payload=payload)

    assert isinstance(response, CancelTaskResponse)
    assert response.result is not None
    assert isinstance(response.result, Task)
    assert response.result.id == "task-123"
    assert response.result.sessionId == "session-456"
    assert response.result.status.state == TaskState.CANCELED
    assert response.result.status.message.parts[0].text == "Task canceled successfully"
    assert response.result.status.message.role == "agent"

@pytest.mark.asyncio
async def test_a2a_client_set_task_callback_response(httpx_mock: HTTPXMock):
    assert mock_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_client, A2AClient)

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

    response = await mock_client.set_task_callback(payload=payload)

    assert isinstance(response, SetTaskPushNotificationResponse)
    assert response.result is not None
    assert response.result.id == "task-123"
    assert response.result.pushNotificationConfig.url == "http://test.com/notify"
    assert response.result.pushNotificationConfig.token == "test-token"

@pytest.mark.asyncio
async def test_a2a_client_get_task_callback_response(httpx_mock: HTTPXMock):
    assert mock_client.url == "http://test.com/test_path/agent.json"
    assert isinstance(mock_client, A2AClient)

    payload = {
        "id": "task-123",
    }

    httpx_mock.add_response(
        method="POST",
        url="http://test.com/test_path/agent.json",
        json={"result": mock_task_callback_response},
        status_code=200
    )
    response = await mock_client.get_task_callback(payload=payload)

    assert isinstance(response, GetTaskPushNotificationResponse)
    assert response.result is not None
    assert response.result.id == "task-123"
    assert response.result.pushNotificationConfig.url == "http://test.com/notify"
    assert response.result.pushNotificationConfig.token == "test-token"
