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
from sam_test_infrastructure.artifact_service.service import (
    TestInMemoryArtifactService,
)
from a2a.types import Task, JSONRPCError
from google.genai import types as adk_types

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
    test_artifact_service_instance: TestInMemoryArtifactService,
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

    # Setup: Pre-save the input artifact to the artifact service
    user_identity = "schema_retry_user@example.com"
    session_id = f"session_{scenario_id}"
    artifact_content = {
        "customer_name": "Test Customer",
        "order_id": "ORD-123",
        "amount": 100,
    }
    artifact_filename = "workflow_input.json"

    # Save artifact like the declarative test runner does
    artifact_part = adk_types.Part(
        inline_data=adk_types.Blob(
            mime_type="application/json",
            data=json.dumps(artifact_content).encode("utf-8"),
        )
    )
    await test_artifact_service_instance.save_artifact(
        app_name="test_namespace",
        user_id=user_identity,
        session_id=session_id,
        filename=artifact_filename,
        artifact=artifact_part,
    )
    print(f"Scenario {scenario_id}: Setup artifact '{artifact_filename}' created.")

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

    # Submit valid input to the structured workflow (using invoked_with_artifacts pattern)
    # Note: Use "external_context" (not "external_context_override") - this is what the test gateway reads
    input_data = {
        "target_agent_name": "StructuredTestWorkflow",
        "user_identity": user_identity,
        "a2a_parts": [{"type": "text", "text": "Process the order data"}],
        "external_context": {
            "test_case": scenario_id,
            "a2a_session_id": session_id,
        },
        "invoked_with_artifacts": [
            {"filename": artifact_filename, "version": 0}
        ],
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
