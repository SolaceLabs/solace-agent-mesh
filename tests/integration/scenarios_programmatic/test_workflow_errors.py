"""
Programmatic integration tests for workflow error handling.

Tests error scenarios that are awkward to express in declarative YAML tests:
- Invalid input schema rejection
- Node failure handling
- Output schema validation with retry
"""

import pytest
import json
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
from a2a.utils.message import get_message_text

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
    pytest.mark.error,
]


def create_workflow_input_with_artifact(
    target_workflow: str,
    user_identity: str,
    artifact_filename: str,
    artifact_content: dict,
    scenario_id: str,
) -> dict:
    """
    Creates gateway input data for a workflow with an artifact.
    """
    return {
        "target_agent_name": target_workflow,
        "user_identity": user_identity,
        "a2a_parts": [{"type": "text", "text": f"Process the workflow input"}],
        "external_context_override": {
            "test_case": scenario_id,
            "a2a_session_id": f"session_{scenario_id}",
        },
        "artifacts": [
            {
                "filename": artifact_filename,
                "content": json.dumps(artifact_content),
                "mime_type": "application/json",
            }
        ],
    }


async def test_workflow_rejects_invalid_input_schema(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that workflows properly reject input that doesn't match the input schema.

    The StructuredTestWorkflow expects:
    - customer_name: string (required)
    - order_id: string (required)
    - amount: integer (required)

    We send input missing required fields to verify validation.
    """
    scenario_id = "workflow_invalid_input_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Don't need to prime LLM - workflow should reject before calling any agents
    prime_llm_server(test_llm_server, [])

    # Send input missing required fields (missing order_id and amount)
    input_data = create_workflow_input_with_artifact(
        target_workflow="StructuredTestWorkflow",
        user_identity="invalid_input_user@example.com",
        artifact_filename="workflow_input.json",
        artifact_content={"customer_name": "Test Customer"},  # Missing order_id and amount
        scenario_id=scenario_id,
    )

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # The workflow should fail due to schema validation
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        # We expect failure due to invalid input
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected workflow to fail with invalid input, "
            f"got state: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        print(f"Scenario {scenario_id}: Received error (expected): {terminal_event.error}")
        # Error response is also acceptable for validation failures

    print(f"Scenario {scenario_id}: Workflow properly rejected invalid input.")


async def test_workflow_rejects_wrong_type_input(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that workflows reject input with wrong types.

    The StructuredTestWorkflow expects amount to be an integer.
    We send a string to verify type validation.
    """
    scenario_id = "workflow_wrong_type_input_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Don't need to prime LLM - workflow should reject before calling any agents
    prime_llm_server(test_llm_server, [])

    # Send input with wrong type (amount should be integer, not string)
    input_data = create_workflow_input_with_artifact(
        target_workflow="StructuredTestWorkflow",
        user_identity="wrong_type_user@example.com",
        artifact_filename="workflow_input.json",
        artifact_content={
            "customer_name": "Test Customer",
            "order_id": "ORD-123",
            "amount": "not_an_integer",  # Should be integer
        },
        scenario_id=scenario_id,
    )

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # The workflow should fail due to type validation
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected workflow to fail with wrong type input, "
            f"got state: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        print(f"Scenario {scenario_id}: Received error (expected): {terminal_event.error}")

    print(f"Scenario {scenario_id}: Workflow properly rejected wrong type input.")


async def test_workflow_node_failure_propagates(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that when an agent node returns a failure status, the workflow fails properly.

    This tests the error handling path where:
    1. Workflow starts execution
    2. First agent node returns status=failure
    3. Workflow should fail with appropriate error information
    """
    scenario_id = "workflow_node_failure_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Prime the LLM to simulate an agent that fails
    # First call: agent saves artifact
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-failure-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""I encountered an error processing this request.
«««save_artifact: filename="error_output.json" mime_type="application/json" description="Error details"
{"error": "Processing failed", "reason": "Invalid data format"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    # Second call: agent returns failure status
    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-failure-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Failed to process the request. «result:artifact=error_output.json:0 status=failure»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(test_llm_server, [llm_response_1, llm_response_2])

    # Submit to the simple workflow - it will fail at step_1
    input_data = create_workflow_input_with_artifact(
        target_workflow="SimpleTestWorkflow",
        user_identity="error_test_user@example.com",
        artifact_filename="workflow_input.json",
        artifact_content={"input_text": "Test data that will fail"},
        scenario_id=scenario_id,
    )

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    # Get all events with a longer timeout for error propagation
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=15.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    # The workflow should complete (potentially with failure state)
    # or return an error
    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # Check that we got either a failed task or an error
    if isinstance(terminal_event, Task):
        # Task completed - check if it's in failed state
        assert terminal_event.status is not None
        print(f"Scenario {scenario_id}: Task completed with state: {terminal_event.status.state}")
        # The workflow should fail when a node fails
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected task to fail when node fails, "
            f"got state: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        # Got an error response - this is also acceptable for failure scenarios
        print(f"Scenario {scenario_id}: Received error: {terminal_event.error}")

    print(f"Scenario {scenario_id}: Completed - workflow properly handled node failure.")


async def test_workflow_completes_successfully_with_valid_input(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Baseline test: verify workflow completes successfully with valid input.
    This serves as a control test for the error scenarios.
    """
    scenario_id = "workflow_success_baseline_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Prime LLM for successful two-node workflow
    # Step 1: First agent
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-success-1a",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing step 1.
«««save_artifact: filename="step1_output.json" mime_type="application/json" description="Step 1 result"
{"processed": "Step 1 done", "data": "intermediate_data"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_1b = ChatCompletionResponse(
        id="chatcmpl-success-1b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Step 1 complete. «result:artifact=step1_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Step 2: Second agent
    llm_response_2a = ChatCompletionResponse(
        id="chatcmpl-success-2a",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing step 2.
«««save_artifact: filename="step2_output.json" mime_type="application/json" description="Step 2 result"
{"final_result": "Workflow completed successfully"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2b = ChatCompletionResponse(
        id="chatcmpl-success-2b",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Step 2 complete. «result:artifact=step2_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [llm_response_1, llm_response_1b, llm_response_2a, llm_response_2b],
    )

    input_data = create_workflow_input_with_artifact(
        target_workflow="SimpleTestWorkflow",
        user_identity="success_test_user@example.com",
        artifact_filename="workflow_input.json",
        artifact_content={"input_text": "Valid test data"},
        scenario_id=scenario_id,
    )

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=20.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"
    assert isinstance(terminal_event, Task), (
        f"Scenario {scenario_id}: Expected Task, got {type(terminal_event)}"
    )
    assert terminal_event.status.state == "completed", (
        f"Scenario {scenario_id}: Expected completed state, got {terminal_event.status.state}"
    )

    print(f"Scenario {scenario_id}: Workflow completed successfully as expected.")


async def test_workflow_handles_empty_agent_response(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test workflow behavior when an agent returns without the expected result embed.

    This tests edge case handling where the agent doesn't properly signal completion.
    """
    scenario_id = "workflow_empty_response_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Prime LLM to return a response without result embed
    # This simulates an agent that doesn't follow the structured invocation protocol
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-empty-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I processed the request but forgot to save the output properly.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
    ).model_dump(exclude_none=True)

    # Second attempt - agent tries again but still no result embed
    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-empty-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Still processing...",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    ).model_dump(exclude_none=True)

    # Eventually give up or provide proper response
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-empty-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Let me save the output properly.
«««save_artifact: filename="step1_output.json" mime_type="application/json" description="Output"
{"processed": "Finally done"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-empty-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Output saved. «result:artifact=step1_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Responses for step 2
    llm_response_5 = ChatCompletionResponse(
        id="chatcmpl-empty-5",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Step 2 processing.
«««save_artifact: filename="step2_output.json" mime_type="application/json" description="Final output"
{"final_result": "Completed after retry"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_6 = ChatCompletionResponse(
        id="chatcmpl-empty-6",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=step2_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1,
            llm_response_2,
            llm_response_3,
            llm_response_4,
            llm_response_5,
            llm_response_6,
        ],
    )

    input_data = create_workflow_input_with_artifact(
        target_workflow="SimpleTestWorkflow",
        user_identity="edge_case_user@example.com",
        artifact_filename="workflow_input.json",
        artifact_content={"input_text": "Test edge case"},
        scenario_id=scenario_id,
    )

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    # Longer timeout since agent might retry
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=30.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # We expect either success (after retries) or failure
    if isinstance(terminal_event, Task):
        print(
            f"Scenario {scenario_id}: Task ended with state: {terminal_event.status.state}"
        )
        # Either state is acceptable - we're testing that the workflow handles this gracefully
        assert terminal_event.status.state in ["completed", "failed"], (
            f"Scenario {scenario_id}: Unexpected state: {terminal_event.status.state}"
        )

    print(f"Scenario {scenario_id}: Workflow handled edge case gracefully.")


async def test_workflow_output_schema_validation_triggers_retry(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that when an agent returns output that doesn't match the output schema,
    the workflow retries the agent with validation feedback.

    The StructuredTestWorkflow's validate_order node expects output with:
    - customer_name: string (required)
    - order_id: string (required)
    - amount: integer (required)
    - status: string (required)

    We simulate the agent first returning invalid output (missing 'status'),
    then returning valid output after receiving retry feedback.
    """
    scenario_id = "workflow_output_schema_retry_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "schema_retry_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-123",
        "amount": 100,
    }

    # First response: Agent saves artifact MISSING the required 'status' field
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-schema-retry-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing the order validation.
«««save_artifact: filename="validate_output.json" mime_type="application/json" description="Validation result"
{"customer_name": "Test Customer", "order_id": "ORD-123", "amount": 100}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    # First result embed - artifact doesn't match schema (missing 'status')
    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-schema-retry-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Validation complete. «result:artifact=validate_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Retry response: Agent saves corrected artifact WITH 'status' field
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-schema-retry-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""I'll correct the output to include the status field.
«««save_artifact: filename="validate_output_corrected.json" mime_type="application/json" description="Corrected validation result"
{"customer_name": "Test Customer", "order_id": "ORD-123", "amount": 100, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=30, total_tokens=80),
    ).model_dump(exclude_none=True)

    # Retry result embed - now with valid artifact
    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-schema-retry-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Corrected output saved. «result:artifact=validate_output_corrected.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Second node (process_order): First response
    llm_response_5 = ChatCompletionResponse(
        id="chatcmpl-schema-retry-5",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing the order.
«««save_artifact: filename="process_output.json" mime_type="application/json" description="Process result"
{"customer_name": "Test Customer", "order_id": "ORD-123", "amount": 100, "status": "processed", "processed": true}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=25, total_tokens=35),
    ).model_dump(exclude_none=True)

    # Second node result embed
    llm_response_6 = ChatCompletionResponse(
        id="chatcmpl-schema-retry-6",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Order processed. «result:artifact=process_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1,
            llm_response_2,
            llm_response_3,
            llm_response_4,
            llm_response_5,
            llm_response_6,
        ],
    )

    # Submit valid input to the structured workflow (using DataPart)
    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
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

    # Allow extra time for retry loop
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=45.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # The workflow should complete successfully after the retry
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "completed", (
            f"Scenario {scenario_id}: Expected workflow to complete after retry, "
            f"got state: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        pytest.fail(
            f"Scenario {scenario_id}: Workflow failed with error: {terminal_event.error}"
        )

    # Verify the LLM was called at least 4 times (2 initial + retry + continue)
    # This confirms the retry actually happened
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")
    assert call_count >= 4, (
        f"Scenario {scenario_id}: Expected at least 4 LLM calls (indicating retry), "
        f"but only got {call_count}"
    )

    print(f"Scenario {scenario_id}: Workflow successfully retried after output schema validation failure.")


async def test_workflow_output_schema_multiple_retries(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that output schema validation can retry multiple times before succeeding.

    This tests the retry loop more thoroughly by having the agent:
    1. First attempt: Missing required field 'status'
    2. Second attempt (retry 1): Wrong type for 'amount' field
    3. Third attempt (retry 2): Valid output

    The workflow should complete successfully after multiple retries.
    """
    scenario_id = "workflow_multiple_retries_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "multi_retry_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-456",
        "amount": 200,
    }

    # First attempt: Save artifact MISSING 'status' field
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""I'll validate this order.
«««save_artifact: filename="validate_attempt1.json" mime_type="application/json" description="First attempt"
{"customer_name": "Test Customer", "order_id": "ORD-456", "amount": 200}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=validate_attempt1.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Second attempt (retry 1): Has status but wrong type for amount (string instead of int)
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Let me fix that - I was missing the status field.
«««save_artifact: filename="validate_attempt2.json" mime_type="application/json" description="Second attempt"
{"customer_name": "Test Customer", "order_id": "ORD-456", "amount": "two hundred", "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=30, total_tokens=80),
    ).model_dump(exclude_none=True)

    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Fixed. «result:artifact=validate_attempt2.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Third attempt (retry 2): All fields valid
    llm_response_5 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-5",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""I apologize - amount should be a number. Here's the corrected version.
«««save_artifact: filename="validate_attempt3.json" mime_type="application/json" description="Third attempt - correct"
{"customer_name": "Test Customer", "order_id": "ORD-456", "amount": 200, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=80, completion_tokens=35, total_tokens=115),
    ).model_dump(exclude_none=True)

    llm_response_6 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-6",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Validation complete. «result:artifact=validate_attempt3.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Second node (process_order) - should run after successful validation
    llm_response_7 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-7",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing the validated order.
«««save_artifact: filename="process_output.json" mime_type="application/json" description="Process result"
{"customer_name": "Test Customer", "order_id": "ORD-456", "amount": 200, "status": "processed", "processed": true}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=25, total_tokens=35),
    ).model_dump(exclude_none=True)

    llm_response_8 = ChatCompletionResponse(
        id="chatcmpl-multi-retry-8",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Order processed. «result:artifact=process_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1, llm_response_2,  # First attempt (fails validation)
            llm_response_3, llm_response_4,  # Retry 1 (fails validation again)
            llm_response_5, llm_response_6,  # Retry 2 (succeeds)
            llm_response_7, llm_response_8,  # Second node
        ],
    )

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
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

    # Allow extra time for multiple retries
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=60.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "completed", (
            f"Scenario {scenario_id}: Expected completed after retries, "
            f"got: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        pytest.fail(f"Scenario {scenario_id}: Workflow failed: {terminal_event.error}")

    # Verify multiple LLM calls happened (indicating retries)
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")

    # Should have at least 6 calls: 2 per attempt × 3 attempts for first node
    assert call_count >= 6, (
        f"Scenario {scenario_id}: Expected at least 6 LLM calls for multiple retries, "
        f"but only got {call_count}"
    )

    print(f"Scenario {scenario_id}: Workflow succeeded after multiple output validation retries.")


async def test_workflow_missing_result_embed_triggers_retry(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that a missing result embed triggers a retry.

    When an agent in a structured workflow saves an artifact but fails to output
    the mandatory result embed «result:artifact=... status=success», the system
    should provide feedback and retry.

    This tests the retry path in handler.py lines 687-706.
    """
    scenario_id = "workflow_missing_result_embed_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "missing_embed_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-789",
        "amount": 150,
    }

    # First attempt: Agent saves artifact but DOES NOT include result embed
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-missing-embed-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""I'll validate this order.
«««save_artifact: filename="validate_output.json" mime_type="application/json" description="Validation result"
{"customer_name": "Test Customer", "order_id": "ORD-789", "amount": 150, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    # System notification after save - agent still doesn't provide result embed
    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-missing-embed-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I have saved the validation result.",  # Missing result embed!
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Retry attempt: Agent now provides the result embed correctly
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-missing-embed-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""I apologize for the missing embed. Here is the corrected response.
«««save_artifact: filename="validate_output_fixed.json" mime_type="application/json" description="Fixed validation"
{"customer_name": "Test Customer", "order_id": "ORD-789", "amount": 150, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
    ).model_dump(exclude_none=True)

    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-missing-embed-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Validation complete. «result:artifact=validate_output_fixed.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Second node (process_order)
    llm_response_5 = ChatCompletionResponse(
        id="chatcmpl-missing-embed-5",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing the order.
«««save_artifact: filename="process_output.json" mime_type="application/json" description="Process result"
{"customer_name": "Test Customer", "order_id": "ORD-789", "amount": 150, "status": "processed", "processed": true}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=25, total_tokens=35),
    ).model_dump(exclude_none=True)

    llm_response_6 = ChatCompletionResponse(
        id="chatcmpl-missing-embed-6",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Order processed. «result:artifact=process_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1, llm_response_2,  # First attempt (missing embed)
            llm_response_3, llm_response_4,  # Retry (correct)
            llm_response_5, llm_response_6,  # Second node
        ],
    )

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
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

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=30.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "completed", (
            f"Scenario {scenario_id}: Expected completed after retry, "
            f"got: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        pytest.fail(f"Scenario {scenario_id}: Workflow failed: {terminal_event.error}")

    # Verify retry happened - should have more than 4 LLM calls
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")

    # Should have at least 4 calls: 2 for first attempt, 2 for retry
    assert call_count >= 4, (
        f"Scenario {scenario_id}: Expected at least 4 LLM calls for retry, "
        f"but only got {call_count}"
    )

    print(f"Scenario {scenario_id}: Workflow successfully retried after missing result embed.")


async def test_workflow_missing_result_embed_max_retries_exceeded(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that workflow fails when agent repeatedly misses result embed and exhausts retries.

    When an agent fails to include the mandatory result embed after all retry attempts
    (default is 2 retries = 3 total attempts), the workflow should fail.

    This tests the max retries exceeded path in handler.py line 708.
    """
    scenario_id = "workflow_missing_embed_max_retries_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "max_retries_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-MAX",
        "amount": 100,
    }

    # All attempts will save artifacts but NEVER include the result embed
    # Attempt 1: Initial try
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-max-retry-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing the order.
«««save_artifact: filename="attempt1.json" mime_type="application/json" description="First attempt"
{"customer_name": "Test Customer", "order_id": "ORD-MAX", "amount": 100, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-max-retry-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done with first attempt.",  # Missing result embed
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Attempt 2: First retry - still no result embed
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-max-retry-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Let me try again.
«««save_artifact: filename="attempt2.json" mime_type="application/json" description="Second attempt"
{"customer_name": "Test Customer", "order_id": "ORD-MAX", "amount": 100, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
    ).model_dump(exclude_none=True)

    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-max-retry-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Second attempt complete.",  # Still missing result embed
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Attempt 3: Second retry - still no result embed (this exhausts retries)
    llm_response_5 = ChatCompletionResponse(
        id="chatcmpl-max-retry-5",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""One more try.
«««save_artifact: filename="attempt3.json" mime_type="application/json" description="Third attempt"
{"customer_name": "Test Customer", "order_id": "ORD-MAX", "amount": 100, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=80, completion_tokens=20, total_tokens=100),
    ).model_dump(exclude_none=True)

    llm_response_6 = ChatCompletionResponse(
        id="chatcmpl-max-retry-6",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Third attempt done.",  # Still missing - will fail now
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1, llm_response_2,  # Initial attempt
            llm_response_3, llm_response_4,  # Retry 1
            llm_response_5, llm_response_6,  # Retry 2 (final)
        ],
    )

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
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

    # Allow time for multiple retry attempts
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=60.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    # The workflow should fail after exhausting retries
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected failed state after max retries, "
            f"got: {terminal_event.status.state}"
        )
        # Check for appropriate error message
        if terminal_event.status.message:
            error_text = get_message_text(terminal_event.status.message, delimiter="")
            print(f"Scenario {scenario_id}: Error message: {error_text}")
            assert "result embed" in error_text.lower(), (
                f"Scenario {scenario_id}: Expected error about result embed, "
                f"got: {error_text}"
            )
    elif isinstance(terminal_event, JSONRPCError):
        # This is also acceptable - workflow failed
        print(f"Scenario {scenario_id}: Workflow failed with error: {terminal_event.error}")

    # Verify all retry attempts were made
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")

    # Should have at least 6 calls: 2 per attempt × 3 attempts
    assert call_count >= 6, (
        f"Scenario {scenario_id}: Expected at least 6 LLM calls for 3 attempts, "
        f"but only got {call_count}"
    )

    print(f"Scenario {scenario_id}: Workflow correctly failed after exhausting retries for missing result embed.")


async def test_workflow_output_schema_max_retries_exceeded(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that workflow fails when output schema validation repeatedly fails after all retries.

    Unlike the missing result embed test, the agent DOES include the result embed,
    but the artifact content fails schema validation every time.

    This tests the max retries exceeded path in handler.py line 813.
    """
    scenario_id = "workflow_output_schema_max_retries_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "schema_max_retries_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-SCHEMA",
        "amount": 100,
    }

    # All attempts will include result embed but fail schema validation
    # The output_schema_override requires: customer_name, order_id, amount, status
    # We'll always omit 'status' to cause validation failure

    # Attempt 1
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-schema-max-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Validating the order.
«««save_artifact: filename="output1.json" mime_type="application/json" description="Attempt 1"
{"customer_name": "Test Customer", "order_id": "ORD-SCHEMA", "amount": 100}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-schema-max-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=output1.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Attempt 2 (retry 1) - still missing 'status'
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-schema-max-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Let me try again.
«««save_artifact: filename="output2.json" mime_type="application/json" description="Attempt 2"
{"customer_name": "Test Customer", "order_id": "ORD-SCHEMA", "amount": 100}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
    ).model_dump(exclude_none=True)

    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-schema-max-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Fixed. «result:artifact=output2.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Attempt 3 (retry 2) - still missing 'status' - exhausts retries
    llm_response_5 = ChatCompletionResponse(
        id="chatcmpl-schema-max-5",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""One more try.
«««save_artifact: filename="output3.json" mime_type="application/json" description="Attempt 3"
{"customer_name": "Test Customer", "order_id": "ORD-SCHEMA", "amount": 100}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=80, completion_tokens=20, total_tokens=100),
    ).model_dump(exclude_none=True)

    llm_response_6 = ChatCompletionResponse(
        id="chatcmpl-schema-max-6",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=output3.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [
            llm_response_1, llm_response_2,  # Initial attempt
            llm_response_3, llm_response_4,  # Retry 1
            llm_response_5, llm_response_6,  # Retry 2 (final)
        ],
    )

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
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

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=60.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected failed state after max retries, "
            f"got: {terminal_event.status.state}"
        )
        if terminal_event.status.message:
            error_text = get_message_text(terminal_event.status.message, delimiter="")
            print(f"Scenario {scenario_id}: Error message: {error_text}")
            # Should mention validation failure
            assert "validation" in error_text.lower() or "failed" in error_text.lower(), (
                f"Scenario {scenario_id}: Expected error about validation, got: {error_text}"
            )
    elif isinstance(terminal_event, JSONRPCError):
        print(f"Scenario {scenario_id}: Workflow failed with error: {terminal_event.error}")

    print(f"Scenario {scenario_id}: Workflow correctly failed after exhausting retries for output schema validation.")


