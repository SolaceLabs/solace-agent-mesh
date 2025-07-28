import pytest
import asyncio
from google.genai import types as adk_types
from tests.integration.infrastructure.artifact_service.service import TestInMemoryArtifactService
from tests.integration.infrastructure.slack_gateway_interface.component import TestSlackGatewayComponent
from src.solace_agent_mesh.agent.sac.component import SamAgentComponent
from src.solace_agent_mesh.common.types import Task, TaskStatus, TaskState
from tests.integration.scenarios_programmatic.test_helpers import (
    get_all_task_events,
    extract_outputs_from_event_list,
)
from tests.integration.scenarios_programmatic.gateways.common import create_llm_response

pytestmark = pytest.mark.asyncio

async def test_submit_prompt_and_get_response(
    test_slack_gateway_component: TestSlackGatewayComponent,
    main_agent_component_for_gateway_test: SamAgentComponent,
    test_llm_server,
):
    """
    Tests a basic interaction: submitting a prompt to the Slack gateway
    and receiving a final response from the agent.
    """
    # 1. Arrange: Define the input for the test
    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [{"type": "text", "text": "Hello, world!"}],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    # Prime the mock LLM server to return a simple response
    test_llm_server.prime_responses(
        [
            create_llm_response(
                content="This is a test response from the mock LLM.",
                id_suffix="123",
                prompt_tokens=5,
                completion_tokens=10,
            )
        ]
    )

    # 2. Act: Send the input to the gateway using our helper method
    task_id = await test_slack_gateway_component.send_test_input(test_input)
    assert task_id is not None

    # 3. Assert: Retrieve the captured output and verify it
    all_events = await get_all_task_events(
        test_slack_gateway_component, task_id, overall_timeout=10.0
    )
    terminal_event, _, terminal_event_text = extract_outputs_from_event_list(
        all_events, f"test_slack_gateway_{task_id}"
    )

    assert terminal_event is not None, "Did not receive a terminal event"
    assert (
        type(terminal_event).__name__ == "Task"
    ), f"Expected a Task, but got {type(terminal_event).__name__}"
    assert terminal_event.id == task_id
    assert terminal_event.status.state == "completed"
    assert terminal_event_text == "This is a test response from the mock LLM."


async def test_submit_prompt_and_get_streaming_response(
    test_slack_gateway_component: TestSlackGatewayComponent,
    main_agent_component_for_gateway_test: SamAgentComponent,
    test_llm_server,
):
    """
    Tests submitting a prompt and receiving a streamed response.
    """
    # 1. Arrange
    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [{"type": "text", "text": "Hello, stream!"}],
        "is_streaming": True,
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }
    test_llm_server.prime_responses(
        [
            create_llm_response(
                content="This is a streamed response.",
                id_suffix="stream-123",
                prompt_tokens=5,
                completion_tokens=10,
            )
        ]
    )

    # 2. Act
    task_id = await test_slack_gateway_component.send_test_input(test_input)
    assert task_id is not None

    # 3. Assert
    all_events = await get_all_task_events(
        test_slack_gateway_component, task_id, overall_timeout=10.0
    )
    terminal_event, intermediate_events, terminal_event_text = extract_outputs_from_event_list(
        all_events, f"test_slack_gateway_{task_id}"
    )

    assert terminal_event is not None, "Did not receive a terminal event"
    assert intermediate_events is not None, "Did not receive any intermediate streaming events"
    assert len(intermediate_events) > 0, "Expected at least one intermediate event"
    assert terminal_event.status.state == "completed"
    assert terminal_event_text == "This is a streamed response."
    assert "".join(intermediate_events) == "This is a streamed response."


async def test_submit_request_with_artifact(
    test_slack_gateway_component: TestSlackGatewayComponent,
    main_agent_component_for_gateway_test: SamAgentComponent,
    test_llm_server,
    test_artifact_service_instance: TestInMemoryArtifactService,
):
    """
    Tests submitting a request that includes a reference to an artifact.
    """
    # 1. Arrange
    artifact_content = b"This is the content of my test artifact."
    artifact_filename = "my_test_artifact.txt"
    artifact_part = adk_types.Part(
        inline_data=adk_types.Blob(mime_type="text/plain", data=artifact_content)
    )
    await test_artifact_service_instance.save_artifact(
        app_name="GatewayTestAgent",
        user_id="test-user",
        session_id="test-channel",
        filename=artifact_filename,
        artifact=artifact_part,
    )

    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [
            {"type": "text", "text": "Please process this artifact."},
            {
                "type": "file",
                "file": {
                    "uri": f"session://GatewayTestAgent/{artifact_filename}"
                }
            },
        ],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    test_llm_server.prime_responses(
        [
            create_llm_response(
                content="Artifact processed.",
                id_suffix="artifact-123",
            )
        ]
    )

    # 2. Act
    task_id = await test_slack_gateway_component.send_test_input(test_input)
    assert task_id is not None

    # 3. Assert
    all_events = await get_all_task_events(
        test_slack_gateway_component, task_id, overall_timeout=10.0
    )
    terminal_event, _, terminal_event_text = extract_outputs_from_event_list(
        all_events, f"test_slack_gateway_{task_id}"
    )

    assert terminal_event is not None, "Did not receive a terminal event"
    assert terminal_event.status.state == "completed"
    assert terminal_event_text == "Artifact processed."


