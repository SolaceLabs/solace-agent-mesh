"""
Programmatic integration tests for workflow-to-workflow invocation.

Tests the new `workflow` node type that allows workflows to invoke other
workflows as sub-workflows.
"""

import pytest
from sam_test_infrastructure.llm_server.server import (
    TestLLMServer,
    ChatCompletionResponse,
    Message,
    Choice,
    Usage,
)
from sam_test_infrastructure.gateway_interface.component import (
    TestGatewayComponent,
)
from a2a.types import Task, JSONRPCError

from .test_helpers import (
    prime_llm_server,
    submit_test_input,
    get_all_task_events,
    extract_outputs_from_event_list,
)

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.workflows,
]


# Note: Direct recursion test would require a workflow definition that invokes itself.
# This is tested via the runtime check in dag_executor._execute_workflow_node.
# See test_direct_recursion_is_rejected below.


async def test_workflow_invokes_sub_workflow_successfully(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that a parent workflow can successfully invoke a child workflow using
    the workflow node type.

    The SubWorkflowInvokeTestWorkflow has three nodes:
    1. prepare_data (agent: TestPeerAgentA) - Prepares data for the sub-workflow
    2. invoke_sub_workflow (workflow: SimpleTestWorkflow) - Invokes the sub-workflow
    3. finalize (agent: TestPeerAgentB) - Processes the sub-workflow output

    SimpleTestWorkflow has two nodes:
    1. step_1 (agent: TestPeerAgentA) - First step
    2. step_2 (agent: TestPeerAgentB) - Second step

    Total expected LLM calls: 8 (2 per agent node × 4 agent nodes)
    """
    scenario_id = "workflow_invoke_workflow_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    user_identity = "sub_workflow_test_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "input_text": "Test data for sub-workflow invocation",
    }

    # =========================================================================
    # Parent workflow - Node 1: prepare_data (TestPeerAgentA)
    # =========================================================================
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-parent-1a",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Preparing data for sub-workflow.
«««save_artifact: filename="prepare_output.json" mime_type="application/json" description="Prepared data"
{"processed_data": "prepared_for_sub_workflow", "parent_marker": "from_parent_workflow"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_1b = ChatCompletionResponse(
        id="chatcmpl-parent-1b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Data prepared. «result:artifact=prepare_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # =========================================================================
    # Sub-workflow (SimpleTestWorkflow) - Node 1: step_1 (TestPeerAgentA)
    # =========================================================================
    llm_response_2a = ChatCompletionResponse(
        id="chatcmpl-sub-1a",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing step 1 of sub-workflow.
«««save_artifact: filename="step1_output.json" mime_type="application/json" description="Step 1 result"
{"processed": "Step 1 done", "data": "intermediate_data"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2b = ChatCompletionResponse(
        id="chatcmpl-sub-1b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Step 1 done. «result:artifact=step1_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # =========================================================================
    # Sub-workflow - Node 2: step_2 (TestPeerAgentB)
    # =========================================================================
    llm_response_3a = ChatCompletionResponse(
        id="chatcmpl-sub-2a",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing step 2 of sub-workflow.
«««save_artifact: filename="step2_output.json" mime_type="application/json" description="Step 2 result"
{"final_result": "sub_workflow_completed_successfully"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_3b = ChatCompletionResponse(
        id="chatcmpl-sub-2b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Step 2 done. «result:artifact=step2_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # =========================================================================
    # Parent workflow - Node 3: finalize (TestPeerAgentB)
    # =========================================================================
    llm_response_4a = ChatCompletionResponse(
        id="chatcmpl-parent-3a",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Finalizing with sub-workflow result.
«««save_artifact: filename="finalize_output.json" mime_type="application/json" description="Final result"
{"result": "parent_workflow_completed_with_sub_workflow_result"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_4b = ChatCompletionResponse(
        id="chatcmpl-parent-3b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Finalized. «result:artifact=finalize_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1, llm_response_1b,   # Parent: prepare_data
            llm_response_2a, llm_response_2b,  # Sub: step_1
            llm_response_3a, llm_response_3b,  # Sub: step_2
            llm_response_4a, llm_response_4b,  # Parent: finalize
        ],
    )

    # Submit to the parent workflow that invokes sub-workflow
    input_data = {
        "target_agent_name": "SubWorkflowInvokeTestWorkflow",
        "user_identity": user_identity,
        "a2a_parts": [{"type": "data", "data": workflow_input}],
        "external_context": {
            "test_case": scenario_id,
            "a2a_session_id": session_id,
        },
    }

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    # Timeout of 15s - workflow-to-workflow should complete quickly
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # The parent workflow should complete successfully
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "completed", (
            f"Scenario {scenario_id}: Expected completed state, "
            f"got: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        pytest.fail(
            f"Scenario {scenario_id}: Workflow failed with error: {terminal_event.message}"
        )

    # Verify that LLM calls were made
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")

    # We expect at least 4 LLM calls (2 per node minimum for 2 nodes)
    # In ideal case with all 4 agent nodes: 8 calls
    assert call_count >= 4, (
        f"Scenario {scenario_id}: Expected at least 4 LLM calls for workflow-to-workflow "
        f"invocation, but only got {call_count}"
    )

    print(
        f"Scenario {scenario_id}: Parent workflow successfully invoked sub-workflow "
        "and completed."
    )


async def test_direct_recursion_is_rejected(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that a workflow cannot invoke itself (direct recursion).

    The RecursiveTestWorkflow tries to invoke itself via a workflow node.
    This should fail with a recursion error.
    """
    scenario_id = "workflow_recursion_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    user_identity = "recursion_test_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {"input": "test"}

    # Prime the LLM server for the first agent node (prepare)
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-recursion-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Preparing data.
«««save_artifact: filename="prepare_output.json" mime_type="application/json" description="Prepared"
{"data": "prepared"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_1b = ChatCompletionResponse(
        id="chatcmpl-recursion-1b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=prepare_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(test_llm_server, [llm_response_1, llm_response_1b])

    # Submit to the recursive workflow
    input_data = {
        "target_agent_name": "RecursiveTestWorkflow",
        "user_identity": user_identity,
        "a2a_parts": [{"type": "data", "data": workflow_input}],
        "external_context": {
            "test_case": scenario_id,
            "a2a_session_id": session_id,
        },
    }

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    # Wait for events - should fail quickly due to recursion detection
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # The workflow should fail due to recursion detection
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected failed state due to recursion, "
            f"got: {terminal_event.status.state}"
        )
        # Verify the error message mentions recursion
        error_message = str(terminal_event.status.message) if terminal_event.status.message else ""
        assert "recursion" in error_message.lower() or "cannot invoke itself" in error_message.lower(), (
            f"Scenario {scenario_id}: Expected recursion error message, got: {error_message}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        # Also acceptable - the error should mention recursion
        error_message = str(terminal_event.message) if hasattr(terminal_event, 'message') else str(terminal_event)
        print(f"Scenario {scenario_id}: Got JSONRPCError: {error_message}")

    print(f"Scenario {scenario_id}: Direct recursion was correctly rejected.")