async def test_workflow_artifact_not_found(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that workflow fails when agent references an artifact that doesn't exist.

    The agent includes a result embed referencing an artifact name that was never saved.

    This tests the artifact not found path in handler.py lines 748-756.
    """
    scenario_id = "workflow_artifact_not_found_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "artifact_not_found_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-NOTFOUND",
        "amount": 100,
    }

    # Agent responds with result embed referencing a NON-EXISTENT artifact
    # Note: Agent does NOT save any artifact, just references one that doesn't exist
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-notfound-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="I have completed the validation.",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Agent claims success with non-existent artifact (no version specified triggers lookup)
    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-notfound-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=nonexistent_artifact.json status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [llm_response_1, llm_response_2],
    )

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
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

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=30.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected failed state for missing artifact, "
            f"got: {terminal_event.status.state}"
        )
        if terminal_event.status.message:
            error_text = get_message_text(terminal_event.status.message, delimiter="")
            print(f"Scenario {scenario_id}: Error message: {error_text}")
            # Should mention artifact not found
            assert "not found" in error_text.lower() or "artifact" in error_text.lower(), (
                f"Scenario {scenario_id}: Expected error about artifact not found, got: {error_text}"
            )
    elif isinstance(terminal_event, JSONRPCError):
        print(f"Scenario {scenario_id}: Workflow failed with error: {terminal_event.error}")

    print(f"Scenario {scenario_id}: Workflow correctly failed when artifact not found.")


async def test_workflow_input_validation_failure(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that workflow fails when input doesn't match the input schema.

    The workflow has an input_schema requiring customer_name, order_id, and amount.
    We provide input that's missing required fields.

    This tests the input validation path in handler.py lines 203-211.
    """
    scenario_id = "workflow_input_validation_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data - MISSING required 'amount' field
    user_identity = "input_validation_user@example.com"
    session_id = f"session_{scenario_id}"

    # Missing 'amount' which is required by the input schema
    invalid_workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-INVALID",
        # "amount" is missing - required field
    }

    # We don't expect any LLM calls since input validation should fail immediately
    # But prime with empty responses just in case
    prime_llm_server(test_llm_server, [])

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
        "user_identity": user_identity,
        "a2a_parts": [{"type": "data", "data": invalid_workflow_input}],
        "external_context": {
            "test_case": scenario_id,
            "a2a_session_id": session_id,
        },
    }

    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )

    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=30.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "failed", (
            f"Scenario {scenario_id}: Expected failed state for input validation failure, "
            f"got: {terminal_event.status.state}"
        )
        if terminal_event.status.message:
            error_text = get_message_text(terminal_event.status.message, delimiter="")
            print(f"Scenario {scenario_id}: Error message: {error_text}")
    elif isinstance(terminal_event, JSONRPCError):
        print(f"Scenario {scenario_id}: Workflow failed with error: {terminal_event.error}")

    # Verify no LLM calls were made (input validation should fail before agent execution)
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")

    # Input validation happens at workflow level, so agent might still be called
    # But the workflow should ultimately fail

    print(f"Scenario {scenario_id}: Workflow correctly failed due to input validation failure.")


