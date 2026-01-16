"""
AgentCaller component for invoking agents via A2A.
"""

import logging
import uuid
import re
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, TYPE_CHECKING

from a2a.types import MessageSendParams, SendMessageRequest, Message as A2AMessage

from ..common import a2a
from ..common.data_parts import StructuredInvocationRequest
from ..common.agent_card_utils import get_schemas_from_agent_card
from ..agent.utils.artifact_helpers import (
    save_artifact_with_metadata,
    format_artifact_uri,
)
from .app import WorkflowNode, WorkflowInvokeNode
from .workflow_execution_context import WorkflowExecutionContext, WorkflowExecutionState

if TYPE_CHECKING:
    from .component import WorkflowExecutorComponent

log = logging.getLogger(__name__)


class AgentCaller:
    """Manages A2A calls to agents from workflow."""

    def __init__(self, host_component: "WorkflowExecutorComponent"):
        self.host = host_component

    def _resolve_string_with_templates(
        self, template_string: str, workflow_state: WorkflowExecutionState
    ) -> Optional[str]:
        """
        Resolve a string that may contain embedded template expressions.

        Unlike dag_executor.resolve_value which only handles strings that ARE templates,
        this method handles strings that CONTAIN templates (e.g., "Hello {{name}}!").

        Args:
            template_string: A string that may contain {{...}} template expressions
            workflow_state: Current workflow state for resolving variables

        Returns:
            The string with all template expressions resolved, or None if resolution fails
        """
        if not template_string:
            return None

        # Pattern to match {{...}} template expressions
        template_pattern = re.compile(r"\{\{\s*(.+?)\s*\}\}")

        def replace_template(match: re.Match) -> str:
            """Replace a single template match with its resolved value."""
            full_match = match.group(0)  # The full {{...}} string
            try:
                # Use dag_executor to resolve the full template
                resolved = self.host.dag_executor.resolve_value(
                    full_match, workflow_state
                )
                if resolved is None:
                    # Keep the original template if resolution fails
                    return full_match
                return str(resolved)
            except Exception as e:
                log.warning(
                    f"{self.host.log_identifier} Failed to resolve template "
                    f"'{full_match}': {e}"
                )
                return full_match

        # Replace all template expressions in the string
        resolved = template_pattern.sub(replace_template, template_string)
        return resolved

    async def call_agent(
        self,
        node: WorkflowNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
        sub_task_id: Optional[str] = None,
    ) -> str:
        """
        Invoke an agent for a workflow node.
        Returns sub-task ID for correlation.
        """
        log_id = f"{self.host.log_identifier}[CallAgent:{node.agent_name}]"

        # Generate sub-task ID if not provided
        if not sub_task_id:
            sub_task_id = (
                f"wf_{workflow_state.execution_id}_{node.id}_{uuid.uuid4().hex[:8]}"
            )
        # Resolve input data
        input_data = await self._resolve_node_input(node, workflow_state)

        # Resolve instruction template if present
        # Handles both full templates ({{...}}) and embedded templates within strings
        resolved_instruction = None
        if hasattr(node, "instruction") and node.instruction:
            resolved_instruction = self._resolve_string_with_templates(
                node.instruction, workflow_state
            )

        # Get agent card - required for proper structured invocation
        agent_card = self.host.agent_registry.get_agent(node.agent_name)
        if not agent_card:
            raise ValueError(
                f"Agent '{node.agent_name}' not found in registry. "
                f"Ensure the agent is running and has published its agent card before "
                f"starting the workflow."
            )

        # Get schemas from agent card extensions
        card_input_schema, card_output_schema = get_schemas_from_agent_card(agent_card)

        # Use override schemas if provided, otherwise use schemas from agent card
        input_schema = node.input_schema_override or card_input_schema
        output_schema = node.output_schema_override or card_output_schema

        # Construct A2A message
        message = await self._construct_agent_message(
            node,
            input_data,
            input_schema,
            output_schema,
            workflow_state,
            sub_task_id,
            workflow_context,
            resolved_instruction,
        )

        # Publish request
        await self._publish_agent_request(
            node.agent_name, message, sub_task_id, workflow_context
        )

        # Track in workflow context
        workflow_context.track_agent_call(node.id, sub_task_id)

        return sub_task_id

    async def call_workflow(
        self,
        node: WorkflowInvokeNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext,
        sub_task_id: Optional[str] = None,
    ) -> str:
        """
        Invoke a sub-workflow.

        Workflows register as agents, so this method adapts the workflow node
        to use the agent calling mechanism.

        Returns sub-task ID for correlation.
        """
        log_id = f"{self.host.log_identifier}[CallWorkflow:{node.workflow_name}]"

        # Generate sub-task ID if not provided
        if not sub_task_id:
            sub_task_id = (
                f"wf_{workflow_state.execution_id}_{node.id}_{uuid.uuid4().hex[:8]}"
            )

        # Create an adapter object that makes WorkflowInvokeNode compatible
        # with the existing _resolve_node_input and _construct_agent_message methods
        class WorkflowNodeAdapter:
            """Adapter to make WorkflowInvokeNode work with agent calling infrastructure."""

            def __init__(self, wf_node: WorkflowInvokeNode):
                self.id = wf_node.id
                self.type = "workflow"
                self.agent_name = wf_node.workflow_name  # Map workflow_name to agent_name
                self.input = wf_node.input
                self.instruction = wf_node.instruction
                self.input_schema_override = wf_node.input_schema_override
                self.output_schema_override = wf_node.output_schema_override
                self.depends_on = wf_node.depends_on

        adapted_node = WorkflowNodeAdapter(node)

        # Resolve input data
        input_data = await self._resolve_node_input(adapted_node, workflow_state)

        # Resolve instruction template if present
        resolved_instruction = None
        if node.instruction:
            resolved_instruction = self._resolve_string_with_templates(
                node.instruction, workflow_state
            )

        # Get agent card - required for proper structured invocation
        # Workflows publish their schemas in their agent cards
        agent_card = self.host.agent_registry.get_agent(node.workflow_name)
        if not agent_card:
            raise ValueError(
                f"Workflow '{node.workflow_name}' not found in registry. "
                f"Ensure the sub-workflow is running and has published its agent card before "
                f"starting the parent workflow."
            )

        # Get schemas from agent card extensions
        card_input_schema, card_output_schema = get_schemas_from_agent_card(agent_card)

        # Use override schemas if provided, otherwise use schemas from agent card
        input_schema = node.input_schema_override or card_input_schema
        output_schema = node.output_schema_override or card_output_schema

        # Construct A2A message
        message = await self._construct_agent_message(
            adapted_node,
            input_data,
            input_schema,
            output_schema,
            workflow_state,
            sub_task_id,
            workflow_context,
            resolved_instruction,
        )

        # Publish request to the sub-workflow
        await self._publish_agent_request(
            node.workflow_name, message, sub_task_id, workflow_context
        )

        # Track in workflow context
        workflow_context.track_agent_call(node.id, sub_task_id)

        log.info(
            f"{log_id} Invoked sub-workflow '{node.workflow_name}' (sub_task_id: {sub_task_id})"
        )

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

            # Check if dependency is a switch node - use workflow input instead of switch metadata
            dep_node = self.host.dag_executor.nodes.get(dep_id)
            if dep_node and dep_node.type == "switch":
                log.debug(
                    f"{self.host.log_identifier} Node '{node.id}' depends on switch '{dep_id}'. Using workflow input."
                )
                if "workflow_input" not in workflow_state.node_outputs:
                    raise ValueError("Workflow input has not been initialized")
                return workflow_state.node_outputs["workflow_input"]["output"]

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
«result:artifact=<your_artifact_name>:<version> status=success»

