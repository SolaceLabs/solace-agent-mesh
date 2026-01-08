"""
Programmatic integration tests for task cancellation flows.
"""

import pytest
import asyncio
from typing import List, Dict, Any

from sam_test_infrastructure.llm_server.server import (
    TestLLMServer,
    ChatCompletionResponse,
    Message,
    Choice,
    ToolCall,
    ToolCallFunction,
    Usage,
)
from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from sam_test_infrastructure.a2a_validator.validator import (
    A2AMessageValidator,
)
from solace_agent_mesh.agent.sac.app import SamAgentApp
from a2a.types import Task, TaskState, TaskStatusUpdateEvent
from solace_agent_mesh.common import a2a

from .test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    find_first_event_of_type,
)

import uuid
import json
import base64

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
    pytest.mark.common,
    pytest.mark.task_cancellation
]


async def test_programmatic_task_cancellation(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
):
    """
    Test a scenario where a task is cancelled while a tool is running.
    """
    scenario_id = "programmatic_task_cancellation_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    llm_response_tool_request_dict = ChatCompletionResponse(
        id="chatcmpl-prog-toolreq-cancel",
        model="test-llm-model-tool-req-cancel",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    tool_calls=[
                        ToolCall(
                            id="call_prog_delay_123",
                            type="function",
                            function=ToolCallFunction(
                                name="time_delay",
                                arguments='{"seconds": 10}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    ).model_dump(exclude_none=True)

    prime_llm_server(test_llm_server, [llm_response_tool_request_dict])

    target_agent = "TestAgent"
    user_identity = "programmatic_user_cancel@example.com"
    input_texts = ["Please wait for 10 seconds."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    await asyncio.sleep(1)
    await test_gateway_app_instance.cancel_task(
        agent_name=target_agent, task_id=task_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=10.0
    )
    final_event = find_first_event_of_type(all_events, Task)

    assert (
        final_event is not None
    ), f"Scenario {scenario_id}: Did not receive the final Task object after cancellation."
    assert isinstance(
        final_event, Task
    ), f"Scenario {scenario_id}: Event after cancellation should be a Task object, but was {type(final_event).__name__}."
    assert (
        a2a.get_task_status(final_event) == TaskState.canceled
    ), f"Scenario {scenario_id}: Task status should be CANCELED, but was {a2a.get_task_status(final_event)}."

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_cancel_during_llm_call(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
):
    """
    Test a scenario where a task is cancelled while the agent is waiting for an LLM response.
    Steps:
    1. Configure the test LLM server to introduce a delay before responding.
    2. Send a request to the agent that will trigger an LLM call.
    3. While the agent is waiting for the LLM, send a CancelTaskRequest.
    4. Verify that the task is immediately cancelled.
    5. Assert that the final task status is CANCELED.
    """
    scenario_id = "programmatic_task_cancellation_llm_002"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    test_llm_server.set_response_delay(5)

    llm_response_dict = ChatCompletionResponse(
        id="chatcmpl-prog-llm-cancel",
        model="test-llm-model-llm-cancel",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="This response should not be received.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    ).model_dump(exclude_none=True)
    prime_llm_server(test_llm_server, [llm_response_dict])

    target_agent = "TestAgent"
    user_identity = "programmatic_user_llm_cancel@example.com"
    input_texts = ["Tell me a story."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    await asyncio.sleep(1)
    await test_gateway_app_instance.cancel_task(
        agent_name=target_agent, task_id=task_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=10.0
    )
    final_event = find_first_event_of_type(all_events, Task)

    assert (
        final_event is not None
    ), f"Scenario {scenario_id}: Did not receive the final Task object after cancellation."
    assert isinstance(
        final_event, Task
    ), f"Scenario {scenario_id}: Event after cancellation should be a Task object, but was {type(final_event).__name__}."
    assert (
        a2a.get_task_status(final_event) == TaskState.canceled
    ), f"Scenario {scenario_id}: Task status should be CANCELED, but was {a2a.get_task_status(final_event)}."

    test_llm_server.set_response_delay(0.01)
    print(f"Scenario {scenario_id}: Completed successfully.")


@pytest.mark.xfail(
    reason="Cancellation signal is sent, but task continues and completes instead of cancelling."
)
async def test_peer_task_cancellation_propagation(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
    peer_agent_a_app_under_test: SamAgentApp,
):
    """
    Tests that cancelling a main task also cancels its delegated peer sub-task.
    This test uses the stateful LLM server protocol to ensure deterministic delegation.
    """
    scenario_id = "peer_cancellation_propagation_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    responses = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_peer_a_123",
                                "type": "function",
                                "function": {
                                    "name": "peer_TestPeerAgentA",
                                    "arguments": '{"task_description": "Please wait for 10 seconds."}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_time_delay_456",
                                "type": "function",
                                "function": {
                                    "name": "time_delay",
                                    "arguments": '{"seconds": 10}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        },
    ]
    responses_json_str = json.dumps(responses)
    responses_b64_str = base64.b64encode(responses_json_str.encode("utf-8")).decode(
        "utf-8"
    )

    main_agent_name = "TestAgent"
    user_identity = "programmatic_user_peer_cancel@example.com"
    input_texts = [
        f"[test_case_id={scenario_id}] [responses_json={responses_b64_str}] Delegate a 10 second wait."
    ]

    test_llm_server.clear_stateful_cache_for_id(scenario_id)

    test_input_data = create_gateway_input_data(
        target_agent=main_agent_name,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )
    main_task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    await asyncio.sleep(2)  # Wait for delegation to occur

    test_gateway_app_instance.clear_all_captured_cancel_calls()
    await test_gateway_app_instance.cancel_task(
        agent_name=main_agent_name, task_id=main_task_id
    )

    assert test_gateway_app_instance.was_cancel_called_for_task(
        main_task_id
    ), f"Scenario {scenario_id}: cancel_task was not called for the main task."

    all_events = await get_all_task_events(
        test_gateway_app_instance, main_task_id, overall_timeout=15.0
    )
    final_main_event = find_first_event_of_type(all_events, Task)

    assert (
        final_main_event is not None
    ), f"Scenario {scenario_id}: Did not receive the final Task object for the main task."
    assert (
        a2a.get_task_status(final_main_event) == TaskState.canceled
    ), f"Scenario {scenario_id}: Main task status should be CANCELED, but was {a2a.get_task_status(final_main_event)}."

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_cancel_a_completed_task(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
):
    """
    Test that sending a cancellation request for a completed task is handled gracefully.
    Steps:
    1. Prime the LLM server for a quick, successful response.
    2. Send a request to the agent and wait for it to complete.
    3. Verify the task status is COMPLETED.
    4. Send a CancelTaskRequest for the now-completed task.
    5. Assert that the system does not error and the final task status remains COMPLETED.
    """
    scenario_id = "programmatic_cancel_completed_task_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    llm_response_dict = ChatCompletionResponse(
        id="chatcmpl-prog-completed-cancel",
        model="test-llm-model-completed-cancel",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="This is a quick response.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    ).model_dump(exclude_none=True)
    prime_llm_server(test_llm_server, [llm_response_dict])

    target_agent = "TestAgent"
    user_identity = "programmatic_user_completed_cancel@example.com"
    input_texts = ["Please give me a quick response."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=10.0
    )
    completed_task = find_first_event_of_type(all_events, Task)

    assert (
        completed_task is not None
    ), f"Scenario {scenario_id}: Task did not complete within the timeout."
    assert (
        a2a.get_task_status(completed_task) == TaskState.completed
    ), f"Scenario {scenario_id}: Task status should be COMPLETED, but was {a2a.get_task_status(completed_task)}."

    await test_gateway_app_instance.cancel_task(
        agent_name=target_agent, task_id=task_id
    )
    await asyncio.sleep(
        2
    )  # Give a moment for any potential (incorrect) status change to process

    final_task_event = None
    events = await test_gateway_app_instance.get_all_captured_outputs(
        task_id, drain_timeout=1.0
    )
    task_events = [e for e in events if isinstance(e, Task)]
    if task_events:
        final_task_event = task_events[-1]
    else:
        final_task_event = completed_task

    assert (
        final_task_event is not None
    ), f"Scenario {scenario_id}: Could not determine final task state."
    assert (
        a2a.get_task_status(final_task_event) == TaskState.completed
    ), f"Scenario {scenario_id}: Final task status should remain COMPLETED, but was {a2a.get_task_status(final_task_event)}."

    print(f"Scenario {scenario_id}: Completed successfully.")


async def test_cancel_a_non_existent_task(
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
):
    """
    Test that sending a cancellation request for a non-existent task is handled gracefully.
    Steps:
    1. Generate a fake, non-existent task ID.
    2. Send a CancelTaskRequest using this fake task ID.
    3. Verify that the gateway and agent handle this without any errors.
    4. Check that no unexpected messages or events are generated.
    """
    scenario_id = "programmatic_cancel_non_existent_task_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    fake_task_id = str(uuid.uuid4())
    target_agent = "TestAgent"

    await test_gateway_app_instance.cancel_task(
        agent_name=target_agent, task_id=fake_task_id
    )

    await asyncio.sleep(2)

    events = await test_gateway_app_instance.get_all_captured_outputs(
        fake_task_id, drain_timeout=1.0
    )
    assert (
        len(events) == 0
    ), f"Scenario {scenario_id}: Expected no events for a non-existent task cancellation, but got {len(events)}."

    print(f"Scenario {scenario_id}: Completed successfully.")


@pytest.mark.xfail(
    reason="Race condition: task completes before cancellation is processed in streaming scenarios."
)
async def test_cancel_during_streaming_output(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,
):
    """
    Test that a task is cancelled correctly while it is streaming back a response.
    Steps:
    1. Prime the LLM server to return a long, chunked/streaming response.
    2. Send a streaming request to the agent.
    3. Once the first few status updates (text chunks) have been received, send a CancelTaskRequest.
    4. Verify that the stream of status updates stops immediately.
    5. Assert that the final task object has a status of CANCELED.
    """
    scenario_id = "programmatic_cancel_streaming_output_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    long_content = (
        "This is a very long response designed to be streamed in multiple chunks. " * 10
    )
    llm_response_dict = ChatCompletionResponse(
        id="chatcmpl-prog-streaming-cancel",
        model="test-llm-model-streaming-cancel",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content=long_content,
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=500, total_tokens=510),
    ).model_dump(exclude_none=True)
    prime_llm_server(test_llm_server, [llm_response_dict])

    target_agent = "TestAgent"
    user_identity = "programmatic_user_streaming_cancel@example.com"
    input_texts = ["Tell me a long story, streaming."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
        external_context_override={"stream": True},
    )
    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    received_chunks_count = 0
    while received_chunks_count < 2:
        events = await test_gateway_app_instance.get_all_captured_outputs(
            task_id, drain_timeout=5.0
        )
        received_chunks_count += len(events)
        if received_chunks_count >= 2:
            break
        await asyncio.sleep(0.1)

    assert (
        received_chunks_count > 0
    ), f"Scenario {scenario_id}: Did not receive any streaming chunks."

    await test_gateway_app_instance.cancel_task(
        agent_name=target_agent, task_id=task_id
    )

    all_events_after_cancel = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=10.0
    )
    final_event = find_first_event_of_type(all_events_after_cancel, Task)

    assert (
        final_event is not None
    ), f"Scenario {scenario_id}: Did not receive the final Task object after cancellation."
    assert (
        a2a.get_task_status(final_event) == TaskState.canceled
    ), f"Scenario {scenario_id}: Task status should be CANCELED, but was {a2a.get_task_status(final_event)}."

    all_received_content = "".join(
        a2a.get_text_from_message(a2a.get_message_from_status_update(e))
        for e in all_events_after_cancel
        if isinstance(e, TaskStatusUpdateEvent)
        and a2a.get_message_from_status_update(e)
    )
    assert (
        long_content not in all_received_content
    ), f"Scenario {scenario_id}: The full content was received despite cancellation."

    print(f"Scenario {scenario_id}: Completed successfully.")
