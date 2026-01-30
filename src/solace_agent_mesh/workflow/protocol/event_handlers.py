"""
Event handlers for WorkflowExecutorComponent.
"""

import logging
import uuid
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Any

from solace_ai_connector.common.message import Message as SolaceMessage
from a2a.types import (
    A2ARequest,
    AgentCard,
    JSONRPCResponse,
    Task,
    TaskState,
    Message as A2AMessage,
)
from ...common import a2a
from ...common.data_parts import WorkflowExecutionStartData
from ..workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState

if TYPE_CHECKING:
    from ..component import WorkflowExecutorComponent

log = logging.getLogger(__name__)


async def _extract_workflow_input(
    component: "WorkflowExecutorComponent",
    message: A2AMessage,
) -> Dict[str, Any]:
    """Extract workflow input from A2A message.

    Supports multiple input modes:
    1. FilePart with artifact URI (structured invocation from workflows/agents)
    2. DataPart (direct data, skipping StructuredInvocationRequest)
    3. TextPart (chat mode)
    """
    from ...agent.utils.artifact_helpers import parse_artifact_uri

    # 1. Check for FilePart with artifact URI (unified structured invocation)
    file_parts = a2a.get_file_parts_from_message(message)
    for file_part in file_parts:
        uri = a2a.get_uri_from_file_part(file_part)
        if uri and uri.startswith("artifact://"):
            try:
                # Parse the artifact URI to get source app_name and other params
                uri_parts = parse_artifact_uri(uri)
                artifact = await component.artifact_service.load_artifact(
                    app_name=uri_parts["app_name"],
                    user_id=uri_parts["user_id"],
                    session_id=uri_parts["session_id"],
                    filename=uri_parts["filename"],
                    version=uri_parts["version"],
                )
                if artifact and artifact.inline_data:
                    return json.loads(artifact.inline_data.data.decode("utf-8"))
            except Exception as e:
                log.warning(
                    f"{component.log_identifier} Failed to load input artifact "
                    f"from URI {uri}: {e}"
                )

    # 2. Check for DataPart (Parameter Mode via direct data)
    # Skip StructuredInvocationRequest data parts - look for actual input data
    data_parts = a2a.get_data_parts_from_message(message)
    for data_part in data_parts:
        # Skip structured invocation metadata
        if (isinstance(data_part.data, dict) and
                data_part.data.get("type") == "structured_invocation_request"):
            continue
        return data_part.data

    # 3. Check for TextPart (Chat Mode)
    text = a2a.get_text_from_message(message)
    if text:
        return {"text": text}

    return {}