For example: «result:artifact=analysis_results.json:0 status=success»

This is required for the workflow to continue. Without this result embed, the workflow will fail.
"""
        else:
            return """
REMINDER: When you complete this task, you MUST end your response with:
«result:artifact=<your_artifact_name>:<version> status=success»

This is MANDATORY for the workflow to continue.
"""

    async def _construct_agent_message(
        self,
        node: WorkflowNode,
        input_data: Dict[str, Any],
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        workflow_state: WorkflowExecutionState,
        sub_task_id: str,
        workflow_context: WorkflowExecutionContext,
        resolved_instruction: Optional[str] = None,
    ) -> A2AMessage:
        """Construct A2A message for agent."""

        # Build message parts
        parts = []

        # Generate unique output filename for this workflow node
        # Use last 8 chars of sub_task_id for uniqueness (contains UUID)
        unique_suffix = sub_task_id[-8:] if len(sub_task_id) >= 8 else sub_task_id
        # Sanitize workflow name (replace spaces/special chars with underscore)
        safe_workflow_name = re.sub(
            r"[^a-zA-Z0-9_-]", "_", workflow_state.workflow_name
        )
        # node.id already includes iteration index for map nodes (e.g., "generate_data_0")
        suggested_output_filename = f"{safe_workflow_name}_{node.id}_{unique_suffix}.json"

        # 1. Structured invocation request (must be first)
        invocation_request = StructuredInvocationRequest(
            type="structured_invocation_request",
            workflow_name=workflow_state.workflow_name,
            node_id=node.id,
            input_schema=input_schema,
            output_schema=output_schema,
            suggested_output_filename=suggested_output_filename,
        )
        parts.append(a2a.create_data_part(data=invocation_request.model_dump()))

        # 2. Add instruction text part if provided
        if resolved_instruction and resolved_instruction.strip():
            parts.append(a2a.create_text_part(text=resolved_instruction))

        # Determine if we should send as structured artifact or text
        # For structured invocations (workflow calls), we ALWAYS send input as FilePart
        # unless it's explicitly a single text schema. This ensures the receiver can
        # properly handle the structured input even if we don't have the agent's schema
        # yet (e.g., due to timing issues with agent card discovery).
        should_send_artifact = True
        if input_schema:
            # Only use text mode if schema is explicitly a single text field
            is_single_text = (
                input_schema.get("type") == "object"
                and len(input_schema.get("properties", {})) == 1
                and "text" in input_schema.get("properties", {})
                and input_schema["properties"]["text"].get("type") == "string"
            )
            if is_single_text:
                should_send_artifact = False

        if should_send_artifact:
            # Create and save input artifact, then add FilePart with URI
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
                        f"{self.host.log_identifier} Created input artifact for node "
                        f"{node.id}: {filename}"
                    )
                else:
                    raise RuntimeError(
                        f"Failed to save input artifact: {save_result.get('message')}"
                    )

            except Exception as e:
                log.error(
                    f"{self.host.log_identifier} Error saving input artifact for node "
                    f"{node.id}: {e}"
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
                "parentTaskId": workflow_context.workflow_task_id,
            },
        )

        return message

    async def _publish_agent_request(
        self,
        agent_name: str,
        message: A2AMessage,
        sub_task_id: str,
        workflow_context: WorkflowExecutionContext,
    ):
        """Publish A2A request to agent."""
        log_id = f"{self.host.log_identifier}[PublishAgentRequest:{agent_name}]"

        # Get agent request topic
        request_topic = a2a.get_agent_request_topic(self.host.namespace, agent_name)

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

        # Get current call depth and increment for outgoing request
        current_depth = workflow_context.a2a_context.get("call_depth", 0)

        # User properties
        user_properties = {
            "replyTo": reply_to_topic,
            "a2aStatusTopic": status_topic,
            "userId": workflow_context.a2a_context["user_id"],
            "a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {}),
            "callDepth": current_depth + 1,
        }

        # Publish request
        self.host.publish_a2a_message(
            payload=a2a_request.model_dump(by_alias=True, exclude_none=True),
            topic=request_topic,
            user_properties=user_properties,
        )

        log.debug(
            f"{log_id} Published agent request to {request_topic} (sub_task_id: {sub_task_id})"
        )

        # Set timeout tracking
        timeout_seconds = self.host.get_config("default_node_timeout_seconds", 300)
        self.host.cache_service.add_data(
            key=sub_task_id,
            value=workflow_context.workflow_task_id,
            expiry=timeout_seconds,
            component=self.host,
        )