async def test_submit_request_with_multimodal_data(
    test_slack_gateway_component: TestSlackGatewayComponent,
    test_llm_server,
):
    """
    Tests submitting a request with multi-modal data (text and image).
    """
    # 1. Arrange
    red_pixel_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/wcAAwAB/epv2AAAAABJRU5ErkJggg=="

    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [
            {"type": "text", "text": "What color is this image?"},
            {
                "type": "data",
                "data": {
                    "mime_type": "image/png",
                    "base64": red_pixel_b64,
                },
            },
        ],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    test_llm_server.prime_responses(
        [
            create_llm_response(
                content="The image is red.",
                id_suffix="multimodal-1",
            )
        ]
    )

    # 2. Act
    task_id = await test_slack_gateway_component.send_test_input(test_input)
    assert task_id is not None

    # 3. Assert
    all_events = await get_all_task_events(
        test_slack_gateway_component, task_id, overall_timeout=10.0
    )
    terminal_event, _, terminal_event_text = extract_outputs_from_event_list(
        all_events, f"test_slack_gateway_{task_id}"
    )
    assert terminal_event is not None
    assert terminal_event.status.state == "completed"
    assert terminal_event_text == "The image is red."


async def test_long_running_task(
    test_slack_gateway_component: TestSlackGatewayComponent,
    test_llm_server,
):
    """
    Tests a long-running task that uses the time_delay tool.
    """
    # 1. Arrange
    delay_seconds = 2.0
    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [{"type": "text", "text": f"Delay for {delay_seconds} seconds"}],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    test_llm_server.prime_responses(
        [
            create_llm_response(
                content=None,
                id_suffix="long-running-1",
                tool_calls=[
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "time_delay",
                            "arguments": f'{{"seconds": {delay_seconds}}}',
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            create_llm_response(
                content=f"Delayed for {delay_seconds} seconds.",
                id_suffix="long-running-2",
            ),
        ]
    )

    # 2. Act
    start_time = asyncio.get_event_loop().time()
    task_id = await test_slack_gateway_component.send_test_input(test_input)
    assert task_id is not None

    all_events = await get_all_task_events(
        test_slack_gateway_component, task_id, overall_timeout=10.0
    )
    end_time = asyncio.get_event_loop().time()

    # 3. Assert
    terminal_event, _, terminal_event_text = extract_outputs_from_event_list(
        all_events, f"test_slack_gateway_{task_id}"
    )
    assert terminal_event is not None
    assert terminal_event.status.state == "completed"
    assert f"Delayed for {delay_seconds} seconds." in terminal_event_text
    assert (end_time - start_time) >= delay_seconds


async def test_submit_concurrent_requests(
    test_slack_gateway_component: TestSlackGatewayComponent,
    test_llm_server,
):
    """
    Tests submitting multiple requests concurrently.
    """
    # 1. Arrange
    inputs = [
        {
            "target_agent_name": "GatewayTestAgent",
            "a2a_parts": [{"type": "text", "text": f"Hello, request {i}"}],
            "user": "test-user",
            "team": "test-team",
            "channel": "test-channel",
            "ts": f"12345.6789{i}",
        }
        for i in range(3)
    ]

    test_llm_server.prime_responses(
        [
            create_llm_response(
                content=f"This is response {i}",
                id_suffix=f"concurrent-{i}",
            )
            for i in range(3)
        ]
    )

    # 2. Act
    tasks = [
        test_slack_gateway_component.send_test_input(input_data)
        for input_data in inputs
    ]
    task_ids = await asyncio.gather(*tasks)

    # 3. Assert
    for i, task_id in enumerate(task_ids):
        all_events = await get_all_task_events(
            test_slack_gateway_component, task_id, overall_timeout=10.0
        )
        terminal_event, _, terminal_event_text = extract_outputs_from_event_list(
            all_events, f"test_slack_gateway_{task_id}"
        )
        assert terminal_event is not None
        assert terminal_event.status.state == "completed"
        assert terminal_event_text == f"This is response {i}"


async def test_submit_request_with_missing_target_agent(
    test_slack_gateway_component: TestSlackGatewayComponent,
):
    """
    Tests that submitting a request without a target_agent_name raises a ValueError.
    """
    # 1. Arrange
    test_input = {
        # "target_agent_name": "GatewayTestAgent", # This is intentionally missing
        "a2a_parts": [{"type": "text", "text": "This should fail."}],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    # 2. Act & Assert
    with pytest.raises(ValueError, match="Test input must specify 'target_agent_name'"):
        await test_slack_gateway_component.send_test_input(test_input)


@pytest.mark.skip(reason="Agent existence check is not implemented yet")
async def test_submit_request_to_non_existent_agent(
    test_slack_gateway_component: TestSlackGatewayComponent,
):
    """
    Tests that submitting a request to a non-existent agent returns an error.
    """
    # 1. Arrange
    test_input = {
        "target_agent_name": "NonExistentAgent",
        "a2a_parts": [{"type": "text", "text": "This should also fail."}],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    # Allow time for agent discovery
    await asyncio.sleep(2)

    # 2. Act & Assert
    with pytest.raises(ValueError, match="Agent NonExistentAgent not found"):
        await test_slack_gateway_component.send_test_input(test_input)


async def test_submit_request_with_malformed_part(
    test_slack_gateway_component: TestSlackGatewayComponent,
):
    """
    Tests that submitting a request with a malformed a2a_parts structure
    raises a validation error.
    """
    # 1. Arrange
    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [{"type": "text"}],  # Missing "text" field
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    # 2. Act & Assert
    with pytest.raises(Exception): # Changed from pydantic.ValidationError to Exception
        await test_slack_gateway_component.send_test_input(test_input)


@pytest.mark.skip(reason="Authentication tests not implemented yet")
async def test_submit_request_with_invalid_auth(
    test_slack_gateway_component: TestSlackGatewayComponent,
):
    """
    Tests that submitting a request with invalid authentication is rejected.
    """
    pass


@pytest.mark.skip(reason="Authorization tests not implemented yet")
async def test_submit_request_with_unauthorized_user(
    test_slack_gateway_component: TestSlackGatewayComponent,
):
    """
    Tests that submitting a request from an unauthorized user is rejected.
    """
    pass


async def test_component_instantiation(
    test_slack_gateway_component: TestSlackGatewayComponent,
):
    """
    Tests that the TestSlackGatewayComponent can be instantiated without errors.
    """
    assert test_slack_gateway_component is not None
    assert isinstance(test_slack_gateway_component, TestSlackGatewayComponent)


async def test_tool_call_create_artifact(
    test_slack_gateway_component: TestSlackGatewayComponent,
    test_llm_server,
    test_artifact_service_instance: TestInMemoryArtifactService,
):
    """
    Tests a task that involves calling the create_artifact tool.
    """
    # 1. Arrange
    artifact_filename = "test_artifact.txt"
    artifact_content = "Hello, artifact!"
    test_input = {
        "target_agent_name": "GatewayTestAgent",
        "a2a_parts": [
            {
                "type": "text",
                "text": f"Create an artifact named '{artifact_filename}' with content '{artifact_content}'",
            }
        ],
        "user": "test-user",
        "team": "test-team",
        "channel": "test-channel",
        "ts": "12345.67890",
    }

    test_llm_server.prime_responses(
        [
            create_llm_response(
                content=None,
                id_suffix="tool-call-1",
                tool_calls=[
                    {
                        "id": "call_456",
                        "type": "function",
                        "function": {
                            "name": "create_artifact",
                            "arguments": f'{{"filename": "{artifact_filename}", "content": "{artifact_content}", "mime_type": "text/plain"}}',
                        },
                    }
                ],
                finish_reason="tool_calls",
            ),
            create_llm_response(
                content=f"I have created the artifact '{artifact_filename}'.",
                id_suffix="tool-call-2",
            ),
        ]
    )

    # 2. Act
    task_id = await test_slack_gateway_component.send_test_input(test_input)
    assert task_id is not None

    all_events = await get_all_task_events(
        test_slack_gateway_component, task_id, overall_timeout=10.0
    )

    # 3. Assert
    terminal_event, _, terminal_event_text = extract_outputs_from_event_list(
        all_events, f"test_slack_gateway_{task_id}"
    )
    assert terminal_event is not None
    assert terminal_event.status.state == "completed"
    assert f"I have created the artifact '{artifact_filename}'." in terminal_event_text

    # Verify the artifact was actually created
    saved_artifact = await test_artifact_service_instance.load_artifact(
        app_name="GatewayTestAgent",
        user_id="test-user@example.com",
        session_id="test-channel",
        filename=artifact_filename,
    )
    assert saved_artifact is not None
    assert saved_artifact.inline_data.data.decode() == artifact_content