async def handle_task_request(
    component: "WorkflowExecutorComponent", message: SolaceMessage
):
    """
    Handle incoming A2A SendMessageRequest for workflow execution.
    Entry point for workflow execution.
    """
    try:
        payload = message.get_payload()
        a2a_request = A2ARequest.model_validate(payload)

        # Extract message and context
        a2a_message = a2a.get_message_from_send_request(a2a_request)
        request_id = a2a.get_request_id(a2a_request)

        # Extract user properties
        user_properties = message.get_user_properties()
        user_id = user_properties.get("userId")
        user_config = user_properties.get("a2aUserConfig", {})
        client_id = user_properties.get("clientId")
        reply_to = user_properties.get("replyTo")

        # Extract and validate call depth
        call_depth = user_properties.get("callDepth", 0)
        max_call_depth = component.workflow_definition.max_call_depth
        if call_depth > max_call_depth:
            raise ValueError(
                f"Call depth {call_depth} exceeds maximum allowed depth of {max_call_depth}. "
                "This may indicate infinite recursion in workflow/agent calls."
            )

        # Check if this is a structured invocation request
        # (from gateway or another workflow/agent)
        is_structured_invocation = False
        data_parts = a2a.get_data_parts_from_message(a2a_message)
        for data_part in data_parts:
            if (isinstance(data_part.data, dict) and
                    data_part.data.get("type") == "structured_invocation_request"):
                is_structured_invocation = True
                log.debug(
                    f"{component.log_identifier} Detected StructuredInvocationRequest in incoming message"
                )
                break

        # Create A2A context
        # The gateway/client is the source of truth for the task ID.
        # The workflow adopts the ID from the JSON-RPC request envelope.
        logical_task_id = str(request_id)

        # Use the logical task ID as the workflow task ID for tracking
        workflow_task_id = logical_task_id

        a2a_context = {
            "logical_task_id": logical_task_id,
            "session_id": a2a_message.context_id,
            "user_id": user_id,
            "client_id": client_id,
            "a2a_user_config": user_config,
            "jsonrpc_request_id": request_id,
            "replyToTopic": reply_to,
            "call_depth": call_depth,
            "is_structured_invocation": is_structured_invocation,
        }
        # Note: original_solace_message is NOT stored in a2a_context to avoid
        # serialization issues when a2a_context is stored in ADK session state.
        # It is stored in WorkflowExecutionContext instead.

        # Initialize workflow state
        workflow_state = await _initialize_workflow_state(
            component, a2a_context
        )

        # Extract and store workflow input
        workflow_input = await _extract_workflow_input(
            component, a2a_message
        )
        workflow_state.node_outputs["workflow_input"] = {"output": workflow_input}
        log.info(
            f"{component.log_identifier} Workflow input extracted: {list(workflow_input.keys())}"
        )

        # Create execution context
        workflow_context = WorkflowExecutionContext(
            workflow_task_id=workflow_task_id, a2a_context=a2a_context
        )
        workflow_context.workflow_state = workflow_state

        # Store the original Solace message separately to avoid serialization issues
        workflow_context.set_original_solace_message(message)

        # Track active workflow
        with component.active_workflows_lock:
            component.active_workflows[workflow_task_id] = workflow_context

        # Start execution
        log.info(f"{component.log_identifier} Starting workflow {workflow_task_id}")

        # Publish start event
        await component.publish_workflow_event(
            workflow_context,
            WorkflowExecutionStartData(
                type="workflow_execution_start",
                workflow_name=component.workflow_name,
                execution_id=workflow_task_id,
                workflow_input=workflow_input,
            ),
        )

        await component.dag_executor.execute_workflow(
            workflow_state, workflow_context
        )

    except Exception as e:
        log.exception(f"{component.log_identifier} Error handling task request: {e}")
        
        # Send error response
        try:
            error_response = a2a.create_internal_error_response(
                message=f"Failed to start workflow: {e}",
                request_id=request_id,
                data={"taskId": logical_task_id} if 'logical_task_id' in locals() else None
            )
            
            if reply_to:
                component.publish_a2a_message(
                    payload=error_response.model_dump(exclude_none=True),
                    topic=reply_to,
                    user_properties={"a2aUserConfig": user_config} if 'user_config' in locals() else {}
                )
            
            # NACK the original message if possible
            message.call_negative_acknowledgements()
            
        except Exception as send_err:
            log.error(f"{component.log_identifier} Failed to send error response: {send_err}")
            # Fallback ACK to prevent redelivery loop if NACK fails or logic is broken
            try:
                message.call_acknowledgements()
            except Exception:
                pass


async def _initialize_workflow_state(
    component: "WorkflowExecutorComponent", a2a_context: Dict[str, Any]
) -> WorkflowExecutionState:
    execution_id = a2a_context["logical_task_id"]

    state = WorkflowExecutionState(
        workflow_name=component.workflow_name,
        execution_id=execution_id,
        start_time=datetime.now(timezone.utc),
        pending_nodes=[],  # Will be populated by execute_workflow loop
    )

    # Store in session
    session = await component.session_service.get_session(
        app_name=component.workflow_name,
        user_id=a2a_context["user_id"],
        session_id=a2a_context["session_id"],
    )
    
    if not session:
        session = await component.session_service.create_session(
            app_name=component.workflow_name,
            user_id=a2a_context["user_id"],
            session_id=a2a_context["session_id"],
        )

    session.state["workflow_execution"] = state.model_dump()
    # Note: Session state is persisted automatically by the SessionService
    # when managed through ADK operations (get_session, append_event, etc.)

    return state


