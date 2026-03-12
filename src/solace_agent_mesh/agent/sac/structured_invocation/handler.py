"""
StructuredInvocationHandler implementation.

Enables agents to be invoked with schema-validated input/output,
functioning as a "structured function call" pattern. Used by workflows
and other programmatic callers that require predictable, validated responses.
"""

import logging
import json
import asyncio
import re
import yaml
import csv
import io
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from pydantic import ValidationError
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event as ADKEvent
from google.genai import types as adk_types
from google.adk.agents import RunConfig
from google.adk.agents.run_config import StreamingMode

from a2a.types import (
    Message as A2AMessage,
    FilePart,
    FileWithBytes,
    FileWithUri,
    TaskState,
)

from ....common import a2a
from ....common.data_parts import (
    ArtifactRef,
    StructuredInvocationRequest,
    StructuredInvocationResult,
)
from ....agent.adk.runner import run_adk_async_task_thread_wrapper
from ....common.utils.embeds.constants import EMBED_REGEX
from ....agent.utils.artifact_helpers import parse_artifact_uri

if TYPE_CHECKING:
    from ..component import SamAgentComponent

log = logging.getLogger(__name__)


class ResultEmbed:
    """Parsed result embed from agent output."""

    def __init__(
        self,
        artifact_name: Optional[str] = None,
        version: Optional[int] = None,
        status: str = "success",
        message: Optional[str] = None,
    ):
        self.artifact_name = artifact_name
        self.version = version
        self.status = status
        self.message = message


