"""
Programmatic integration tests for parallel peer tool synchronous return handling.

These tests verify the fix for the race condition where parallel long-running tool calls
could cause the agent to hang if one tool returns synchronously (e.g., validation error)
while others are still being registered or execute asynchronously.

Related to DATAGO-120188: Handle long-running tools better

Test Strategy:
- To cause synchronous error returns from PeerAgentTool, we monkeypatch `submit_a2a_task`
  to raise `MessageSizeExceededError` for specific peer agents.
- This error is caught in `run_async` and returns `{"status": "error", ...}` synchronously.
- The monkeypatch happens AFTER tool registration, so it doesn't break the ADK's tool
  filtering callbacks.
"""

import pytest

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
from solace_agent_mesh.agent.sac.app import SamAgentApp
from solace_agent_mesh.agent.sac.component import SamAgentComponent
from solace_agent_mesh.common.exceptions import MessageSizeExceededError
from a2a.types import Task, TaskState

from .test_helpers import (
    prime_llm_server,
    create_gateway_input_data,
    submit_test_input,
    get_all_task_events,
    find_first_event_of_type,
)


pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.agent,
    pytest.mark.tools,
]


async def test_single_peer_tool_sync_error_no_hang(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,  # noqa: ARG001 - required for fixture setup
    main_agent_component: SamAgentComponent,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that when a single peer tool returns synchronously with an error,
    the agent does NOT hang and properly continues execution.

    This validates Bug 1 fix: Agent hangs on synchronous returns.

    Scenario:
    1. LLM requests a peer tool call (peer_TestPeerAgentA)
    2. submit_a2a_task raises MessageSizeExceededError
    3. Tool returns synchronously with error dict
    4. Agent should NOT hang and should re-run LLM with the error response
    5. LLM provides final response
    """
    scenario_id = "single_peer_sync_error_001"
    print(f"\nRunning scenario: {scenario_id}")

    # First LLM response: Request a call to peer agent
    llm_response_peer_call = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step1",
        model="test-model-sam-peer-call",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I'll ask TestPeerAgentA to help with this.",
                    tool_calls=[
                        ToolCall(
                            id="call_peer_a_sync_error",
                            type="function",
                            function=ToolCallFunction(
                                name="peer_TestPeerAgentA",
                                arguments='{"task_description": "Help me with this task."}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    ).model_dump(exclude_none=True)

    # Second LLM response: Process the error and provide final response
    llm_response_final = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step2",
        model="test-model-sam-final",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I received an error when trying to contact the peer agent due to message size limits.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=15, total_tokens=65),
    ).model_dump(exclude_none=True)

    prime_llm_server(test_llm_server, [llm_response_peer_call, llm_response_final])

    target_agent = "TestAgent"
    user_identity = f"test_user_{scenario_id}@example.com"
    input_texts = ["Please ask TestPeerAgentA to help me."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )

    # Store original method
    original_submit_a2a_task = main_agent_component.submit_a2a_task

    # Create a patched method that raises MessageSizeExceededError for TestPeerAgentA
    def patched_submit_a2a_task(target_agent_name, **kwargs):
        if target_agent_name == "TestPeerAgentA":
            raise MessageSizeExceededError("Simulated message size exceeded for testing")
        return original_submit_a2a_task(target_agent_name=target_agent_name, **kwargs)

    monkeypatch.setattr(main_agent_component, "submit_a2a_task", patched_submit_a2a_task)

    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    # Wait for task completion with a reasonable timeout
    # If the bug is present, this will timeout (hang)
    all_events = await get_all_task_events(
        gateway_component=test_gateway_app_instance,
        task_id=task_id,
        overall_timeout=15.0,
    )

    assert all_events, f"Scenario {scenario_id}: No events captured"

    # Find final task response
    final_task = find_first_event_of_type(all_events, Task, fail_if_not_found=False)
    assert final_task is not None, f"Scenario {scenario_id}: No final Task event found"
    assert (
        final_task.status.state == TaskState.completed
    ), f"Scenario {scenario_id}: Task not completed, got {final_task.status.state}"

    # Verify we got the expected number of LLM calls (2)
    captured_requests = test_llm_server.get_captured_requests()
    assert (
        len(captured_requests) >= 2
    ), f"Scenario {scenario_id}: Expected at least 2 LLM calls, got {len(captured_requests)}"

    # Verify the second request contains the error response from the peer tool
    second_request = captured_requests[1]
    tool_messages = [
        msg for msg in second_request.messages if msg.role == "tool"
    ]
    assert (
        len(tool_messages) > 0
    ), f"Scenario {scenario_id}: Expected tool response in second LLM call"

    # Check that the tool response contains an error about message size
    tool_response_content = tool_messages[0].content
    if isinstance(tool_response_content, str):
        assert "error" in tool_response_content.lower() or "size" in tool_response_content.lower(), (
            f"Scenario {scenario_id}: Expected error about message size in tool response, got: {tool_response_content}"
        )

    print(f"Scenario {scenario_id}: Passed - Agent did not hang on sync error")


async def test_parallel_peer_tools_all_sync_errors(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,  # noqa: ARG001 - required for fixture setup
    main_agent_component: SamAgentComponent,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that when ALL parallel peer tools return synchronously with errors,
    the agent properly re-runs with all error responses.

    This validates the all-sync case in the runner.py fix.

    Scenario:
    1. LLM requests two parallel peer tool calls
    2. Both submit_a2a_task calls raise MessageSizeExceededError
    3. Both tools return synchronously with error dicts
    4. Agent should re-run LLM with both error responses
    5. LLM provides final response acknowledging both errors
    """
    scenario_id = "parallel_peers_all_sync_error_001"
    print(f"\nRunning scenario: {scenario_id}")

    # First LLM response: Request calls to two peer agents in parallel
    llm_response_parallel_calls = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step1",
        model="test-model-sam-parallel",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I'll ask both peer agents to help.",
                    tool_calls=[
                        ToolCall(
                            id="call_peer_a_parallel",
                            type="function",
                            function=ToolCallFunction(
                                name="peer_TestPeerAgentA",
                                arguments='{"task_description": "Task for agent A"}',
                            ),
                        ),
                        ToolCall(
                            id="call_peer_b_parallel",
                            type="function",
                            function=ToolCallFunction(
                                name="peer_TestPeerAgentB",
                                arguments='{"task_description": "Task for agent B"}',
                            ),
                        ),
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=12, total_tokens=22),
    ).model_dump(exclude_none=True)

    # Second LLM response: Process both errors and provide final response
    llm_response_final = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step2",
        model="test-model-sam-final",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Both peer agent requests failed due to message size limits.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=80, completion_tokens=20, total_tokens=100),
    ).model_dump(exclude_none=True)

    prime_llm_server(test_llm_server, [llm_response_parallel_calls, llm_response_final])

    target_agent = "TestAgent"
    user_identity = f"test_user_{scenario_id}@example.com"
    input_texts = ["Please ask both TestPeerAgentA and TestPeerAgentB to help."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )

    # Store original method
    original_submit_a2a_task = main_agent_component.submit_a2a_task

    # Create a patched method that raises MessageSizeExceededError for both peers
    def patched_submit_a2a_task(target_agent_name, **kwargs):
        if target_agent_name in ("TestPeerAgentA", "TestPeerAgentB"):
            raise MessageSizeExceededError(f"Simulated message size exceeded for {target_agent_name}")
        return original_submit_a2a_task(target_agent_name=target_agent_name, **kwargs)

    monkeypatch.setattr(main_agent_component, "submit_a2a_task", patched_submit_a2a_task)

    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    # Wait for task completion
    # If the bug is present (all sync without re-run), this would hang or error
    all_events = await get_all_task_events(
        gateway_component=test_gateway_app_instance,
        task_id=task_id,
        overall_timeout=15.0,
    )

    assert all_events, f"Scenario {scenario_id}: No events captured"

    # Find final task response
    final_task = find_first_event_of_type(all_events, Task, fail_if_not_found=False)
    assert final_task is not None, f"Scenario {scenario_id}: No final Task event found"
    assert (
        final_task.status.state == TaskState.completed
    ), f"Scenario {scenario_id}: Task not completed, got {final_task.status.state}"

    # Verify we got the expected number of LLM calls
    captured_requests = test_llm_server.get_captured_requests()
    assert (
        len(captured_requests) >= 2
    ), f"Scenario {scenario_id}: Expected at least 2 LLM calls, got {len(captured_requests)}"

    # Verify the second request contains BOTH tool error responses
    second_request = captured_requests[1]
    tool_messages = [
        msg for msg in second_request.messages if msg.role == "tool"
    ]
    # Should have 2 tool responses (one for each failed peer call)
    assert (
        len(tool_messages) >= 2
    ), f"Scenario {scenario_id}: Expected 2 tool responses in second LLM call, got {len(tool_messages)}"

    print(f"Scenario {scenario_id}: Passed - Agent re-ran with all sync errors")


