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
    a2a_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Extract workflow input from A2A message."""

    # 1. Check for artifact reference in metadata (Artifact Mode)
    if message.metadata and "invoked_with_artifacts" in message.metadata:
        artifacts = message.metadata["invoked_with_artifacts"]
        if artifacts:
            # Use first artifact
            artifact_ref = artifacts[0]
            filename = artifact_ref.get("filename")
            version = artifact_ref.get("version")

            if filename:
                # Load artifact content
                try:
                    # Resolve version if 'latest' or None
                    if version == "latest" or version is None:
                        versions = await component.artifact_service.list_versions(
                            app_name=component.workflow_name,
                            user_id=a2a_context["user_id"],
                            session_id=a2a_context["session_id"],
                            filename=filename,
                        )
                        version = max(versions) if versions else None

                    if version is not None:
                        artifact = await component.artifact_service.load_artifact(
                            app_name=component.workflow_name,
                            user_id=a2a_context["user_id"],
                            session_id=a2a_context["session_id"],
                            filename=filename,
                            version=version,
                        )

                        if artifact and artifact.inline_data:
                            return json.loads(artifact.inline_data.data.decode("utf-8"))

                except Exception as e:
                    log.warning(
                        f"{component.log_identifier} Failed to load input artifact {filename}: {e}"
                    )

    # 2. Check for DataPart (Parameter Mode via direct data)
    data_parts = a2a.get_data_parts_from_message(message)
    if data_parts:
        return data_parts[0].data

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
            component, a2a_message, a2a_context
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
            except:
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


def handle_cancel_request(component: "WorkflowExecutorComponent", task_id: str):
    """Handle workflow cancellation request."""
    # TODO: Implement cancellation logic
    pass


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