async def handle_agent_response(
    component: "WorkflowExecutorComponent", message: SolaceMessage
):
    """Handle response from an agent."""
    try:
        topic = message.get_topic()
        payload = message.get_payload()
        
        # Extract sub-task ID from topic
        # Topic format: .../agent/response/{workflow_name}/{sub_task_id}
        # or .../agent/status/{workflow_name}/{sub_task_id}
        
        parts = topic.split("/")
        sub_task_id = parts[-1]

        # Find workflow context
        # We need to map sub_task_id to workflow_task_id
        # This mapping is stored in the cache service by AgentCaller
        workflow_task_id = component.cache_service.get_data(sub_task_id)
        
        if not workflow_task_id:
            log.warning(f"{component.log_identifier} Received response for unknown/expired sub-task: {sub_task_id}")
            message.call_acknowledgements()
            return

        with component.active_workflows_lock:
            workflow_context = component.active_workflows.get(workflow_task_id)

        if not workflow_context:
            log.warning(f"{component.log_identifier} Received response for unknown workflow: {workflow_task_id}")
            message.call_acknowledgements()
            return

        # Parse response
        response = JSONRPCResponse.model_validate(payload)
        result = a2a.get_response_result(response)
        
        if isinstance(result, Task):
            # Final response
            # Extract StructuredInvocationResult from Task
            # The agent should have returned it as a DataPart
            # StructuredInvocationHandler puts StructuredInvocationResult in the message.

            task_message = result.status.message
            data_parts = a2a.get_data_parts_from_message(task_message)

            node_result = None
            for part in data_parts:
                if part.data.get("type") == "structured_invocation_result":
                    from ...common.data_parts import StructuredInvocationResult
                    node_result = StructuredInvocationResult.model_validate(part.data)
                    break

            if node_result:
                # Remove the cache entry for timeout tracking since we received a response
                component.cache_service.remove_data(sub_task_id)

                await component.dag_executor.handle_node_completion(
                    workflow_context, sub_task_id, node_result
                )
            elif result.status.state == TaskState.failed:
                # Sub-workflow or agent failed - create a failure result
                # Remove the cache entry since we received a response
                component.cache_service.remove_data(sub_task_id)

                # Extract error message from the task status
                error_text = a2a.get_text_from_message(task_message) if task_message else "Unknown error"
                log.warning(
                    f"{component.log_identifier} Sub-task {sub_task_id} failed: {error_text}"
                )

                # Create a failure StructuredInvocationResult
                from ...common.data_parts import StructuredInvocationResult
                failure_result = StructuredInvocationResult(
                    type="structured_invocation_result",
                    status="error",
                    error_message=error_text,
                )

                await component.dag_executor.handle_node_completion(
                    workflow_context, sub_task_id, failure_result
                )
            elif result.status.state == TaskState.canceled:
                # Sub-task was cancelled - this is expected when workflow is being cancelled
                # Remove the cache entry since we received a response
                component.cache_service.remove_data(sub_task_id)
                
                log.info(
                    f"{component.log_identifier} Sub-task {sub_task_id} was cancelled"
                )
                
                # Don't call handle_node_completion for cancelled tasks
                # The workflow cancellation handler will finalize the workflow
            else:
                log.error(f"{component.log_identifier} Received Task response without StructuredInvocationResult")
                
        # Handle status updates if needed (for logging/monitoring)
        
        message.call_acknowledgements()

    except Exception as e:
        log.exception(f"{component.log_identifier} Error handling agent response: {e}")
        
        # If we have a workflow context, fail the workflow gracefully
        if 'workflow_context' in locals() and workflow_context:
            try:
                await component.finalize_workflow_failure(workflow_context, e)
            except Exception as final_err:
                log.error(f"{component.log_identifier} Failed to finalize workflow failure: {final_err}")
        
        message.call_acknowledgements() # ACK to avoid redelivery loop on error