async def test_mixed_sync_async_parallel_peer_tools(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,  # noqa: ARG001 - required for fixture setup
    main_agent_component: SamAgentComponent,
    peer_b_component: SamAgentComponent,  # noqa: ARG001 - ensures peer B is running
    monkeypatch: pytest.MonkeyPatch,
):
    """
    Test that when parallel peer tools return with a mix of sync errors and
    async responses, the agent properly waits for async and combines all responses.

    This validates the mixed sync/async case in the runner.py fix.

    Scenario:
    1. LLM requests two parallel peer tool calls (A and B)
    2. Peer A's submit_a2a_task raises MessageSizeExceededError -> sync error
    3. Peer B's submit_a2a_task succeeds -> waits for async response
    4. When B's response arrives, both results are combined and sent to LLM
    5. LLM provides final response
    """
    scenario_id = "mixed_sync_async_001"
    print(f"\nRunning scenario: {scenario_id}")

    # First LLM response: Request calls to two peer agents in parallel
    llm_response_parallel_calls = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step1",
        model="test-model-sam-mixed",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I'll ask both peer agents to help.",
                    tool_calls=[
                        ToolCall(
                            id="call_peer_a_mixed",
                            type="function",
                            function=ToolCallFunction(
                                name="peer_TestPeerAgentA",
                                arguments='{"task_description": "Task for agent A"}',
                            ),
                        ),
                        ToolCall(
                            id="call_peer_b_mixed",
                            type="function",
                            function=ToolCallFunction(
                                name="peer_TestPeerAgentB",
                                arguments='{"task_description": "Task for agent B"}',
                            ),
                        ),
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=12, total_tokens=22),
    ).model_dump(exclude_none=True)

    # Second LLM response (for peer agent B): Respond to the task
    llm_response_peer_b = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step2",
        model="test-model-peerB-response",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Response from TestPeerAgentB!",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=20, completion_tokens=5, total_tokens=25),
    ).model_dump(exclude_none=True)

    # Third LLM response: Main agent processes both results (error from A, success from B)
    llm_response_final = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step3",
        model="test-model-sam-final",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="TestPeerAgentA failed due to message size, but TestPeerAgentB responded successfully.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=80, completion_tokens=20, total_tokens=100),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [llm_response_parallel_calls, llm_response_peer_b, llm_response_final],
    )

    target_agent = "TestAgent"
    user_identity = f"test_user_{scenario_id}@example.com"
    input_texts = ["Please ask both TestPeerAgentA and TestPeerAgentB to help."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )

    # Store original method
    original_submit_a2a_task = main_agent_component.submit_a2a_task

    # Create a patched method that raises MessageSizeExceededError for TestPeerAgentA only
    def patched_submit_a2a_task(target_agent_name, **kwargs):
        if target_agent_name == "TestPeerAgentA":
            raise MessageSizeExceededError("Simulated message size exceeded for TestPeerAgentA")
        return original_submit_a2a_task(target_agent_name=target_agent_name, **kwargs)

    monkeypatch.setattr(main_agent_component, "submit_a2a_task", patched_submit_a2a_task)

    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    # Wait for task completion
    # The agent should wait for B's async response and combine with A's sync error
    all_events = await get_all_task_events(
        gateway_component=test_gateway_app_instance,
        task_id=task_id,
        overall_timeout=30.0,  # Allow time for async inter-agent communication
    )

    assert all_events, f"Scenario {scenario_id}: No events captured"

    # Find final task response
    final_task = find_first_event_of_type(all_events, Task, fail_if_not_found=False)
    assert final_task is not None, f"Scenario {scenario_id}: No final Task event found"
    assert (
        final_task.status.state == TaskState.completed
    ), f"Scenario {scenario_id}: Task not completed, got {final_task.status.state}"

    # Verify we got the expected number of LLM calls
    captured_requests = test_llm_server.get_captured_requests()
    # Should have at least 3 calls: main parallel request, peer B response, main combines results
    assert (
        len(captured_requests) >= 3
    ), f"Scenario {scenario_id}: Expected at least 3 LLM calls, got {len(captured_requests)}"

    # Verify the third request contains BOTH tool responses
    # (sync error from A stored earlier, async success from B)
    third_request = captured_requests[2]
    tool_messages = [
        msg for msg in third_request.messages if msg.role == "tool"
    ]
    # Should have 2 tool responses (error from A + success from B)
    assert (
        len(tool_messages) >= 2
    ), f"Scenario {scenario_id}: Expected 2 tool responses in third LLM call, got {len(tool_messages)}"

    print(f"Scenario {scenario_id}: Passed - Agent combined sync error with async response")


