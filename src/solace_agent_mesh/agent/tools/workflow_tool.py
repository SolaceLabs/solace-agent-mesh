"""
ADK Tool implementation for invoking Workflow agents via A2A.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jsonschema
from google.adk.tools import BaseTool, ToolContext
from google.genai import types as adk_types

from ...common import a2a
from ...common.constants import DEFAULT_COMMUNICATION_TIMEOUT
from ...common.exceptions import MessageSizeExceededError
from ...agent.utils.artifact_helpers import save_artifact_with_metadata

log = logging.getLogger(__name__)

WORKFLOW_TOOL_PREFIX = "workflow_"
CORRELATION_DATA_PREFIX = "a2a_subtask_"


class WorkflowAgentTool(BaseTool):
    """
    An ADK Tool that represents a discovered Workflow agent.
    Supports dual-mode invocation:
    1. Parameter Mode: Pass arguments directly (validated against schema).
    2. Artifact Mode: Pass an 'input_artifact' reference.
    """

    is_long_running = True

    def __init__(
        self,
        target_agent_name: str,
        input_schema: Dict[str, Any],
        host_component,
    ):
        """
        Initializes the WorkflowAgentTool.

        Args:
            target_agent_name: The name of the workflow agent.
            input_schema: The JSON schema defining the workflow's input parameters.
            host_component: A reference to the SamAgentComponent instance.
        """
        tool_name = f"{WORKFLOW_TOOL_PREFIX}{target_agent_name}"
        # Sanitize tool name if necessary (replace hyphens with underscores)
        tool_name = tool_name.replace("-", "_")

        super().__init__(
            name=tool_name,
            description=f"Invoke the '{target_agent_name}' workflow.",
            is_long_running=True,
        )
        self.target_agent_name = target_agent_name
        self.input_schema = input_schema
        self.host_component = host_component
        self.log_identifier = (
            f"{host_component.log_identifier}[WorkflowTool:{target_agent_name}]"
        )

    def _get_declaration(self) -> adk_types.FunctionDeclaration:
        """
        Dynamically generates the FunctionDeclaration based on the workflow's input schema.
        Adds 'input_artifact' as an optional parameter and marks all parameters as optional
        to support dual-mode invocation.
        """
        properties = self.input_schema.get("properties", {})
        adk_properties = {}

        # Add input_artifact parameter
        adk_properties["input_artifact"] = adk_types.Schema(
            type=adk_types.Type.STRING,
            description="Filename of an existing artifact containing the input JSON data. Use this OR individual parameters.",
            nullable=True,
        )

        for prop_name, prop_def in properties.items():
            # Basic type mapping
            json_type = prop_def.get("type", "string")
            adk_type = adk_types.Type.STRING
            if json_type == "integer":
                adk_type = adk_types.Type.INTEGER
            elif json_type == "number":
                adk_type = adk_types.Type.NUMBER
            elif json_type == "boolean":
                adk_type = adk_types.Type.BOOLEAN
            elif json_type == "array":
                adk_type = adk_types.Type.ARRAY
            elif json_type == "object":
                adk_type = adk_types.Type.OBJECT

            adk_properties[prop_name] = adk_types.Schema(
                type=adk_type,
                description=prop_def.get("description", ""),
                nullable=True,  # Force optional
            )

        parameters_schema = adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties=adk_properties,
            required=[],  # All optional
        )

        return adk_types.FunctionDeclaration(
            name=self.name,
            description=f"Invoke the '{self.target_agent_name}' workflow. Dual-mode: provide parameters directly OR 'input_artifact'.",
            parameters=parameters_schema,
        )

    async def run_async(
        self, *, args: Dict[str, Any], tool_context: ToolContext
    ) -> Any:
        """
        Handles the workflow invocation.
        """
        sub_task_id = f"{CORRELATION_DATA_PREFIX}{uuid.uuid4().hex}"
        log_identifier = f"{self.log_identifier}[SubTask:{sub_task_id}]"

        try:
            # 1. Determine Input Mode
            input_artifact_name = args.get("input_artifact")
            payload_artifact_name = None

            if input_artifact_name:
                # Artifact Mode
                log.info(
                    "%s Invoking in Artifact Mode with '%s'",
                    log_identifier,
                    input_artifact_name,
                )
                payload_artifact_name = input_artifact_name
            else:
                # Parameter Mode
                log.info("%s Invoking in Parameter Mode", log_identifier)

                # Validate against strict schema
                try:
                    jsonschema.validate(instance=args, schema=self.input_schema)
                except jsonschema.ValidationError as e:
                    return {
                        "status": "error",
                        "message": f"Input validation failed: {e.message}. Please provide required parameters or use input_artifact.",
                    }

                # Create implicit artifact
                payload_data = args
                payload_bytes = json.dumps(payload_data).encode("utf-8")

                # Generate filename
                sanitized_wf_name = "".join(
                    c for c in self.target_agent_name if c.isalnum() or c in "_-"
                )
                payload_artifact_name = f"workflow_input_{sanitized_wf_name}_{uuid.uuid4().hex[:8]}.json"

                # Save artifact
                user_id = tool_context._invocation_context.user_id
                session_id = tool_context._invocation_context.session.id

                save_result = await save_artifact_with_metadata(
                    artifact_service=self.host_component.artifact_service,
                    app_name=self.host_component.agent_name,
                    user_id=user_id,
                    session_id=session_id,
                    filename=payload_artifact_name,
                    content_bytes=payload_bytes,
                    mime_type="application/json",
                    metadata_dict={
                        "description": f"Auto-generated input for workflow '{self.target_agent_name}'",
                        "source": "workflow_tool_implicit_creation",
                    },
                    timestamp=datetime.now(timezone.utc),
                )

                if save_result["status"] != "success":
                    raise RuntimeError(
                        f"Failed to save implicit input artifact: {save_result.get('message')}"
                    )

                log.info(
                    "%s Created implicit input artifact: %s",
                    log_identifier,
                    payload_artifact_name,
                )

            # 2. Prepare A2A Message
            original_task_context = tool_context.state.get("a2a_context", {})
            main_logical_task_id = original_task_context.get(
                "logical_task_id", "unknown_task"
            )
            invocation_id = tool_context._invocation_context.invocation_id
            user_id = tool_context._invocation_context.user_id
            user_config = original_task_context.get("a2a_user_config", {})

            # Register parallel call
            task_context_obj = None
            with self.host_component.active_tasks_lock:
                task_context_obj = self.host_component.active_tasks.get(
                    main_logical_task_id
                )

            if not task_context_obj:
                raise ValueError(
                    f"TaskExecutionContext not found for task '{main_logical_task_id}'"
                )

            task_context_obj.register_parallel_call_sent(invocation_id)

            # Construct message
            a2a_message_parts = [
                a2a.create_text_part(
                    text=f"Invoking workflow with input artifact: {payload_artifact_name}"
                )
            ]

            a2a_metadata = {
                "sessionBehavior": "RUN_BASED",
                "parentTaskId": main_logical_task_id,
                "function_call_id": tool_context.function_call_id,
                "agent_name": self.target_agent_name,
                "invoked_with_artifacts": [{"filename": payload_artifact_name}],
            }

            a2a_message = a2a.create_user_message(
                parts=a2a_message_parts,
                metadata=a2a_metadata,
                context_id=original_task_context.get("contextId"),
            )

            # 3. Submit Task
            correlation_data = {
                "adk_function_call_id": tool_context.function_call_id,
                "original_task_context": original_task_context,
                "peer_tool_name": self.name,
                "peer_agent_name": self.target_agent_name,
                "logical_task_id": main_logical_task_id,
                "invocation_id": invocation_id,
            }

            task_context_obj.register_peer_sub_task(sub_task_id, correlation_data)

            timeout_sec = self.host_component.get_config(
                "inter_agent_communication", {}
            ).get("request_timeout_seconds", DEFAULT_COMMUNICATION_TIMEOUT)

            self.host_component.cache_service.add_data(
                key=sub_task_id,
                value=main_logical_task_id,
                expiry=timeout_sec,
                component=self.host_component,
            )

            try:
                self.host_component.submit_a2a_task(
                    target_agent_name=self.target_agent_name,
                    a2a_message=a2a_message,
                    user_id=user_id,
                    user_config=user_config,
                    sub_task_id=sub_task_id,
                )
            except MessageSizeExceededError as e:
                log.error("%s Message size exceeded: %s", log_identifier, e)
                return {
                    "status": "error",
                    "message": f"Error: {str(e)}. Message size exceeded.",
                }

            log.info("%s Workflow task submitted.", log_identifier)
            return None  # Fire-and-forget

        except Exception as e:
            log.exception("%s Error in WorkflowAgentTool: %s", log_identifier, e)
            return {
                "status": "error",
                "message": f"Failed to invoke workflow '{self.target_agent_name}': {e}",
            }