class StructuredInvocationHandler:
    """
    Handles structured invocation logic for an agent.

    Enables agents to be invoked with schema-validated input and output,
    supporting retry on validation failure. Used by workflows and other
    programmatic callers that need predictable, validated responses.
    """

    def __init__(self, host_component: "SamAgentComponent"):
        self.host = host_component
        self.input_schema = host_component.get_config("input_schema")
        self.output_schema = host_component.get_config("output_schema")
        self.max_validation_retries = host_component.get_config(
            "validation_max_retries", 2
        )

    def extract_structured_invocation_context(
        self, message: A2AMessage
    ) -> Optional[StructuredInvocationRequest]:
        """
        Extract structured invocation context from message if present.
        Structured invocation messages contain StructuredInvocationRequest in a DataPart.

        Note: The DataPart may not be first in the message - the base gateway prepends
        a timestamp TextPart. We scan all DataParts to find the request.
        """
        if not message.parts:
            return None

        # Scan all DataParts for structured invocation request
        # The base gateway may prepend other parts (e.g., timestamp), so we can't assume position
        data_parts = a2a.get_data_parts_from_message(message)

        for data_part in data_parts:
            # Check if this DataPart contains a structured_invocation_request
            data = data_part.data if hasattr(data_part, "data") else None
            if not data or not isinstance(data, dict):
                continue

            if data.get("type") != "structured_invocation_request":
                continue

            # Found it - parse and return
            try:
                invocation_data = StructuredInvocationRequest.model_validate(data)
                return invocation_data
            except ValidationError as e:
                log.error(f"{self.host.log_identifier} Invalid structured invocation request data: {e}")
                return None

        return None

    async def execute_structured_invocation(
        self,
        message: A2AMessage,
        invocation_data: StructuredInvocationRequest,
        a2a_context: Dict[str, Any],
        original_solace_message: Any = None,
    ):
        """Execute agent as a structured invocation with schema validation."""
        log_id = f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}]"

        log.debug(
            f"{log_id} Received structured invocation request. Context: {invocation_data.workflow_name}, "
            f"node_id: {invocation_data.node_id}, suggested_output_filename: {invocation_data.suggested_output_filename}"
        )

        try:
            # Determine effective schemas
            input_schema = invocation_data.input_schema or self.input_schema
            output_schema = invocation_data.output_schema or self.output_schema

            # Default input schema to single text field if not provided
            if not input_schema:
                input_schema = {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                }
                log.debug(
                    f"{log_id} No input schema provided, using default text schema"
                )

            # Validate input against schema
            validation_errors = await self._validate_input(
                message, input_schema, a2a_context, log_id
            )

            if validation_errors:
                log.error(f"{log_id} Input validation failed: {validation_errors}")

                # Return validation error immediately
                result_data = StructuredInvocationResult(
                    type="structured_invocation_result",
                    status="error",
                    error_message=f"Input validation failed: {validation_errors}",
                )
                return await self._return_structured_result(
                    invocation_data, result_data, a2a_context
                )

            # Input valid, proceed with execution
            return await self._execute_with_output_validation(
                message,
                invocation_data,
                output_schema,
                a2a_context,
                original_solace_message,
            )

        except Exception as e:
            # Catch any unhandled exceptions and return as structured invocation failure
            log.warning(f"{log_id} Structured invocation execution failed: {e}", exc_info=True)

            result_data = StructuredInvocationResult(
                type="structured_invocation_result",
                status="error",
                error_message=f"Node execution error: {str(e)}",
            )
            return await self._return_structured_result(
                invocation_data, result_data, a2a_context
            )

    async def _validate_input(
        self,
        message: A2AMessage,
        input_schema: Dict[str, Any],
        a2a_context: Dict[str, Any],
        log_id: str = "",
    ) -> Optional[List[str]]:
        """
        Validate message content against input schema.
        Returns list of validation errors or None if valid.
        """
        from .validator import validate_against_schema

        # Extract input data from message
        input_data = await self._extract_input_data(message, input_schema, a2a_context)

        log.debug(
            f"{log_id} Resolved input data: {json.dumps(input_data, default=str)}"
        )

        # Validate against schema
        errors = validate_against_schema(input_data, input_schema)

        return errors if errors else None

    async def _extract_input_data(
        self,
        message: A2AMessage,
        input_schema: Dict[str, Any],
        a2a_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract structured input data from message parts.

        Handles two cases:
        1. Single text field schema: Aggregates all text parts into 'text' field
        2. Structured schema: Extracts from first FilePart (JSON/YAML/CSV)

        Returns:
            Validated input data dictionary
        """
        log_id = f"{self.host.log_identifier}[ExtractInput]"

        # Check if this is a single text field schema
        if self._is_single_text_schema(input_schema):
            log.debug(f"{log_id} Using single text field extraction")
            return await self._extract_text_input(message)

        # Otherwise, extract from FilePart
        log.debug(f"{log_id} Using structured FilePart extraction")
        return await self._extract_file_input(message, input_schema, a2a_context)

    def _is_single_text_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Check if schema represents a single text field.
        Returns True if schema has exactly one property named 'text' of type 'string'.
        """
        if schema.get("type") != "object":
            return False

        properties = schema.get("properties", {})
        if len(properties) != 1:
            return False

        if "text" not in properties:
            return False

        return properties["text"].get("type") == "string"

    async def _extract_text_input(self, message: A2AMessage) -> Dict[str, Any]:
        """
        Extract text input by aggregating all text parts.
        Returns: {"text": "<aggregated_text>"}
        """
        unwrapped_parts = [p.root for p in message.parts]
        text_parts = []

        for part in unwrapped_parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        aggregated_text = "\n".join(text_parts) if text_parts else ""
        return {"text": aggregated_text}

    async def _extract_file_input(
        self,
        message: A2AMessage,
        input_schema: Dict[str, Any],
        a2a_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract input data from first FilePart in message.
        Handles both inline bytes and URI references.
        """
        log_id = f"{self.host.log_identifier}[ExtractFile]"

        # Find first FilePart
        file_parts = a2a.get_file_parts_from_message(message)

        if not file_parts:
            raise ValueError("No FilePart found in message for structured schema")

        file_part = file_parts[0]

        # Determine if this is bytes or URI
        if a2a.is_file_part_bytes(file_part):
            log.debug(f"{log_id} Processing FileWithBytes")
            return await self._process_file_with_bytes(
                file_part, input_schema, a2a_context
            )
        elif a2a.is_file_part_uri(file_part):
            log.debug(f"{log_id} Processing FileWithUri")
            return await self._process_file_with_uri(file_part, a2a_context)
        else:
            raise ValueError(f"Unknown FilePart type: {type(file_part)}")

    async def _process_file_with_bytes(
        self,
        file_part: FilePart,
        input_schema: Dict[str, Any],
        a2a_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process inline file bytes: decode, validate, and save to artifact store.
        """
        log_id = f"{self.host.log_identifier}[ProcessBytes]"

        # Decode bytes according to MIME type
        mime_type = a2a.get_mimetype_from_file_part(file_part)
        content_bytes = a2a.get_bytes_from_file_part(file_part)

        if content_bytes is None:
            raise ValueError("FilePart has no content bytes")

        data = self._decode_file_bytes(content_bytes, mime_type)

        log.debug(f"{log_id} Decoded {mime_type} file data")

        # Save to artifact store with appropriate name
        artifact_name = self._generate_input_artifact_name(mime_type)

        # Use helper to save artifact
        from ....agent.utils.artifact_helpers import save_artifact_with_metadata

        await save_artifact_with_metadata(
            artifact_service=self.host.artifact_service,
            app_name=self.host.agent_name,
            user_id=a2a_context["user_id"],
            session_id=a2a_context["effective_session_id"],
            filename=artifact_name,
            content_bytes=content_bytes,
            mime_type=mime_type,
            metadata_dict={"source": "workflow_input"},
            timestamp=datetime.now(timezone.utc),
        )

        log.info(f"{log_id} Saved input data to artifact: {artifact_name}")

        return data

    async def _process_file_with_uri(
        self, file_part: FilePart, a2a_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process file URI: load artifact and decode.
        """
        log_id = f"{self.host.log_identifier}[ProcessURI]"

        # Parse URI to extract artifact name and version
        uri = a2a.get_uri_from_file_part(file_part)
        if not uri:
            raise ValueError("FilePart has no URI")

        try:
            uri_parts = parse_artifact_uri(uri)
        except ValueError as e:
            raise ValueError(f"Invalid artifact URI: {e}")

        log.debug(f"{log_id} Loading artifact from URI: {uri}")

        # Load artifact using the context from the URI (app_name, user_id, session_id)
        # This ensures we can read artifacts created by the workflow orchestrator
        artifact = await self.host.artifact_service.load_artifact(
            app_name=uri_parts["app_name"],
            user_id=uri_parts["user_id"],
            session_id=uri_parts["session_id"],
            filename=uri_parts["filename"],
            version=uri_parts["version"],
        )

        if not artifact or not artifact.inline_data:
            raise ValueError(
                f"Artifact not found or has no data: {uri_parts['filename']}"
            )

        # Decode artifact data
        mime_type = artifact.inline_data.mime_type
        data = self._decode_file_bytes(artifact.inline_data.data, mime_type)

        log.info(f"{log_id} Loaded and decoded artifact: {uri_parts['filename']}")

        return data

    def _decode_file_bytes(self, data: bytes, mime_type: str) -> Dict[str, Any]:
        """
        Decode file bytes according to MIME type.
        Supports: application/json, application/yaml, text/yaml, text/csv
        """
        log_id = f"{self.host.log_identifier}[Decode]"

        if mime_type in ["application/json", "text/json"]:
            return json.loads(data.decode("utf-8"))

        elif mime_type in ["application/yaml", "text/yaml", "application/x-yaml"]:
            return yaml.safe_load(data.decode("utf-8"))

        elif mime_type in ["text/csv", "application/csv"]:
            # CSV to dict list
            csv_text = data.decode("utf-8")
            reader = csv.DictReader(io.StringIO(csv_text))
            return {"rows": list(reader)}

        else:
            raise ValueError(f"Unsupported MIME type for input data: {mime_type}")

    def _generate_input_artifact_name(self, mime_type: str) -> str:
        """
        Generate artifact name for input data based on MIME type.
        Format: {agent-name}_input_data.{ext}
        """
        ext_map = {
            "application/json": "json",
            "text/json": "json",
            "application/yaml": "yaml",
            "text/yaml": "yaml",
            "application/x-yaml": "yaml",
            "text/csv": "csv",
            "application/csv": "csv",
        }

        extension = ext_map.get(mime_type, "dat")
        return f"{self.host.agent_name}_input_data.{extension}"

    async def _execute_with_output_validation(
        self,
        message: A2AMessage,
        invocation_data: StructuredInvocationRequest,
        output_schema: Optional[Dict[str, Any]],
        a2a_context: Dict[str, Any],
        original_solace_message: Any = None,
    ):
        """Execute agent with output validation and retry logic."""
        log_id = f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}]"

        # Create callback for instruction injection
        workflow_callback = self._create_workflow_callback(invocation_data, output_schema)

        # We need to register this callback with the agent.
        # Since SamAgentComponent manages the agent lifecycle, we need a way to inject this.
        # SamAgentComponent supports `_agent_system_instruction_callback`.
        # We can temporarily override it or chain it.

        original_callback = self.host._agent_system_instruction_callback

        def chained_callback(context, request):
            # Call original if exists
            original_instr = (
                original_callback(context, request) if original_callback else None
            )
            # Call workflow callback
            workflow_instr = workflow_callback(context, request)

            parts = []
            if original_instr:
                parts.append(original_instr)
            if workflow_instr:
                parts.append(workflow_instr)
            return "\n\n".join(parts) if parts else None

        self.host.set_agent_system_instruction_callback(chained_callback)

        # Import TaskExecutionContext
        from ..task_execution_context import TaskExecutionContext

        logical_task_id = a2a_context.get("logical_task_id")

        # Create and register TaskExecutionContext for this structured invocation
        task_context = TaskExecutionContext(
            task_id=logical_task_id, a2a_context=a2a_context
        )

        # Store the original Solace message if provided
        # Note: original_solace_message is passed as a parameter, not stored in a2a_context,
        # to avoid serialization issues when a2a_context is stored in ADK session state
        if original_solace_message:
            task_context.set_original_solace_message(original_solace_message)

        # Register the task context
        with self.host.active_tasks_lock:
            self.host.active_tasks[logical_task_id] = task_context

        log.debug(
            f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] Created TaskExecutionContext for task {logical_task_id}"
        )

        try:
            # Execute agent (existing ADK execution path)
            # We need to trigger the standard handle_a2a_request logic but intercept the result.
            # However, handle_a2a_request is designed to run the agent and return.
            # It calls `run_adk_async_task_thread_wrapper`.
            # We can call that directly.

            # Prepare ADK content
            user_id = a2a_context.get("user_id")
            # For structured invocations, create a run-based session ID following the same pattern
            # as RUN_BASED A2A requests: {original_session_id}:{logical_task_id}:run
            # This ensures:
            # 1. Each invocation starts with a fresh session (RUN_BASED behavior)
            # 2. get_original_session_id() can extract the parent session for artifact sharing
            original_session_id = a2a_context.get("session_id")
            logical_task_id = a2a_context.get("logical_task_id")
            session_id = f"{original_session_id}:{logical_task_id}:run"

            adk_content = await a2a.translate_a2a_to_adk_content(
                a2a_message=message,
                component=self.host,
                user_id=user_id,
                session_id=session_id,
            )

            # Always create a new session for structured invocations (RUN_BASED behavior)
            adk_session = await self.host.session_service.create_session(
                app_name=self.host.agent_name,
                user_id=user_id,
                session_id=session_id,
            )

            run_config = RunConfig(
                streaming_mode=StreamingMode.SSE,
                max_llm_calls=self.host.get_config("max_llm_calls_per_task", 20),
            )

            # Execute
            await run_adk_async_task_thread_wrapper(
                self.host,
                adk_session,
                adk_content,
                run_config,
                a2a_context,
                skip_finalization=True,  # Structured invocations do custom finalization
            )

            # After execution, we need to validate the result.
            # The result is in the session history.
            # We need to fetch the updated session.
            adk_session = await self.host.session_service.get_session(
                app_name=self.host.agent_name,
                user_id=user_id,
                session_id=session_id,
            )

            # Find the last model response event
            # The session might end with a tool response (e.g. _notify_artifact_save) if the model
            # outputs nothing in the final turn. We scan backwards for the text output.
            last_model_event = None
            if adk_session.events:
                for i, event in enumerate(reversed(adk_session.events)):
                    if event.content and event.content.role == "model":
                        last_model_event = event
                        log.debug(f"{log_id} Found last model event at index -{i+1}: {event.id}")
                        break

            if not last_model_event:
                log.warning(f"{log_id} No model event found in session history.")

            result_data = await self._finalize_structured_invocation(
                adk_session, last_model_event, invocation_data, output_schema, retry_count=0
            )

            log.debug(
                f"{log_id} Final result data: {result_data.model_dump_json()}"
            )

            # Send result back to workflow
            await self._return_structured_result(invocation_data, result_data, a2a_context)

        finally:
            # Clean up task context
            with self.host.active_tasks_lock:
                if logical_task_id in self.host.active_tasks:
                    del self.host.active_tasks[logical_task_id]
                    log.debug(
                        f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] Removed TaskExecutionContext for task {logical_task_id}"
                    )

            # Restore original callback
            self.host.set_agent_system_instruction_callback(original_callback)

    def _create_workflow_callback(
        self,
        invocation_data: StructuredInvocationRequest,
        output_schema: Optional[Dict[str, Any]],
    ) -> Callable:
        """Create callback for workflow instruction injection."""

        def inject_instructions(
            callback_context: CallbackContext, llm_request: LlmRequest
        ) -> Optional[str]:
            return self._generate_workflow_instructions(invocation_data, output_schema)

        return inject_instructions

    def _generate_workflow_instructions(
        self,
        invocation_data: StructuredInvocationRequest,
        output_schema: Optional[Dict[str, Any]],
    ) -> str:
        """Generate workflow-specific instructions."""

        workflow_instructions = f"""

=== WORKFLOW EXECUTION CONTEXT ===
You are executing as node '{invocation_data.node_id}' in workflow '{invocation_data.workflow_name}'.
"""

        # Add required output filename if provided
        if invocation_data.suggested_output_filename:
            workflow_instructions += f"""
=== REQUIRED OUTPUT ARTIFACT FILENAME ===
You MUST save your output artifact with this exact filename:
{invocation_data.suggested_output_filename}

When you complete this task, use: «result:artifact={invocation_data.suggested_output_filename} status=success»
"""

        # Add output schema requirement if present
        if output_schema:
            workflow_instructions += f"""

=== CRITICAL: REQUIRED OUTPUT FORMAT ===
You MUST follow these steps to complete this task:

1. Create an artifact containing your result data conforming to this JSON Schema:

{json.dumps(output_schema, indent=2)}

2. MANDATORY: End your response with the result embed marking your output artifact:
   «result:artifact=<artifact_name> status=success»

   Example: «result:artifact=customer_data.json status=success»

   IMPORTANT: Do NOT include a version number if returning the latest version - the system will automatically provide the most recent version.

3. The artifact MUST strictly conform to the provided schema. Your output will be validated.
   If validation fails, you will be asked to retry with error feedback.

IMPORTANT NOTES:
- Use the save_artifact tool OR inline fenced blocks to create the output artifact
- The result embed («result:artifact=...») is MANDATORY - the invocation will fail without it
- The artifact format (JSON, YAML, etc.) must be parseable
- Additional fields beyond the schema are allowed, but all required fields must be present

FAILURE TO INCLUDE THE RESULT EMBED WILL CAUSE THE INVOCATION TO FAIL.
"""
        else:
            # No output schema, just mark result
            workflow_instructions += """

=== CRITICAL: REQUIRED OUTPUT FORMAT ===
You MUST end your response with the result embed to mark your completion:

«result:artifact=<artifact_name> status=success»

This result embed is MANDATORY. The invocation cannot proceed without it.

   IMPORTANT: Do NOT include a version number if returning the latest version - the system will automatically provide the most recent version.

If you cannot complete the task, use:
«result:artifact=<artifact_name> status=error message="<reason>"»
"""
        return workflow_instructions.strip()

    async def _finalize_structured_invocation(
        self,
        session,
        last_event: ADKEvent,
        invocation_data: StructuredInvocationRequest,
        output_schema: Optional[Dict[str, Any]],
        retry_count: int = 0,
    ) -> StructuredInvocationResult:
        """
        Finalize structured invocation with output validation.
        Handles retry on validation failure or missing result embed.
        """
        log_id = f"{self.host.log_identifier}[Node:{invocation_data.node_id}]"

        # 1. Parse result embed from agent output
        result_embed = self._parse_result_embed(last_event)

        if not result_embed:
            error_msg = "Agent did not output the mandatory result embed: «result:artifact=... status=success»"
            log.warning(f"{log_id} {error_msg}")

            if retry_count < self.max_validation_retries:
                log.info(f"{log_id} Retrying due to missing result embed (Attempt {retry_count + 1})")
                feedback_text = f"""
ERROR: You failed to provide the mandatory result embed in your response.
You MUST end your response with:
«result:artifact=<your_artifact_name>:<version> status=success»

Please retry and ensure you include this embed.
"""
                return await self._execute_retry_loop(
                    session,
                    invocation_data,
                    output_schema,
                    feedback_text,
                    retry_count + 1,
                )
            else:
                return StructuredInvocationResult(
                    type="structured_invocation_result",
                    status="error",
                    error_message=error_msg,
                    retry_count=retry_count,
                )

        # Handle explicit failure status
        if result_embed.status == "error":
            return StructuredInvocationResult(
                type="structured_invocation_result",
                status="error",
                error_message=result_embed.message or "Agent reported failure",
                output_artifact_ref=ArtifactRef(name=result_embed.artifact_name) if result_embed.artifact_name else None,
                retry_count=retry_count,
            )

        # 2. Load artifact from artifact service
        try:
            # If version is missing, query for latest version
            version = int(result_embed.version) if result_embed.version else None

            if version is None:
                # Use original session ID to query for versions (same as when artifacts were saved)
                from ....agent.utils.context_helpers import get_original_session_id
                original_session_id_for_versions = get_original_session_id(session.id)

                # Query for the latest version
                versions = await self.host.artifact_service.list_versions(
                    app_name=self.host.agent_name,
                    user_id=session.user_id,
                    session_id=original_session_id_for_versions,
                    filename=result_embed.artifact_name,
                )
                if versions:
                    version = max(versions)
                    log.debug(
                        f"{log_id} Resolved latest version for {result_embed.artifact_name}: v{version}"
                    )
                else:
                    log.error(
                        f"{log_id} No versions found for artifact {result_embed.artifact_name}"
                    )
                    return StructuredInvocationResult(
                        type="structured_invocation_result",
                        status="error",
                        error_message=f"Artifact {result_embed.artifact_name} not found (no versions available)",
                        retry_count=retry_count,
                    )

            # Use original session ID (without :run suffix) to load artifacts
            # This ensures we can access artifacts saved by the agent, which uses
            # get_original_session_id() to store them in the parent session scope
            from ....agent.utils.context_helpers import get_original_session_id
            original_session_id = get_original_session_id(session.id)

            artifact = await self.host.artifact_service.load_artifact(
                app_name=self.host.agent_name,
                user_id=session.user_id,
                session_id=original_session_id,
                filename=result_embed.artifact_name,
                version=version,
            )
        except Exception as e:
            log.error(f"{log_id} Failed to load artifact: {e}")
            return StructuredInvocationResult(
                type="structured_invocation_result",
                status="error",
                error_message=f"Failed to load result artifact: {e}",
                retry_count=retry_count,
            )

        # 3. Validate artifact against output schema
        if output_schema:
            validation_errors = self._validate_artifact(artifact, output_schema)

            if validation_errors:
                log.warning(f"{log_id} Output validation failed: {validation_errors}")

                # Check if we can retry
                if retry_count < self.max_validation_retries:
                    log.info(f"{log_id} Retrying with validation feedback (Attempt {retry_count + 1})")
                    
                    error_text = "\n".join([f"- {err}" for err in validation_errors])
                    feedback_text = f"""
Your previous output artifact failed schema validation with the following errors:

{error_text}

Please review the required schema and create a corrected artifact that addresses these errors:

{json.dumps(output_schema, indent=2)}

Remember to end your response with the result embed:
«result:artifact=<corrected_artifact_name>:<version> status=success»
"""
                    return await self._execute_retry_loop(
                        session,
                        invocation_data,
                        output_schema,
                        feedback_text,
                        retry_count + 1,
                    )
                else:
                    # Max retries exceeded
                    return StructuredInvocationResult(
                        type="structured_invocation_result",
                        status="error",
                        error_message="Output validation failed after max retries",
                        validation_errors=validation_errors,
                        retry_count=retry_count,
                    )

        # 4. Validation succeeded
        return StructuredInvocationResult(
            type="structured_invocation_result",
            status="success",
            output_artifact_ref=ArtifactRef(name=result_embed.artifact_name, version=version),
            retry_count=retry_count,
        )

    def _parse_result_embed(self, adk_event: ADKEvent) -> Optional[ResultEmbed]:
        """
        Parse result embed from agent's final output.
        Format: «result:artifact=<name>:v<version> status=<success|error> message="<text>"»
        """
        if not adk_event or not adk_event.content or not adk_event.content.parts:
            log.debug("Result embed parse: Event is empty or has no content.")
            return None

        # Only parse result embeds from agent responses (role="model"), not instructions (role="user")
        # This prevents parsing example embeds from the workflow instructions
        if adk_event.content.role != "model":
            log.debug(f"Result embed parse: Event role is {adk_event.content.role}, skipping.")
            return None

        # Extract text from last event
        text_content = ""
        for part in adk_event.content.parts:
            if part.text:
                text_content += part.text

        log.debug(f"Result embed parse: Scanning text content (len={len(text_content)}): {text_content[:100]}...")

        # Parse embeds using EMBED_REGEX
        result_embeds = []
        for match in EMBED_REGEX.finditer(text_content):
            embed_type = match.group(1)
            if embed_type == "result":
                expression = match.group(2)
                result_embeds.append(expression)

        if not result_embeds:
            return None

        # Take last result embed and parse its parameters
        # Format: artifact=<name>:v<version> status=<success|error> message="<text>"
        expression = result_embeds[-1]

        # Parse parameters from expression
        params = {}

        # Match key=value patterns, handling quoted values
        param_pattern = r'(\w+)=(?:"([^"]*)"|([^\s]+))'
        for param_match in re.finditer(param_pattern, expression):
            key = param_match.group(1)
            # Use quoted value if present, otherwise use unquoted
            value = (
                param_match.group(2)
                if param_match.group(2) is not None
                else param_match.group(3)
            )
            params[key] = value

        # Extract artifact name and version
        artifact_spec = params.get("artifact", "")
        artifact_name = artifact_spec
        version = None

        # Check if version is in artifact spec (e.g., "filename:v1" or "filename:1")
        if ":" in artifact_spec:
            parts = artifact_spec.split(":", 1)
            artifact_name = parts[0]
            version_str = parts[1]

            # Handle both "v1" and "1" formats
            if version_str.startswith("v"):
                version_str = version_str[1:]

            try:
                version = int(version_str)
            except (ValueError, IndexError):
                pass

        # Also check for standalone version parameter (less common)
        if version is None and "version" in params:
            try:
                version_str = params["version"]
                if version_str.startswith("v"):
                    version_str = version_str[1:]
                version = int(version_str)
            except (ValueError, TypeError):
                pass

        # Validate: must have artifact OR explicit error status
        status = params.get("status", "success")
        if not artifact_name and status != "error":
            log.debug(
                "Result embed parse: Malformed embed - no artifact and no explicit error status"
            )
            return None

        return ResultEmbed(
            artifact_name=artifact_name,
            version=version,
            status=status,
            message=params.get("message"),
        )

    def _validate_artifact(
        self, artifact_part: adk_types.Part, schema: Dict[str, Any]
    ) -> Optional[List[str]]:
        """Validate artifact content against schema."""
        from .validator import validate_against_schema

        if not artifact_part:
            return ["Artifact is None"]

        if not artifact_part.inline_data:
            return ["Artifact has no inline data"]

        try:
            data = json.loads(artifact_part.inline_data.data.decode("utf-8"))
            return validate_against_schema(data, schema)
        except json.JSONDecodeError:
            return ["Artifact content is not valid JSON"]
        except Exception as e:
            return [f"Error validating artifact: {e}"]

    async def _execute_retry_loop(
        self,
        session,
        invocation_data: StructuredInvocationRequest,
        output_schema: Optional[Dict[str, Any]],
        feedback_text: str,
        retry_count: int,
    ) -> StructuredInvocationResult:
        """
        Execute a retry loop: append feedback, run agent, and validate result.
        """
        log_id = f"{self.host.log_identifier}[Node:{invocation_data.node_id}]"
        log.info(f"{log_id} Executing retry loop {retry_count}/{self.max_validation_retries}")

        # 1. Prepare feedback content
        feedback_content = adk_types.Content(
            role="user",
            parts=[adk_types.Part(text=feedback_text)],
        )

        # 2. Re-run the agent
        # We need to reconstruct the context needed for execution.
        # We need the original a2a_context to pass through.
        # Since we don't have it passed in here, we need to retrieve it from the active task context.
        # The session ID contains the logical_task_id: {original}:{logical}:run
        
        try:
            parts = session.id.split(":")
            if len(parts) >= 3 and parts[-1] == "run":
                logical_task_id = parts[-2]
            else:
                # Fallback or error
                log.error(f"{log_id} Could not extract logical_task_id from session ID {session.id}. Cannot retry.")
                return StructuredInvocationResult(
                    type="structured_invocation_result",
                    status="error",
                    error_message="Internal error: Lost task context during retry",
                    retry_count=retry_count
                )

            with self.host.active_tasks_lock:
                task_context = self.host.active_tasks.get(logical_task_id)
            
            if not task_context:
                log.error(f"{log_id} TaskExecutionContext not found for {logical_task_id}. Cannot retry.")
                return StructuredInvocationResult(
                    type="structured_invocation_result",
                    status="error",
                    error_message="Internal error: Task context lost during retry",
                    retry_count=retry_count
                )
                
            a2a_context = task_context.a2a_context

            # Prepare run config
            run_config = RunConfig(
                streaming_mode=StreamingMode.SSE,
                max_llm_calls=self.host.get_config("max_llm_calls_per_task", 20),
            )

            # Run the agent again with the feedback content
            # The runner will handle appending the event to the session
            await run_adk_async_task_thread_wrapper(
                self.host,
                session,
                feedback_content,
                run_config,
                a2a_context,
                skip_finalization=True,
                append_context_event=False # Context already set
            )

            # 3. Fetch updated session and validate new result
            updated_session = await self.host.session_service.get_session(
                app_name=self.host.agent_name,
                user_id=session.user_id,
                session_id=session.id,
            )

            # Find the new last model event
            last_model_event = None
            if updated_session.events:
                for i, event in enumerate(reversed(updated_session.events)):
                    if event.content and event.content.role == "model":
                        last_model_event = event
                        break
            
            if not last_model_event:
                log.warning(f"{log_id} No model response in retry turn.")
                # This will trigger another retry if count allows, via _finalize...

            # Recursively call finalize to validate the new output
            return await self._finalize_structured_invocation(
                updated_session, 
                last_model_event, 
                invocation_data, 
                output_schema, 
                retry_count
            )

        except Exception as e:
            log.exception(f"{log_id} Error during retry execution: {e}")
            return StructuredInvocationResult(
                type="structured_invocation_result",
                status="error",
                error_message=f"Retry execution failed: {e}",
                retry_count=retry_count
            )

    async def _return_structured_result(
        self,
        invocation_data: StructuredInvocationRequest,
        result_data: StructuredInvocationResult,
        a2a_context: Dict[str, Any],
    ):
        """Return structured invocation result to the caller."""
        try:
            # Create message with result data part
            result_message = a2a.create_agent_parts_message(
                parts=[a2a.create_data_part(data=result_data.model_dump())],
                task_id=a2a_context["logical_task_id"],
                context_id=a2a_context["session_id"],
            )

            # Create task status
            task_state = (
                TaskState.completed
                if result_data.status == "success"
                else TaskState.failed
            )
            task_status = a2a.create_task_status(
                state=task_state, message=result_message
            )

            # Create final task
            final_task = a2a.create_final_task(
                task_id=a2a_context["logical_task_id"],
                context_id=a2a_context["session_id"],
                final_status=task_status,
                metadata={
                    "agent_name": self.host.agent_name,
                    "workflow_node_id": invocation_data.node_id,
                    "workflow_name": invocation_data.workflow_name,
                },
            )

            # Create JSON-RPC response
            response = a2a.create_success_response(
                result=final_task, request_id=a2a_context["jsonrpc_request_id"]
            )

            # Publish to workflow's response topic
            response_topic = a2a_context.get("replyToTopic")

            # DEBUG: Log task ID when agent returns result to caller
            log.debug(
                f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] "
                f"Returning structured invocation result to caller | "
                f"sub_task_id={a2a_context['logical_task_id']} | "
                f"jsonrpc_request_id={a2a_context['jsonrpc_request_id']} | "
                f"result_status={result_data.status} | "
                f"response_topic={response_topic} | "
                f"workflow_name={invocation_data.workflow_name} | "
                f"node_id={invocation_data.node_id}"
            )

            if not response_topic:
                log.error(
                    f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] "
                    f"No replyToTopic in a2a_context! Cannot send structured invocation result. "
                    f"a2a_context keys: {list(a2a_context.keys())}"
                )
                # Still ACK the message to avoid redelivery
                # Retrieve from TaskExecutionContext
                logical_task_id = a2a_context.get("logical_task_id")
                with self.host.active_tasks_lock:
                    task_context = self.host.active_tasks.get(logical_task_id)
                    if task_context:
                        original_message = task_context.get_original_solace_message()
                        if original_message:
                            original_message.call_acknowledgements()
                return

            log.info(
                f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] "
                f"Publishing structured invocation result (status={result_data.status}) to {response_topic}"
            )

            self.host.publish_a2a_message(
                payload=response.model_dump(exclude_none=True),
                topic=response_topic,
                user_properties={"a2aUserConfig": a2a_context.get("a2a_user_config")},
            )

            # ACK original message
            # Retrieve from TaskExecutionContext
            logical_task_id = a2a_context.get("logical_task_id")
            with self.host.active_tasks_lock:
                task_context = self.host.active_tasks.get(logical_task_id)
                if task_context:
                    original_message = task_context.get_original_solace_message()
                    if original_message:
                        original_message.call_acknowledgements()

        except Exception as e:
            log.error(
                f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] "
                f"CRITICAL: Failed to return structured invocation result to caller: {e}",
                exc_info=True,
            )
            # Try to ACK message even on error to avoid redelivery loop
            try:
                # Retrieve from TaskExecutionContext
                logical_task_id = a2a_context.get("logical_task_id")
                with self.host.active_tasks_lock:
                    task_context = self.host.active_tasks.get(logical_task_id)
                    if task_context:
                        original_message = task_context.get_original_solace_message()
                        if original_message:
                            original_message.call_acknowledgements()
            except Exception as ack_e:
                log.error(
                    f"{self.host.log_identifier}[StructuredInvocation:{invocation_data.node_id}] "
                    f"Failed to ACK message after error: {ack_e}"
                )
