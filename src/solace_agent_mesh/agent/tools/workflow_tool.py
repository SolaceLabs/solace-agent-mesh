"""
ADK Tool implementation for invoking Workflow agents via A2A.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

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
        log.info(
            "%s [WORKFLOW_DEBUG] _get_declaration called | target_agent=%s | input_schema=%s",
            self.log_identifier,
            self.target_agent_name,
            self.input_schema,
        )
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

        log.info(
            "%s [WORKFLOW_DEBUG] run_async ENTERED | target_agent=%s | args=%s",
            log_identifier,
            self.target_agent_name,
            args,
        )

        try:
            # 1. Prepare Input Artifact
            try:
                log.info("%s [WORKFLOW_DEBUG] About to call _prepare_input_artifact", log_identifier)
                (
                    payload_artifact_name,
                    payload_artifact_version,
                ) = await self._prepare_input_artifact(
                    args, tool_context, log_identifier
                )
                log.info("%s [WORKFLOW_DEBUG] _prepare_input_artifact returned successfully", log_identifier)
            except jsonschema.ValidationError as e:
                log.error(
                    "%s [WORKFLOW_DEBUG] Caught ValidationError in run_async | message=%s",
                    log_identifier,
                    e.message,
                )
                error_response = {
                    "status": "error",
                    "message": f"Input validation failed: {e.message}. Please provide required parameters or use input_artifact.",
                }
                log.info(
                    "%s [WORKFLOW_DEBUG] Returning validation error response to LLM | response=%s",
                    log_identifier,
                    error_response,
                )
                return error_response

            log.info(
                "%s [WORKFLOW_DEBUG] Input artifact prepared | artifact_name=%s | version=%s",
                log_identifier,
                payload_artifact_name,
                payload_artifact_version,
            )

            # 2. Prepare Context
            original_task_context = tool_context.state.get("a2a_context", {})
            main_logical_task_id = original_task_context.get(
                "logical_task_id", "unknown_task"
            )
            invocation_id = tool_context._invocation_context.invocation_id
            user_id = tool_context._invocation_context.user_id
            user_config = original_task_context.get("a2a_user_config", {})

            log.info(
                "%s [WORKFLOW_DEBUG] Context prepared | main_task_id=%s | invocation_id=%s | user_id=%s",
                log_identifier,
                main_logical_task_id,
                invocation_id,
                user_id,
            )

            # 3. Prepare Message
            a2a_message = self._prepare_a2a_message(
                payload_artifact_name,
                payload_artifact_version,
                tool_context,
                main_logical_task_id,
                original_task_context,
            )

            log.info(
                "%s [WORKFLOW_DEBUG] A2A message prepared | about to submit task",
                log_identifier,
            )

            # 4. Submit Task
            try:
                self._submit_workflow_task(
                    sub_task_id,
                    main_logical_task_id,
                    invocation_id,
                    tool_context,
                    original_task_context,
                    a2a_message,
                    user_id,
                    user_config,
                    log_identifier,
                )
            except MessageSizeExceededError as e:
                log.error("%s Message size exceeded: %s", log_identifier, e)
                return {
                    "status": "error",
                    "message": f"Error: {str(e)}. Message size exceeded.",
                }

            return None  # Fire-and-forget

        except Exception as e:
            log.exception("%s Error in WorkflowAgentTool: %s", log_identifier, e)
            return {
                "status": "error",
                "message": f"Failed to invoke workflow '{self.target_agent_name}': {e}",
            }

    async def _prepare_input_artifact(
        self, args: Dict[str, Any], tool_context: ToolContext, log_identifier: str
    ) -> Tuple[str, Optional[int]]:
        """
        Determines input mode, validates parameters, and creates implicit artifact if needed.
        Returns (artifact_name, artifact_version).
        """
        log.info(
            "%s [WORKFLOW_DEBUG] _prepare_input_artifact ENTERED | args=%s",
            log_identifier,
            args,
        )

        log.info("%s [WORKFLOW_DEBUG] Checking for input_artifact in args", log_identifier)
        input_artifact_name = args.get("input_artifact")
        log.info(
            "%s [WORKFLOW_DEBUG] input_artifact_name=%s",
            log_identifier,
            input_artifact_name,
        )

        if input_artifact_name:
            log.info(
                "%s Invoking in Artifact Mode with '%s'",
                log_identifier,
                input_artifact_name,
            )
            return input_artifact_name, None

        # Parameter Mode
        log.info("%s [WORKFLOW_DEBUG] Invoking in Parameter Mode", log_identifier)

        # Validate against strict schema
        log.info(
            "%s [WORKFLOW_DEBUG] About to validate args against schema | schema=%s",
            log_identifier,
            self.input_schema,
        )
        try:
            jsonschema.validate(instance=args, schema=self.input_schema)
            log.info("%s [WORKFLOW_DEBUG] Schema validation PASSED", log_identifier)
        except jsonschema.ValidationError as ve:
            log.error(
                "%s [WORKFLOW_DEBUG] Schema validation FAILED | error=%s | path=%s",
                log_identifier,
                ve.message,
                list(ve.absolute_path),
            )
            raise

        # Create implicit artifact
        payload_data = args
        payload_bytes = json.dumps(payload_data).encode("utf-8")

        # Generate unique filename using UUID to avoid collisions in parallel invocations
        sanitized_wf_name = "".join(
            c for c in self.target_agent_name if c.isalnum() or c in "_-"
        )
        unique_suffix = uuid.uuid4().hex[:8]
        payload_artifact_name = f"wi_{sanitized_wf_name}_{unique_suffix}.json"

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

        payload_artifact_version = save_result.get("data_version")

        log.info(
            "%s Created implicit input artifact: %s v%s",
            log_identifier,
            payload_artifact_name,
            payload_artifact_version,
        )

        return payload_artifact_name, payload_artifact_version

    def _prepare_a2a_message(
        self,
        payload_artifact_name: str,
        payload_artifact_version: Optional[int],
        tool_context: ToolContext,
        main_logical_task_id: str,
        original_task_context: Dict[str, Any],
    ) -> Any:
        """Constructs the A2A message with metadata."""
        a2a_message_parts = [
            a2a.create_text_part(
                text=f"Invoking workflow with input artifact: {payload_artifact_name}"
            )
        ]

        invoked_artifacts = []
        if payload_artifact_name:
            artifact_ref = {"filename": payload_artifact_name}
            if payload_artifact_version is not None:
                artifact_ref["version"] = payload_artifact_version
            invoked_artifacts.append(artifact_ref)

        a2a_metadata = {
            "sessionBehavior": "RUN_BASED",
            "parentTaskId": main_logical_task_id,
            "function_call_id": tool_context.function_call_id,
            "agent_name": self.target_agent_name,
            "invoked_with_artifacts": invoked_artifacts,
        }

        return a2a.create_user_message(
            parts=a2a_message_parts,
            metadata=a2a_metadata,
            context_id=original_task_context.get("contextId"),
        )

    def _submit_workflow_task(
        self,
        sub_task_id: str,
        main_logical_task_id: str,
        invocation_id: str,
        tool_context: ToolContext,
        original_task_context: Dict[str, Any],
        a2a_message: Any,
        user_id: str,
        user_config: Dict[str, Any],
        log_identifier: str,
    ):
        """Handles task registration, correlation data, and submission."""
        log.info(
            "%s [WORKFLOW_DEBUG] _submit_workflow_task ENTERED | sub_task_id=%s | main_task_id=%s",
            log_identifier,
            sub_task_id,
            main_logical_task_id,
        )

        # Register parallel call
        task_context_obj = None
        with self.host_component.active_tasks_lock:
            task_context_obj = self.host_component.active_tasks.get(
                main_logical_task_id
            )

        if not task_context_obj:
            log.error(
                "%s [WORKFLOW_DEBUG] TaskExecutionContext NOT FOUND | main_task_id=%s | active_tasks_keys=%s",
                log_identifier,
                main_logical_task_id,
                list(self.host_component.active_tasks.keys()),
            )
            raise ValueError(
                f"TaskExecutionContext not found for task '{main_logical_task_id}'"
            )

        # NOTE: register_parallel_call_sent is now called in
        # preregister_long_running_tools_callback (after_model_callback)
        # BEFORE tool execution begins. This prevents race conditions where
        # one tool completes before another registers.

        # Submit Task
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

        # DEBUG: Log the target agent name and expected topic
        from ...common import a2a as a2a_module

        expected_topic = a2a_module.get_agent_request_topic(
            self.host_component.namespace, self.target_agent_name
        )
        log.info(
            "%s [MSG_DEBUG] About to submit workflow task | target_agent_name=%s | expected_topic=%s",
            log_identifier,
            self.target_agent_name,
            expected_topic,
        )

        self.host_component.submit_a2a_task(
            target_agent_name=self.target_agent_name,
            a2a_message=a2a_message,
            user_id=user_id,
            user_config=user_config,
            sub_task_id=sub_task_id,
        )

        log.info(
            "%s Workflow task submitted to topic: %s", log_identifier, expected_topic
        )
