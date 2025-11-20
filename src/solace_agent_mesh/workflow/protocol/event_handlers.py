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
)
from ...common import a2a
from ..workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState

if TYPE_CHECKING:
    from ..component import WorkflowExecutorComponent

log = logging.getLogger(__name__)


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

        # DEBUG: Log task ID reception from gateway/client
        log.error(
            f"{component.log_identifier} [TASK_ID_DEBUG] RECEIVED workflow request from gateway/client | "
            f"logical_task_id={logical_task_id} | "
            f"jsonrpc_request_id={request_id} | "
            f"client_id={client_id} | "
            f"replyTo={reply_to} | "
            f"context_id={a2a_message.context_id}"
        )

        a2a_context = {
            "logical_task_id": logical_task_id,
            "session_id": a2a_message.context_id,
            "user_id": user_id,
            "client_id": client_id,
            "a2a_user_config": user_config,
            "jsonrpc_request_id": request_id,
            "original_solace_message": message,
            "replyToTopic": reply_to,
        }

        # Initialize workflow state
        workflow_state = await _initialize_workflow_state(
            component, a2a_context
        )

        # Create execution context
        workflow_context = WorkflowExecutionContext(
            workflow_task_id=workflow_task_id, a2a_context=a2a_context
        )
        workflow_context.workflow_state = workflow_state

        # Track active workflow
        with component.active_workflows_lock:
            component.active_workflows[workflow_task_id] = workflow_context

        # Start execution
        log.info(f"{component.log_identifier} Starting workflow {workflow_task_id}")
        await component.dag_executor.execute_workflow(
            workflow_state, workflow_context
        )

    except Exception as e:
        log.exception(f"{component.log_identifier} Error handling task request: {e}")
        # Send error response
        # ...


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


async def handle_persona_response(
    component: "WorkflowExecutorComponent", message: SolaceMessage
):
    """Handle response from a persona agent."""
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
        # This mapping is stored in the cache service by PersonaCaller
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
            # Extract WorkflowNodeResultData from Task
            # The agent should have returned it as a DataPart
            # But wait, standard agents return Task with status.message
            # WorkflowNodeHandler puts WorkflowNodeResultData in the message.
            
            task_message = result.status.message
            data_parts = a2a.get_data_parts_from_message(task_message)
            
            node_result = None
            for part in data_parts:
                if part.data.get("type") == "workflow_node_result":
                    from ...common.data_parts import WorkflowNodeResultData
                    node_result = WorkflowNodeResultData.model_validate(part.data)
                    break
            
            if node_result:
                await component.dag_executor.handle_node_completion(
                    workflow_context, sub_task_id, node_result
                )
            else:
                log.error(f"{component.log_identifier} Received Task response without WorkflowNodeResultData")
                
        # Handle status updates if needed (for logging/monitoring)
        
        message.call_acknowledgements()

    except Exception as e:
        log.exception(f"{component.log_identifier} Error handling persona response: {e}")
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
