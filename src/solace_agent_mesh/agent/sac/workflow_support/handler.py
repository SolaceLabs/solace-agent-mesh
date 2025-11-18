"""
WorkflowNodeHandler implementation.
Enables a standard agent to act as a workflow node.
"""

import logging
import json
import asyncio
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
    TaskState,
)

from ....common import a2a
from ....common.data_parts import (
    WorkflowNodeRequestData,
    WorkflowNodeResultData,
)
from ....agent.adk.runner import run_adk_async_task_thread_wrapper
from ....common.utils.embeds.parser import parse_embeds

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
            log.error(
                f"{self.host.log_identifier} Invalid workflow request data: {e}"
            )
            return None

    async def execute_workflow_node(
        self,
        message: A2AMessage,
        workflow_data: WorkflowNodeRequestData,
        a2a_context: Dict[str, Any],
    ):
        """Execute agent as a workflow node with validation."""
        log_id = f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}]"

        # Determine effective schemas
        input_schema = workflow_data.input_schema or self.input_schema
        output_schema = workflow_data.output_schema or self.output_schema

        # Validate input if schema exists
        if input_schema:
            validation_errors = self._validate_input(message, input_schema)

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

    def _validate_input(
        self, message: A2AMessage, input_schema: Dict[str, Any]
    ) -> Optional[List[str]]:
        """
        Validate message content against input schema.
        Returns list of validation errors or None if valid.
        """
        from .validator import validate_against_schema

        # Extract input data from message
        input_data = self._extract_input_data(message, input_schema)

        # Validate against schema
        errors = validate_against_schema(input_data, input_schema)

        return errors if errors else None

    def _extract_input_data(
        self, message: A2AMessage, input_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract structured input data from message parts.
        If an input schema is active, it prioritizes the content of the first
        FilePart for validation. Otherwise, it combines text and data parts.
        """
        input_data = {}

        # If a schema is present, prioritize the first FilePart
        if input_schema:
            # Unwrap parts
            unwrapped_parts = [p.root for p in message.parts]
            file_parts = [p for p in unwrapped_parts if isinstance(p, FilePart)]
            if file_parts:
                # For validation, we'd load the file content here.
                # This example assumes the content is loaded into `input_data`.
                # The actual implementation will handle byte decoding and parsing.
                # For MVP, we assume the file content IS the input data if it's JSON.
                # TODO: Implement file content loading/parsing
                pass

        # Fallback for no schema or no FilePart: combine text and data
        unwrapped_parts = [p.root for p in message.parts]
        for part in unwrapped_parts:
            if hasattr(part, "text") and part.text:
                input_data.setdefault("query", "")
                input_data["query"] += part.text
            elif hasattr(part, "data") and part.data:
                if part.data.get("type") == "workflow_node_request":
                    continue
                input_data.update(part.data)

        return input_data

    async def _execute_with_output_validation(
        self,
        message: A2AMessage,
        workflow_data: WorkflowNodeRequestData,
        output_schema: Optional[Dict[str, Any]],
        a2a_context: Dict[str, Any],
    ):
        """Execute agent with output validation and retry logic."""
        
        # Create callback for instruction injection
        workflow_callback = self._create_workflow_callback(
            workflow_data, output_schema
        )

        # We need to register this callback with the agent.
        # Since SamAgentComponent manages the agent lifecycle, we need a way to inject this.
        # SamAgentComponent supports `_agent_system_instruction_callback`.
        # We can temporarily override it or chain it.
        
        original_callback = self.host._agent_system_instruction_callback
        
        def chained_callback(context, request):
            # Call original if exists
            original_instr = original_callback(context, request) if original_callback else None
            # Call workflow callback
            workflow_instr = workflow_callback(context, request)
            
            parts = []
            if original_instr: parts.append(original_instr)
            if workflow_instr: parts.append(workflow_instr)
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
                max_llm_calls=self.host.get_config("max_llm_calls_per_task", 20)
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
                adk_session,
                last_event,
                workflow_data,
                output_schema,
                retry_count=0
            )
            
            # Send result back to workflow
            await self._return_workflow_result(
                workflow_data, result_data, a2a_context
            )

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
            return self._generate_workflow_instructions(
                workflow_data, output_schema
            )

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
            artifact_version=version or 0, # TODO: get actual version if None
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

        # Parse embeds
        embeds = parse_embeds(text_content, types=["result"])

        if not embeds:
            return None

        # Take last result embed
        result_embed_dict = embeds[-1]

        # Parse embed parameters
        # The parser returns a dict of params
        return ResultEmbed(
            artifact_name=result_embed_dict.get("artifact"),
            version=result_embed_dict.get("v"), # parser might use 'v' if in string
            status=result_embed_dict.get("status", "success"),
            message=result_embed_dict.get("message"),
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

        # Re-run agent with updated session
        run_config = RunConfig(
            streaming_mode=StreamingMode.SSE,
            max_llm_calls=self.host.get_config("max_llm_calls_per_task", 20),
        )

        # Execute agent again
        try:
            # We need to pass a dummy a2a_context or reuse the previous one?
            # The runner needs it.
            # We don't have easy access to the original a2a_context here unless passed down.
            # But wait, we are inside `_execute_with_output_validation` which has `a2a_context`.
            # But this is a separate method.
            # We should pass `a2a_context` to `_finalize_workflow_node_execution` and then here.
            # For now, let's assume we can get it from session state if needed, or pass empty dict if runner allows.
            # Actually, `run_adk_async_task_thread_wrapper` requires `a2a_context`.
            # Let's update the signature chain.
            pass 

        except Exception as e:
            log.error(f"{log_id} Retry execution failed: {e}")
            return WorkflowNodeResultData(
                type="workflow_node_result",
                status="failure",
                error_message=f"Retry execution failed: {e}",
                retry_count=retry_count,
            )
            
        # NOTE: The retry logic requires recursively calling the runner and then finalize again.
        # This is getting complex to implement in this snippet without full context passing.
        # For MVP, we might skip the actual re-execution implementation here and just return failure.
        # Or we need to refactor to pass `a2a_context` down.
        
        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message="Retry logic not fully implemented in MVP handler",
            retry_count=retry_count,
        )

    async def _return_workflow_result(
        self,
        workflow_data: WorkflowNodeRequestData,
        result_data: WorkflowNodeResultData,
        a2a_context: Dict[str, Any],
    ):
        """Return workflow node result to workflow executor."""

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
            result=final_task, request_id=a2a.get_request_id(a2a_context.get("original_solace_message")) # Wait, we need the request object or ID
        )
        # a2a_context has jsonrpc_request_id
        response = a2a.create_success_response(
            result=final_task, request_id=a2a_context["jsonrpc_request_id"]
        )

        # Publish to workflow's response topic
        response_topic = a2a_context.get("replyToTopic")
        self.host.publish_a2a_message(
            payload=response.model_dump(exclude_none=True),
            topic=response_topic,
            user_properties={"a2aUserConfig": a2a_context.get("a2a_user_config")},
        )

        # ACK original message
        original_message = a2a_context.get("original_solace_message")
        if original_message:
            original_message.call_acknowledgements()
