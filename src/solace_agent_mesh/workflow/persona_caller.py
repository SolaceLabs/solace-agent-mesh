"""
PersonaCaller component for invoking persona agents via A2A.
"""

import logging
import uuid
import re
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from a2a.types import MessageSendParams, SendMessageRequest, Message as A2AMessage

from ..common import a2a
from ..common.data_parts import WorkflowNodeRequestData
from ..common.agent_card_utils import get_schemas_from_agent_card
from ..agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    format_artifact_uri,
)
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

        # Get schemas from agent card extensions if available
        persona_card = self.host.agent_registry.get_agent(node.agent_persona)
        card_input_schema, card_output_schema = get_schemas_from_agent_card(persona_card)

        # Use override schemas if provided, otherwise use schemas from agent card
        input_schema = node.input_schema_override or card_input_schema
        output_schema = node.output_schema_override or card_output_schema

        # Construct A2A message
        message = await self._construct_persona_message(
            node,
            input_data,
            input_schema,
            output_schema,
            workflow_state,
            sub_task_id,
            workflow_context,
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
        """
        Resolve input mapping for a node.
        If input is not provided, infer it from dependencies.
        """
        # Case 1: Explicit Input Mapping
        if node.input is not None:
            resolved_input = {}
            for key, value in node.input.items():
                # Use DAGExecutor's resolve_value to handle templates and operators
                resolved_value = self.host.dag_executor.resolve_value(
                    value, workflow_state
                )
                resolved_input[key] = resolved_value
            return resolved_input

        # Case 2: Implicit Input Inference
        log.debug(
            f"{self.host.log_identifier} Node '{node.id}' has no explicit input. Inferring from dependencies."
        )

        # Case 2a: No dependencies (Initial Node) -> Use Workflow Input
        if not node.depends_on:
            if "workflow_input" not in workflow_state.node_outputs:
                raise ValueError("Workflow input has not been initialized")
            return workflow_state.node_outputs["workflow_input"]["output"]

        # Case 2b: Single Dependency -> Use Dependency Output
        if len(node.depends_on) == 1:
            dep_id = node.depends_on[0]
            if dep_id not in workflow_state.node_outputs:
                raise ValueError(f"Dependency '{dep_id}' has not completed")
            return workflow_state.node_outputs[dep_id]["output"]

        # Case 2c: Multiple Dependencies -> Ambiguous
        raise ValueError(
            f"Node '{node.id}' has multiple dependencies {node.depends_on} but no explicit 'input' mapping. "
            "Implicit input inference is only supported for nodes with 0 or 1 dependency. "
            "Please provide an explicit 'input' mapping."
        )


    def _generate_result_embed_reminder(
        self, output_schema: Optional[Dict[str, Any]]
    ) -> str:
        """Generate user-facing reminder about result embed requirement."""
        if output_schema:
            return """
REMINDER: When you complete this task, you MUST end your response with:
«result:artifact=<your_artifact_name>:v<version> status=success»

For example: «result:artifact=analysis_results.json:v0 status=success»

This is required for the workflow to continue. Without this result embed, the workflow will fail.
"""
        else:
            return """
REMINDER: When you complete this task, you MUST end your response with:
«result:artifact=<your_artifact_name>:v<version> status=success»

This is MANDATORY for the workflow to continue.
"""

    async def _construct_persona_message(
        self,
        node: WorkflowNode,
        input_data: Dict[str, Any],
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        workflow_state: WorkflowExecutionState,
        sub_task_id: str,
        workflow_context: WorkflowExecutionContext,
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

        # Determine if we should send as structured artifact or text
        should_send_artifact = False
        if input_schema:
            # Check if it's NOT a single text schema
            is_single_text = (
                input_schema.get("type") == "object"
                and len(input_schema.get("properties", {})) == 1
                and "text" in input_schema.get("properties", {})
                and input_schema["properties"]["text"].get("type") == "string"
            )
            should_send_artifact = not is_single_text

        if should_send_artifact:
            # Create and save input artifact
            filename = f"input_{node.id}_{sub_task_id}.json"
            content_bytes = json.dumps(input_data).encode("utf-8")
            user_id = workflow_context.a2a_context["user_id"]
            session_id = workflow_context.a2a_context["session_id"]

            try:
                save_result = await save_artifact_with_metadata(
                    artifact_service=self.host.artifact_service,
                    app_name=self.host.workflow_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=filename,
                    content_bytes=content_bytes,
                    mime_type="application/json",
                    metadata_dict={
                        "description": f"Input for node {node.id}",
                        "source": "workflow_execution",
                    },
                    timestamp=datetime.now(timezone.utc),
                )

                if save_result["status"] == "success":
                    version = save_result["data_version"]
                    uri = format_artifact_uri(
                        app_name=self.host.workflow_name,
                        user_id=user_id,
                        session_id=session_id,
                        filename=filename,
                        version=version,
                    )
                    parts.append(
                        a2a.create_file_part_from_uri(
                            uri=uri, name=filename, mime_type="application/json"
                        )
                    )
                    log.info(
                        f"{self.host.log_identifier} Created input artifact for node {node.id}: {filename}"
                    )
                else:
                    raise RuntimeError(
                        f"Failed to save input artifact: {save_result.get('message')}"
                    )

            except Exception as e:
                log.error(
                    f"{self.host.log_identifier} Error saving input artifact for node {node.id}: {e}"
                )
                raise e

        else:
            # Send as text/data parts (Chat Mode)
            if "query" in input_data:
                parts.append(a2a.create_text_part(text=input_data["query"]))
            elif "text" in input_data:
                parts.append(a2a.create_text_part(text=input_data["text"]))
            else:
                # Fallback for unstructured data without 'query'/'text' keys
                text_parts = []
                for key, value in input_data.items():
                    text_parts.append(f"{key}: {value}")
                if text_parts:
                    parts.append(a2a.create_text_part(text="\n".join(text_parts)))

        # Add reminder about result embed requirement
        reminder_text = self._generate_result_embed_reminder(output_schema)
        parts.append(a2a.create_text_part(text=reminder_text))

        # Construct message using helper function
        # Use the original workflow session ID as context_id so that RUN_BASED sessions
        # will be created as {workflow_session_id}:{sub_task_id}:run, allowing the workflow
        # to find artifacts saved by the node using get_original_session_id()
        message = a2a.create_user_message(
            parts=parts,
            task_id=sub_task_id,
            context_id=workflow_context.a2a_context["session_id"],
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
        log_id = f"{self.host.log_identifier}[PublishPersonaRequest:{persona_name}]"

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