async def handle_cancel_request(
    component: "WorkflowExecutorComponent",
    task_id: str,
    message: SolaceMessage,
):
    """
    Handle workflow cancellation request.

    When a CancelTaskRequest is received:
    1. Signal cancellation to the workflow context
    2. Cancel any active agent sub-tasks
    3. Finalize the workflow as cancelled
    4. Clean up resources
    """
    log_id = f"{component.log_identifier}[CancelWorkflow:{task_id}]"
    log.info(f"{log_id} Received cancellation request")

    # Find the workflow context
    with component.active_workflows_lock:
        workflow_context = component.active_workflows.get(task_id)

    if not workflow_context:
        log.warning(f"{log_id} Workflow not found or already completed")
        message.call_acknowledgements()
        return

    # Signal cancellation to the workflow context
    workflow_context.cancel()
    log.info(f"{log_id} Cancellation signal sent to workflow")

    # Cancel any active agent sub-tasks
    sub_task_ids = workflow_context.get_all_sub_task_ids()
    if sub_task_ids:
        log.info(f"{log_id} Cancelling {len(sub_task_ids)} active agent sub-task(s)")

        for sub_task_id in sub_task_ids:
            node_id = workflow_context.get_node_id_for_sub_task(sub_task_id)
            if not node_id:
                continue

            # Get the target agent for this node
            # For map/loop iteration nodes (e.g., "map_node_0"), we need to find the
            # original node definition. Iteration node IDs follow the pattern:
            # - Map iterations: "{map_node_id}_{index}" (e.g., "generate_data_0")
            # - Loop iterations: "{loop_node_id}_iter_{iteration}" (e.g., "poll_status_iter_0")
            node = component.dag_executor.get_node_by_id(node_id)
            
            if not node:
                # Try to find the original node for iteration nodes
                # Check for map iteration pattern: "{parent_id}_{index}"
                # Check for loop iteration pattern: "{parent_id}_iter_{iteration}"
                original_node_id = None
                if "_iter_" in node_id:
                    # Loop iteration: extract parent node ID
                    original_node_id = node_id.rsplit("_iter_", 1)[0]
                elif "_" in node_id:
                    # Map iteration: extract parent node ID (everything before last underscore that's a number)
                    parts = node_id.rsplit("_", 1)
                    if len(parts) == 2 and parts[1].isdigit():
                        original_node_id = parts[0]
                
                if original_node_id:
                    # Get the parent control node (map or loop)
                    parent_node = component.dag_executor.get_node_by_id(original_node_id)
                    if parent_node:
                        # Get the inner node that the map/loop executes
                        inner_node_id = getattr(parent_node, 'node', None)
                        if inner_node_id:
                            node = component.dag_executor.get_node_by_id(inner_node_id)
            
            if node:
                # Get agent_name or workflow_name depending on node type
                target_name = getattr(node, 'agent_name', None) or getattr(node, 'workflow_name', None)
                if target_name:
                    try:
                        from ...common import a2a
                        cancel_request = a2a.create_cancel_task_request(task_id=sub_task_id)
                        target_topic = a2a.get_agent_request_topic(
                            component.namespace, target_name
                        )
                        component.publish_a2a_message(
                            payload=cancel_request.model_dump(exclude_none=True),
                            topic=target_topic,
                            user_properties={"clientId": component.workflow_name},
                        )
                        log.info(
                            f"{log_id} Sent CancelTaskRequest to '{target_name}' "
                            f"for sub-task {sub_task_id}"
                        )
                    except Exception as e:
                        log.error(
                            f"{log_id} Failed to send CancelTaskRequest to "
                            f"'{target_name}': {e}"
                        )
            else:
                log.warning(
                    f"{log_id} Could not find node definition for node_id '{node_id}', "
                    f"cannot send cancel request for sub-task {sub_task_id}"
                )

    # Finalize the workflow as cancelled
    try:
        await component.finalize_workflow_cancelled(workflow_context)
    except Exception as e:
        log.error(f"{log_id} Error finalizing cancelled workflow: {e}")

    message.call_acknowledgements()
    log.info(f"{log_id} Cancellation complete")


def handle_agent_card_message(component: "WorkflowExecutorComponent", message: SolaceMessage):
    """Handle incoming agent card."""
    try:
        payload = message.get_payload()
        agent_card = AgentCard.model_validate(payload)
        component.agent_registry.add_or_update_agent(agent_card)
        message.call_acknowledgements()
    except Exception as e:
        log.error(f"{component.log_identifier} Error handling agent card: {e}")
        message.call_acknowledgements()