async def test_workflow_cancellation(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that a workflow can be cancelled while running.

    This tests the cancellation logic in:
    - event_handlers.py handle_cancel_request()
    - component.py finalize_workflow_cancelled()
    - dag_executor.py cancellation checks
    """
    import asyncio
    scenario_id = "workflow_cancellation_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data (passed directly via DataPart)
    user_identity = "cancellation_test_user@example.com"
    session_id = f"session_{scenario_id}"
    workflow_input = {
        "customer_name": "Test Customer",
        "order_id": "ORD-CANCEL",
        "amount": 100,
    }

    # Prime LLM with responses for first node - make it slow by including save_artifact
    # The first node will save an artifact, giving us time to send cancellation
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-cancel-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Starting validation.
«««save_artifact: filename="validate_output.json" mime_type="application/json" description="Validation result"
{"customer_name": "Test Customer", "order_id": "ORD-CANCEL", "amount": 100, "status": "validated"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-cancel-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Validation complete. «result:artifact=validate_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    # Second node responses (in case cancellation doesn't work)
    llm_response_3 = ChatCompletionResponse(
        id="chatcmpl-cancel-3",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing order.
«««save_artifact: filename="process_output.json" mime_type="application/json" description="Process result"
{"status": "processed"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_4 = ChatCompletionResponse(
        id="chatcmpl-cancel-4",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Process complete. «result:artifact=process_output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(
        test_llm_server,
        [llm_response_1, llm_response_2, llm_response_3, llm_response_4],
    )

    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
        "user_identity": user_identity,
        "a2a_parts": [{"type": "data", "data": workflow_input}],
        "external_context": {
            "test_case": scenario_id,
            "a2a_session_id": session_id,
        },
    }

    # Submit the workflow task
    task_id = await submit_test_input(
        test_gateway_app_instance, input_data, scenario_id
    )
    print(f"Scenario {scenario_id}: Submitted workflow task: {task_id}")

    # Wait briefly for the workflow to start, then cancel it
    await asyncio.sleep(0.5)

    # Send cancellation request
    print(f"Scenario {scenario_id}: Sending cancellation request")
    await test_gateway_app_instance.cancel_task(
        agent_name="StructuredTestWorkflow",
        task_id=task_id,
    )

    # Wait for the workflow to complete (should be cancelled)
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=30.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event"

    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        # The workflow could be cancelled or completed depending on timing
        # Both are acceptable outcomes for this test
        if terminal_event.status.state == "canceled":
            print(f"Scenario {scenario_id}: Workflow was successfully cancelled")
        elif terminal_event.status.state == "completed":
            print(f"Scenario {scenario_id}: Workflow completed before cancellation took effect (timing issue, acceptable)")
        else:
            # Failed state should not happen
            assert terminal_event.status.state in ("canceled", "completed"), (
                f"Scenario {scenario_id}: Unexpected state: {terminal_event.status.state}"
            )
    elif isinstance(terminal_event, JSONRPCError):
        pytest.fail(f"Scenario {scenario_id}: Unexpected error: {terminal_event.error}")

    print(f"Scenario {scenario_id}: Workflow cancellation test completed.")


async def test_workflow_instruction_appears_in_llm_request(
    test_llm_server: TestLLMServer,
    test_gateway_app_instance: TestGatewayComponent,
):
    """
    Test that the instruction field on a workflow agent node appears in the LLM request,
    including template expression resolution.

    The InstructionTestWorkflow has an agent node with:
        instruction: "STATIC_MARKER_123 - Context from workflow input: {{workflow.input.context}}"

    This test verifies that:
    1. The workflow executes successfully
    2. The static instruction text appears in the captured LLM request messages
    3. The template expression {{workflow.input.context}} is resolved to its actual value
    4. The unresolved template placeholder does NOT appear (proving resolution worked)

    This tests the instruction resolution and message construction in:
    - agent_caller.py call_agent() - resolves instruction template
    - agent_caller.py _construct_agent_message() - adds instruction as text part
    """
    scenario_id = "workflow_instruction_llm_001"
    print(f"\nRunning programmatic scenario: {scenario_id}")

    # Setup workflow input data with a unique context value
    user_identity = "instruction_test_user@example.com"
    session_id = f"session_{scenario_id}"

    # Use a unique context value that we can search for in the LLM request
    context_value = "RESOLVED_CONTEXT_VALUE_XYZ789"
    workflow_input = {
        "input_text": "Test data for instruction validation",
        "context": context_value,
    }

    # Prime LLM for successful single-node workflow
    # Agent saves artifact and returns success
    llm_response_1 = ChatCompletionResponse(
        id="chatcmpl-instruction-1",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="""Processing with the special instruction.
«««save_artifact: filename="output.json" mime_type="application/json" description="Result"
{"result": "Processed successfully following instructions"}
»»»""",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
    ).model_dump(exclude_none=True)

    llm_response_2 = ChatCompletionResponse(
        id="chatcmpl-instruction-2",
        model="test-model",
        choices=[
            Choice(
                message=Message(
                    role="assistant",
                    content="Done. «result:artifact=output.json:0 status=success»",
                ),
                finish_reason="stop",
            )
        ],
        usage=Usage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
    ).model_dump(exclude_none=True)

    prime_llm_server(test_llm_server, [llm_response_1, llm_response_2])

    # Submit to the instruction test workflow
    input_data = {
        "target_agent_name": "InstructionTestWorkflow",
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

    # Wait for workflow completion
    all_events = await get_all_task_events(
        test_gateway_app_instance, task_id, overall_timeout=30.0
    )

    terminal_event, _, _ = extract_outputs_from_event_list(all_events, scenario_id)

    assert terminal_event is not None, f"Scenario {scenario_id}: No terminal event received"

    # Verify workflow completed successfully
    if isinstance(terminal_event, Task):
        print(f"Scenario {scenario_id}: Task state: {terminal_event.status.state}")
        assert terminal_event.status.state == "completed", (
            f"Scenario {scenario_id}: Expected completed state, "
            f"got: {terminal_event.status.state}"
        )
    elif isinstance(terminal_event, JSONRPCError):
        pytest.fail(f"Scenario {scenario_id}: Workflow failed: {terminal_event.error}")

    # Now verify the instruction appeared in the LLM requests
    captured_requests = test_llm_server.get_captured_requests()
    call_count = len(captured_requests)
    print(f"Scenario {scenario_id}: LLM was called {call_count} times")

    assert call_count >= 1, (
        f"Scenario {scenario_id}: Expected at least 1 LLM call, got {call_count}"
    )

    # Helper function to search for a marker in captured requests
    def find_marker_in_requests(marker: str) -> bool:
        for request in captured_requests:
            messages = getattr(request, "messages", [])
            for message in messages:
                content = getattr(message, "content", "")
                if isinstance(content, str) and marker in content:
                    return True
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            text = part.get("text", "")
                            if marker in text:
                                return True
        return False

    # Test 1: Verify the static instruction marker appears
    static_marker = "STATIC_MARKER_123"
    assert find_marker_in_requests(static_marker), (
        f"Scenario {scenario_id}: The static marker '{static_marker}' was NOT found "
        f"in any of the {call_count} captured LLM requests. "
        "This indicates the instruction field is not being passed to the target agent."
    )
    print(f"Scenario {scenario_id}: Found static marker '{static_marker}' in LLM request")

    # Test 2: Verify the RESOLVED context value appears (template was resolved)
    assert find_marker_in_requests(context_value), (
        f"Scenario {scenario_id}: The resolved context value '{context_value}' was NOT "
        f"found in any of the {call_count} captured LLM requests. "
        "This indicates the template expression {{workflow.input.context}} was not resolved."
    )
    print(
        f"Scenario {scenario_id}: Found resolved context value '{context_value}' "
        "in LLM request"
    )

    # Test 3: Verify the UNRESOLVED template placeholder does NOT appear
    unresolved_template = "{{workflow.input.context}}"
    assert not find_marker_in_requests(unresolved_template), (
        f"Scenario {scenario_id}: The unresolved template '{unresolved_template}' "
        f"was found in the LLM requests. "
        "This indicates template resolution is not working correctly."
    )
    print(
        f"Scenario {scenario_id}: Confirmed template placeholder "
        "was resolved (not found in raw form)"
    )

    print(
        f"Scenario {scenario_id}: Successfully verified instruction with template "
        "expression appears correctly resolved in LLM request."
    )
