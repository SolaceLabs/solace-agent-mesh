"""
WorkflowNodeHandler implementation.
Enables a standard agent to act as a workflow node.
"""

import logging
import json
import asyncio
import re
import yaml
import csv
import io
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
    WorkflowNodeRequestData,
    WorkflowNodeResultData,
)
from ....agent.adk.runner import run_adk_async_task_thread_wrapper
from ....common.utils.embeds.constants import EMBED_REGEX

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


class WorkflowNodeHandler:
    """
    Handles workflow-specific logic for an agent.
    """

    def __init__(self, host_component: "SamAgentComponent"):
        self.host = host_component
        self.input_schema = host_component.get_config("input_schema")
        self.output_schema = host_component.get_config("output_schema")
        self.max_validation_retries = host_component.get_config(
            "validation_max_retries", 2
        )

    def extract_workflow_context(
        self, message: A2AMessage
    ) -> Optional[WorkflowNodeRequestData]:
        """
        Extract workflow context from message if present.
        Workflow messages contain WorkflowNodeRequestData as first DataPart.
        """
        if not message.parts:
            return None

        # Check first part for workflow data
        # Note: A2AMessage parts are wrapped in Part(root=...)
        first_part_wrapper = message.parts[0]
        first_part = first_part_wrapper.root

        if not hasattr(first_part, "data") or not first_part.data:
            return None

        # Check for workflow_node_request type
        if first_part.data.get("type") != "workflow_node_request":
            return None

        # Parse workflow request data
        try:
            workflow_data = WorkflowNodeRequestData.model_validate(first_part.data)
            return workflow_data
        except ValidationError as e:
            log.error(f"{self.host.log_identifier} Invalid workflow request data: {e}")
            return None

    async def execute_workflow_node(
        self,
        message: A2AMessage,
        workflow_data: WorkflowNodeRequestData,
        a2a_context: Dict[str, Any],
    ):
        """Execute agent as a workflow node with validation."""
        log_id = f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}]"

        try:
            # Determine effective schemas
            input_schema = workflow_data.input_schema or self.input_schema
            output_schema = workflow_data.output_schema or self.output_schema

            # Default input schema to single text field if not provided
            if not input_schema:
                input_schema = {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"}
                    },
                    "required": ["text"]
                }
                log.debug(f"{log_id} No input schema provided, using default text schema")

            # Validate input if schema exists
            if input_schema:
                validation_errors = await self._validate_input(message, input_schema, a2a_context)

                if validation_errors:
                    log.error(f"{log_id} Input validation failed: {validation_errors}")

                    # Return validation error immediately
                    result_data = WorkflowNodeResultData(
                        type="workflow_node_result",
                        status="failure",
                        error_message=f"Input validation failed: {validation_errors}",
                    )
                    return await self._return_workflow_result(
                        workflow_data, result_data, a2a_context
                    )

            # Input valid, proceed with execution
            return await self._execute_with_output_validation(
                message, workflow_data, output_schema, a2a_context
            )

        except Exception as e:
            # Catch any unhandled exceptions and return as workflow node failure
            log.warning(f"{log_id} Workflow node execution failed: {e}")

            result_data = WorkflowNodeResultData(
                type="workflow_node_result",
                status="failure",
                error_message=f"Node execution error: {str(e)}",
            )
            return await self._return_workflow_result(
                workflow_data, result_data, a2a_context
            )

    async def _validate_input(
        self, message: A2AMessage, input_schema: Dict[str, Any], a2a_context: Dict[str, Any]
    ) -> Optional[List[str]]:
        """
        Validate message content against input schema.
        Returns list of validation errors or None if valid.
        """
        from .validator import validate_against_schema

        # Extract input data from message
        input_data = await self._extract_input_data(message, input_schema, a2a_context)

        # Validate against schema
        errors = validate_against_schema(input_data, input_schema)

        return errors if errors else None

    async def _extract_input_data(
        self, message: A2AMessage, input_schema: Dict[str, Any], a2a_context: Dict[str, Any]
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
        self, message: A2AMessage, input_schema: Dict[str, Any], a2a_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract input data from first FilePart in message.
        Handles both inline bytes and URI references.
        """
        log_id = f"{self.host.log_identifier}[ExtractFile]"

        # Find first FilePart
        unwrapped_parts = [p.root for p in message.parts]
        file_parts = [p for p in unwrapped_parts if isinstance(p, FilePart)]

        if not file_parts:
            raise ValueError("No FilePart found in message for structured schema")

        file_part = file_parts[0]

        # Determine if this is bytes or URI
        if isinstance(file_part, FileWithBytes):
            log.debug(f"{log_id} Processing FileWithBytes")
            return await self._process_file_with_bytes(file_part, input_schema, a2a_context)
        elif isinstance(file_part, FileWithUri):
            log.debug(f"{log_id} Processing FileWithUri")
            return await self._process_file_with_uri(file_part, a2a_context)
        else:
            raise ValueError(f"Unknown FilePart type: {type(file_part)}")

    async def _process_file_with_bytes(
        self, file_part: FileWithBytes, input_schema: Dict[str, Any], a2a_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process inline file bytes: decode, validate, and save to artifact store.
        """
        log_id = f"{self.host.log_identifier}[ProcessBytes]"

        # Decode bytes according to MIME type
        mime_type = file_part.mime_type
        data = self._decode_file_bytes(file_part.data, mime_type)

        log.debug(f"{log_id} Decoded {mime_type} file data")

        # Save to artifact store with appropriate name
        artifact_name = self._generate_input_artifact_name(mime_type)

        await self.host.artifact_service.save_artifact(
            app_name=self.host.agent_name,
            user_id=a2a_context["user_id"],
            session_id=a2a_context["effective_session_id"],
            filename=artifact_name,
            data=file_part.data,
            mime_type=mime_type,
        )

        log.info(f"{log_id} Saved input data to artifact: {artifact_name}")

        return data

    async def _process_file_with_uri(
        self, file_part: FileWithUri, a2a_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process file URI: load artifact and decode.
        """
        log_id = f"{self.host.log_identifier}[ProcessURI]"

        # Parse URI to extract artifact name and version
        # Expected format: artifact://<filename>?version=<version>
        artifact_name, version = self._parse_artifact_uri(file_part.uri)

        log.debug(f"{log_id} Loading artifact: {artifact_name} v{version}")

        # Load artifact
        artifact = await self.host.artifact_service.load_artifact(
            app_name=self.host.agent_name,
            user_id=a2a_context["user_id"],
            session_id=a2a_context["effective_session_id"],
            filename=artifact_name,
            version=version,
        )

        if not artifact or not artifact.inline_data:
            raise ValueError(f"Artifact not found or has no data: {artifact_name}")

        # Decode artifact data
        mime_type = artifact.inline_data.mime_type
        data = self._decode_file_bytes(artifact.inline_data.data, mime_type)

        log.info(f"{log_id} Loaded and decoded artifact: {artifact_name}")

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

    def _parse_artifact_uri(self, uri: str) -> tuple[str, Optional[int]]:
        """
        Parse artifact URI to extract filename and version.
        Format: artifact://<filename>?version=<version>
        Returns: (filename, version)
        """
        # Remove artifact:// prefix
        if uri.startswith("artifact://"):
            uri = uri[11:]

        # Split on query params
        if "?" in uri:
            filename, query = uri.split("?", 1)
            # Parse version from query
            for param in query.split("&"):
                if param.startswith("version="):
                    version_str = param.split("=", 1)[1]
                    return filename, int(version_str)
            return filename, None

        return uri, None

    async def _execute_with_output_validation(
        self,
        message: A2AMessage,
        workflow_data: WorkflowNodeRequestData,
        output_schema: Optional[Dict[str, Any]],
        a2a_context: Dict[str, Any],
    ):
        """Execute agent with output validation and retry logic."""

        # Create callback for instruction injection
        workflow_callback = self._create_workflow_callback(workflow_data, output_schema)

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

        try:
            # Execute agent (existing ADK execution path)
            # We need to trigger the standard handle_a2a_request logic but intercept the result.
            # However, handle_a2a_request is designed to run the agent and return.
            # It calls `run_adk_async_task_thread_wrapper`.
            # We can call that directly.

            # Prepare ADK content
            user_id = a2a_context.get("user_id")
            session_id = a2a_context.get("effective_session_id")

            adk_content = await a2a.translate_a2a_to_adk_content(
                a2a_message=message,
                component=self.host,
                user_id=user_id,
                session_id=session_id,
            )

            adk_session = await self.host.session_service.get_session(
                app_name=self.host.agent_name,
                user_id=user_id,
                session_id=session_id,
            )

            if not adk_session:
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
            )

            # After execution, we need to validate the result.
            # The result is in the session history.
            # We need to fetch the updated session.
            adk_session = await self.host.session_service.get_session(
                app_name=self.host.agent_name,
                user_id=user_id,
                session_id=session_id,
            )

            last_event = adk_session.events[-1] if adk_session.events else None

            result_data = await self._finalize_workflow_node_execution(
                adk_session, last_event, workflow_data, output_schema, retry_count=0
            )

            # Send result back to workflow
            await self._return_workflow_result(workflow_data, result_data, a2a_context)

        finally:
            # Restore original callback
            self.host.set_agent_system_instruction_callback(original_callback)

    def _create_workflow_callback(
        self,
        workflow_data: WorkflowNodeRequestData,
        output_schema: Optional[Dict[str, Any]],
    ) -> Callable:
        """Create callback for workflow instruction injection."""

        def inject_instructions(
            callback_context: CallbackContext, llm_request: LlmRequest
        ) -> Optional[str]:
            return self._generate_workflow_instructions(workflow_data, output_schema)

        return inject_instructions

    def _generate_workflow_instructions(
        self,
        workflow_data: WorkflowNodeRequestData,
        output_schema: Optional[Dict[str, Any]],
    ) -> str:
        """Generate workflow-specific instructions."""

        workflow_instructions = f"""

WORKFLOW EXECUTION CONTEXT:
You are executing as node '{workflow_data.node_id}' in workflow '{workflow_data.workflow_name}'.
"""

        # Add output schema requirement if present
        if output_schema:
            workflow_instructions += f"""

REQUIRED OUTPUT FORMAT:
1. Create an artifact containing your result data conforming to this JSON Schema:

{json.dumps(output_schema, indent=2)}

2. End your response with the result embed marking your output artifact:
   «result:artifact=<artifact_name>:v<version> status=success»

   Example: «result:artifact=customer_data.json:v1 status=success»

3. The artifact MUST strictly conform to the provided schema. Your output will be validated.
   If validation fails, you will be asked to retry with error feedback.

IMPORTANT:
- Use tools like save_artifact to create the output artifact
- Or ensure tool responses are saved as artifacts (automatic if size exceeds threshold)
- The artifact format (JSON, YAML, etc.) must be parseable
- Additional fields beyond the schema are allowed, but required fields must be present
"""
        else:
            # No output schema, just mark result
            workflow_instructions += """

REQUIRED OUTPUT FORMAT:
End your response with the result embed to mark your completion:
«result:artifact=<artifact_name>:v<version> status=success»

If you cannot complete the task, use:
«result:artifact=<artifact_name>:v<version> status=failure message="<reason>"»
"""
        return workflow_instructions.strip()

    async def _finalize_workflow_node_execution(
        self,
        session,
        last_event: ADKEvent,
        workflow_data: WorkflowNodeRequestData,
        output_schema: Optional[Dict[str, Any]],
        retry_count: int = 0,
    ) -> WorkflowNodeResultData:
        """
        Finalize workflow node execution with output validation.
        Handles retry on validation failure.
        """
        log_id = f"{self.host.log_identifier}[Node:{workflow_data.node_id}]"

        # 1. Parse result embed from agent output
        result_embed = self._parse_result_embed(last_event)

        if not result_embed:
            return WorkflowNodeResultData(
                type="workflow_node_result",
                status="failure",
                error_message="Agent did not output result embed",
                retry_count=retry_count,
            )

        # Handle explicit failure status
        if result_embed.status == "failure":
            return WorkflowNodeResultData(
                type="workflow_node_result",
                status="failure",
                error_message=result_embed.message or "Agent reported failure",
                artifact_name=result_embed.artifact_name,
                retry_count=retry_count,
            )

        # 2. Load artifact from artifact service
        try:
            # If version is missing, assume latest (None)
            version = int(result_embed.version) if result_embed.version else None

            artifact = await self.host.artifact_service.load_artifact(
                app_name=self.host.agent_name,
                user_id=session.user_id,
                session_id=session.id,
                filename=result_embed.artifact_name,
                version=version,
            )
        except Exception as e:
            log.error(f"{log_id} Failed to load artifact: {e}")
            return WorkflowNodeResultData(
                type="workflow_node_result",
                status="failure",
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
                    log.info(f"{log_id} Retrying with validation feedback")
                    return await self._retry_with_validation_error(
                        session,
                        workflow_data,
                        output_schema,
                        validation_errors,
                        retry_count + 1,
                    )
                else:
                    # Max retries exceeded
                    return WorkflowNodeResultData(
                        type="workflow_node_result",
                        status="failure",
                        error_message="Output validation failed after max retries",
                        validation_errors=validation_errors,
                        retry_count=retry_count,
                    )

        # 4. Validation succeeded
        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="success",
            artifact_name=result_embed.artifact_name,
            artifact_version=version or 0,  # TODO: get actual version if None
            retry_count=retry_count,
        )

    def _parse_result_embed(self, adk_event: ADKEvent) -> Optional[ResultEmbed]:
        """
        Parse result embed from agent's final output.
        Format: «result:artifact=<name>:v<version> status=<success|failure> message="<text>"»
        """
        if not adk_event.content or not adk_event.content.parts:
            return None

        # Extract text from last event
        text_content = ""
        for part in adk_event.content.parts:
            if part.text:
                text_content += part.text

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
        # Format: artifact=<name>:v<version> status=<success|failure> message="<text>"
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

        # Check if version is in artifact spec (e.g., "filename:v1")
        if ":v" in artifact_spec:
            parts = artifact_spec.split(":v")
            artifact_name = parts[0]
            try:
                version = int(parts[1])
            except (ValueError, IndexError):
                pass

        return ResultEmbed(
            artifact_name=artifact_name,
            version=version,
            status=params.get("status", "success"),
            message=params.get("message"),
        )

    def _validate_artifact(
        self, artifact_part: adk_types.Part, schema: Dict[str, Any]
    ) -> Optional[List[str]]:
        """Validate artifact content against schema."""
        from .validator import validate_against_schema

        if not artifact_part.inline_data:
            return ["Artifact has no inline data"]

        try:
            data = json.loads(artifact_part.inline_data.data.decode("utf-8"))
            return validate_against_schema(data, schema)
        except json.JSONDecodeError:
            return ["Artifact content is not valid JSON"]
        except Exception as e:
            return [f"Error validating artifact: {e}"]

    async def _retry_with_validation_error(
        self,
        session,
        workflow_data: WorkflowNodeRequestData,
        output_schema: Dict[str, Any],
        validation_errors: List[str],
        retry_count: int,
    ) -> WorkflowNodeResultData:
        """
        Retry agent execution with validation error feedback.
        Appends validation errors to session history.
        """
        log_id = f"{self.host.log_identifier}[Node:{workflow_data.node_id}]"
        log.info(f"{log_id} Retry {retry_count}/{self.max_validation_retries}")

        # Create feedback message
        error_text = "\n".join([f"- {err}" for err in validation_errors])
        feedback_content = adk_types.Content(
            role="user",
            parts=[
                adk_types.Part(
                    text=f"""
Your previous output artifact failed schema validation with the following errors:

{error_text}

Please review the required schema and create a corrected artifact that addresses these errors:

{json.dumps(output_schema, indent=2)}

Remember to end your response with the result embed:
«result:artifact=<corrected_artifact_name>:v<version> status=success»
"""
                )
            ],
        )

        # Append feedback to session
        feedback_event = ADKEvent(
            invocation_id=session.events[-1].invocation_id if session.events else None,
            author="system",
            content=feedback_content,
        )
        await self.host.session_service.append_event(session, feedback_event)

        # TODO: Implement actual retry execution logic
        # The retry logic requires:
        # 1. Re-running the agent with the updated session containing validation feedback
        # 2. Passing the original a2a_context through the call chain
        # 3. Recursively calling _finalize_workflow_node_execution to validate the new output
        #
        # For MVP, validation errors are logged and the workflow node returns failure
        # after max retries. Future enhancement should implement full retry with execution.

        log.warning(
            f"{log_id} Retry with validation error feedback is not fully implemented. "
            f"Returning failure after {retry_count} retries."
        )

        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message=f"Output validation failed after {retry_count} attempts. Retry execution not yet implemented.",
            validation_errors=validation_errors,
            retry_count=retry_count,
        )

    async def _return_workflow_result(
        self,
        workflow_data: WorkflowNodeRequestData,
        result_data: WorkflowNodeResultData,
        a2a_context: Dict[str, Any],
    ):
        """Return workflow node result to workflow executor."""
        try:
            # Create message with result data part
            result_message = a2a.create_agent_parts_message(
                parts=[a2a.create_data_part(data=result_data.model_dump())],
                task_id=a2a_context["logical_task_id"],
                context_id=a2a_context["session_id"],
            )

            # Create task status
            task_state = (
                TaskState.completed if result_data.status == "success" else TaskState.failed
            )
            task_status = a2a.create_task_status(state=task_state, message=result_message)

            # Create final task
            final_task = a2a.create_final_task(
                task_id=a2a_context["logical_task_id"],
                context_id=a2a_context["session_id"],
                final_status=task_status,
                metadata={
                    "agent_name": self.host.agent_name,
                    "workflow_node_id": workflow_data.node_id,
                    "workflow_name": workflow_data.workflow_name,
                },
            )

            # Create JSON-RPC response
            response = a2a.create_success_response(
                result=final_task, request_id=a2a_context["jsonrpc_request_id"]
            )

            # Publish to workflow's response topic
            response_topic = a2a_context.get("replyToTopic")

            # DEBUG: Log task ID when agent returns result to workflow executor
            log.error(
                f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}] "
                f"[TASK_ID_DEBUG] AGENT returning result to WORKFLOW EXECUTOR | "
                f"sub_task_id={a2a_context['logical_task_id']} | "
                f"jsonrpc_request_id={a2a_context['jsonrpc_request_id']} | "
                f"result_status={result_data.status} | "
                f"response_topic={response_topic} | "
                f"workflow_name={workflow_data.workflow_name} | "
                f"node_id={workflow_data.node_id}"
            )

            if not response_topic:
                log.error(
                    f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}] "
                    f"No replyToTopic in a2a_context! Cannot send workflow node result. "
                    f"a2a_context keys: {list(a2a_context.keys())}"
                )
                # Still ACK the message to avoid redelivery
                original_message = a2a_context.get("original_solace_message")
                if original_message:
                    original_message.call_acknowledgements()
                return

            log.info(
                f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}] "
                f"Publishing workflow node result (status={result_data.status}) to {response_topic}"
            )

            self.host.publish_a2a_message(
                payload=response.model_dump(exclude_none=True),
                topic=response_topic,
                user_properties={"a2aUserConfig": a2a_context.get("a2a_user_config")},
            )

            # ACK original message
            original_message = a2a_context.get("original_solace_message")
            if original_message:
                original_message.call_acknowledgements()

        except Exception as e:
            log.error(
                f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}] "
                f"CRITICAL: Failed to return workflow node result to workflow executor: {e}",
                exc_info=True
            )
            # Try to ACK message even on error to avoid redelivery loop
            try:
                original_message = a2a_context.get("original_solace_message")
                if original_message:
                    original_message.call_acknowledgements()
            except Exception as ack_e:
                log.error(
                    f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}] "
                    f"Failed to ACK message after error: {ack_e}"
                )