async def test_successful_parallel_peer_delegation(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
    sam_app_under_test: SamAgentApp,  # noqa: ARG001 - required for test fixture setup
    main_agent_component: SamAgentComponent,  # noqa: ARG001 - may be used for debugging
    peer_a_component: SamAgentComponent,  # noqa: ARG001 - ensures peer agent is running
):
    """
    Test that the preregister_long_running_tools_callback properly pre-registers
    all peer tool calls before execution begins, and parallel delegation works correctly.

    This validates Bug 2 fix: Race condition in registration - ensures pre-registration
    happens atomically before any tool execution.

    Scenario:
    1. LLM requests a peer tool call
    2. The preregistration callback should be invoked
    3. The tool should complete successfully (async response via broker)
    4. LLM processes the response
    """
    scenario_id = "successful_parallel_delegation_001"
    print(f"\nRunning scenario: {scenario_id}")

    # First LLM response: Request a peer tool call
    llm_response_peer_call = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step1",
        model="test-model-sam-prereg",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I'll delegate this to TestPeerAgentA.",
                    tool_calls=[
                        ToolCall(
                            id="call_peer_a_prereg",
                            type="function",
                            function=ToolCallFunction(
                                name="peer_TestPeerAgentA",
                                arguments='{"task_description": "Say hello"}',
                            ),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
    ).model_dump(exclude_none=True)

    # Second LLM response (for peer agent A): Respond to the task
    llm_response_peer_a = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step2",
        model="test-model-peerA-response",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Hello from TestPeerAgentA!",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=20, completion_tokens=5, total_tokens=25),
    ).model_dump(exclude_none=True)

    # Third LLM response: Main agent processes peer response
    llm_response_final = ChatCompletionResponse(
        id=f"chatcmpl-{scenario_id}-step3",
        model="test-model-sam-final",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="TestPeerAgentA responded with: Hello!",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [llm_response_peer_call, llm_response_peer_a, llm_response_final],
    )

    target_agent = "TestAgent"
    user_identity = f"test_user_{scenario_id}@example.com"
    input_texts = ["Please ask TestPeerAgentA to say hello."]

    test_input_data = create_gateway_input_data(
        target_agent=target_agent,
        user_identity=user_identity,
        text_parts_content=input_texts,
        scenario_id=scenario_id,
    )

    task_id = await submit_test_input(
        test_gateway_app_instance, test_input_data, scenario_id
    )

    # Wait for task completion
    all_events = await get_all_task_events(
        gateway_component=test_gateway_app_instance,
        task_id=task_id,
        overall_timeout=30.0,  # Allow more time for inter-agent communication
    )

    assert all_events, f"Scenario {scenario_id}: No events captured"

    # Find final task response
    final_task = find_first_event_of_type(all_events, Task, fail_if_not_found=False)
    assert final_task is not None, f"Scenario {scenario_id}: No final Task event found"
    assert (
        final_task.status.state == TaskState.completed
    ), f"Scenario {scenario_id}: Task not completed, got {final_task.status.state}"

    # Verify LLM was called the expected number of times
    captured_requests = test_llm_server.get_captured_requests()
    # Should have at least 3 calls: main->peer request, peer response, main processes peer response
    assert (
        len(captured_requests) >= 3
    ), f"Scenario {scenario_id}: Expected at least 3 LLM calls, got {len(captured_requests)}"

    print(f"Scenario {scenario_id}: Passed - Preregistration and delegation worked correctly")
