"""
PersonaCaller component for invoking persona agents via A2A.
"""

import logging
import uuid
import re
from typing import Any, Dict, Optional, TYPE_CHECKING

from a2a.types import MessageSendParams, SendMessageRequest, A2AMessage

from ..common import a2a
from ..common.data_parts import WorkflowNodeRequestData
from .app import WorkflowNode
from .workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState

if TYPE_CHECKING:
    from .component import WorkflowExecutorComponent

log = logging.getLogger(__name__)


class PersonaCaller:
    """Manages A2A calls to persona agents from workflow."""

    def __init__(self, host_component: "WorkflowExecutorComponent"):
        self.host = host_component

    async def call_persona(
        self,
        node: WorkflowNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
    ) -> str:
        """
        Invoke a persona agent for a workflow node.
        Returns sub-task ID for correlation.
        """
        log_id = f"{self.host.log_identifier}[CallPersona:{node.agent_persona}]"

        # Generate sub-task ID
        sub_task_id = (
            f"wf_{workflow_state.execution_id}_{node.id}_{uuid.uuid4().hex[:8]}"
        )

        # Resolve input data
        input_data = await self._resolve_node_input(node, workflow_state)

        # Get persona schemas from agent registry
        persona_card = self.host.agent_registry.get_agent(node.agent_persona)
        input_schema = node.input_schema_override or (
            persona_card.input_schema if persona_card else None
        )
        output_schema = node.output_schema_override or (
            persona_card.output_schema if persona_card else None
        )

        # Construct A2A message
        message = self._construct_persona_message(
            node,
            input_data,
            input_schema,
            output_schema,
            workflow_state,
            sub_task_id,
        )

        # Publish request
        await self._publish_persona_request(
            node.agent_persona, message, sub_task_id, workflow_context
        )

        # Track in workflow context
        workflow_context.track_persona_call(node.id, sub_task_id)

        return sub_task_id

    async def _resolve_node_input(
        self, node: WorkflowNode, workflow_state: WorkflowExecutionState
    ) -> Dict[str, Any]:
        """Resolve input mapping for a node."""
        resolved_input = {}

        for key, value in node.input.items():
            if isinstance(value, str) and value.startswith("{{"):
                # Template reference
                resolved_value = self._resolve_template(value, workflow_state)
                resolved_input[key] = resolved_value
            else:
                # Literal value
                resolved_input[key] = value

        return resolved_input

    def _resolve_template(
        self, template: str, workflow_state: WorkflowExecutionState
    ) -> Any:
        """
        Resolve template variable.
        Format: {{node_id.output.field_path}}
        """
        # Extract variable path
        match = re.match(r"\{\{(.+?)\}\}", template)
        if not match:
            return template

        path = match.group(1)
        parts = path.split(".")

        # Navigate path in workflow state
        if parts[0] == "workflow" and parts[1] == "input":
            # Reference to workflow input
            # TODO: implement workflow input storage
            pass
        else:
            # Reference to node output
            node_id = parts[0]
            if node_id not in workflow_state.node_outputs:
                raise ValueError(f"Referenced node '{node_id}' has not completed")

            # Navigate remaining path
            data = workflow_state.node_outputs[node_id]
            for part in parts[1:]:
                if isinstance(data, dict) and part in data:
                    data = data[part]
                else:
                    # Path not found
                    return None

            return data

    def _construct_persona_message(
        self,
        node: WorkflowNode,
        input_data: Dict[str, Any],
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        workflow_state: WorkflowExecutionState,
        sub_task_id: str,
    ) -> A2AMessage:
        """Construct A2A message for persona agent."""

        # Build message parts
        parts = []

        # 1. Workflow context (must be first)
        workflow_data = WorkflowNodeRequestData(
            type="workflow_node_request",
            workflow_name=workflow_state.workflow_name,
            node_id=node.id,
            input_schema=input_schema,
            output_schema=output_schema,
        )
        parts.append(a2a.create_data_part(data=workflow_data.model_dump()))

        # 2. User query/text content
        if "query" in input_data:
            parts.append(a2a.create_text_part(text=input_data["query"]))

        # 3. Additional input data
        for key, value in input_data.items():
            if key != "query":
                parts.append(a2a.create_data_part(data={key: value}))

        # Construct message
        message = A2AMessage(
            parts=parts,
            contextId=workflow_state.execution_id,
            metadata={
                "workflow_name": workflow_state.workflow_name,
                "node_id": node.id,
                "sub_task_id": sub_task_id,
            },
        )

        return message

    async def _publish_persona_request(
        self,
        persona_name: str,
        message: A2AMessage,
        sub_task_id: str,
        workflow_context: WorkflowExecutionContext,
    ):
        """Publish A2A request to persona agent."""

        # Get persona request topic
        request_topic = a2a.get_agent_request_topic(self.host.namespace, persona_name)

        # Create SendMessageRequest
        send_params = MessageSendParams(message=message)
        a2a_request = SendMessageRequest(id=sub_task_id, params=send_params)

        # Construct reply-to and status topics
        reply_to_topic = a2a.get_agent_response_topic(
            self.host.namespace, self.host.workflow_name, sub_task_id
        )
        status_topic = a2a.get_peer_agent_status_topic(
            self.host.namespace, self.host.workflow_name, sub_task_id
        )

        # User properties
        user_properties = {
            "replyTo": reply_to_topic,
            "a2aStatusTopic": status_topic,
            "userId": workflow_context.a2a_context["user_id"],
            "a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {}),
        }

        # Publish request
        self.host.publish_a2a_message(
            payload=a2a_request.model_dump(by_alias=True, exclude_none=True),
            topic=request_topic,
            user_properties=user_properties,
        )
        
        log.debug(f"{log_id} Published persona request to {request_topic} (sub_task_id: {sub_task_id})")

        # Set timeout tracking
        timeout_seconds = self.host.get_config("default_node_timeout_seconds", 300)
        self.host.cache_service.add_data(
            key=sub_task_id,
            value=workflow_context.workflow_task_id,
            expiry=timeout_seconds,
            component=self.host,
        )
