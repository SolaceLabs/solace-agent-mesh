"""
ADK Callbacks for the A2A Host Component.
Includes dynamic instruction injection, artifact metadata injection,
embed resolution, and logging.
"""

import logging
import json
import asyncio
import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING, List
from collections import defaultdict

from google.adk.tools import BaseTool, ToolContext
from google.adk.artifacts import BaseArtifactService
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types as adk_types
from google.adk.tools.mcp_tool import MCPTool

from .intelligent_mcp_callbacks import (
    save_mcp_response_as_artifact_intelligent,
    McpSaveStatus,
)

from ...agent.utils.artifact_helpers import (
    METADATA_SUFFIX,
    format_metadata_for_llm,
)
from ...agent.utils.context_helpers import (
    get_original_session_id,
    get_session_from_callback_context,
)
from ..tools.tool_definition import BuiltinTool

from ...common.utils.embeds import (
    EMBED_DELIMITER_OPEN,
    EMBED_DELIMITER_CLOSE,
    EMBED_CHAIN_DELIMITER,
    EARLY_EMBED_TYPES,
    evaluate_embed,
    resolve_embeds_in_string,
)
from ...common.utils.embeds.types import ResolutionMode

from ...common.utils.embeds.modifiers import MODIFIER_IMPLEMENTATIONS

from ...common import a2a
from ...common.data_parts import (
    AgentProgressUpdateData,
    ArtifactCreationProgressData,
    LlmInvocationData,
    ToolInvocationStartData,
    ToolResultData,
    TemplateBlockData,
)


METADATA_RESPONSE_KEY = "appended_artifact_metadata"
from ..tools.builtin_artifact_tools import _internal_create_artifact
from ...agent.adk.tool_wrapper import ADKToolWrapper

# Import the new parser and its events
from pydantic import BaseModel
from ...agent.adk.stream_parser import (
    FencedBlockStreamParser,
    BlockStartedEvent,
    BlockProgressedEvent,
    BlockCompletedEvent,
    BlockInvalidatedEvent,
    TemplateBlockStartedEvent,
    TemplateBlockCompletedEvent,
    ARTIFACT_BLOCK_DELIMITER_OPEN,
    ARTIFACT_BLOCK_DELIMITER_CLOSE,
)

log = logging.getLogger(__name__)

A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY = "temp:llm_stream_chunks_processed"

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent


async def _publish_data_part_status_update(
    host_component: "SamAgentComponent",
    a2a_context: Dict[str, Any],
    data_part_model: BaseModel,
):
    """Helper to construct and publish a TaskStatusUpdateEvent with a DataPart."""
    logical_task_id = a2a_context.get("logical_task_id")
    context_id = a2a_context.get("contextId")

    status_update_event = a2a.create_data_signal_event(
        task_id=logical_task_id,
        context_id=context_id,
        signal_data=data_part_model,
        agent_name=host_component.agent_name,
    )

    loop = host_component.get_async_loop()
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(
            host_component._publish_status_update_with_buffer_flush(
                status_update_event,
                a2a_context,
                skip_buffer_flush=False,
            ),
            loop,
        )
    else:
        log.error(
            "%s Async loop not available. Cannot publish status update.",
            host_component.log_identifier,
        )


async def _resolve_early_embeds_in_chunk(
    chunk: str,
    callback_context: CallbackContext,
    host_component: "SamAgentComponent",
    log_identifier: str,
) -> str:
    """
    Resolves early embeds in an artifact chunk before streaming to the browser.

    Args:
        chunk: The text chunk containing potential embeds
        callback_context: The ADK callback context with services
        host_component: The host component instance
        log_identifier: Identifier for logging

    Returns:
        The chunk with early embeds resolved
    """
    if not chunk or EMBED_DELIMITER_OPEN not in chunk:
        return chunk

    try:
        # Build resolution context from callback_context (pattern from EmbedResolvingMCPToolset)
        invocation_context = callback_context._invocation_context
        if not invocation_context:
            log.warning("%s No invocation context available for embed resolution", log_identifier)
            return chunk

        session_context = invocation_context.session
        if not session_context:
            log.warning("%s No session context available for embed resolution", log_identifier)
            return chunk

        resolution_context = {
            "artifact_service": invocation_context.artifact_service,
            "session_context": {
                "session_id": get_original_session_id(invocation_context),
                "user_id": session_context.user_id,
                "app_name": session_context.app_name,
            },
        }

        # Resolve only early embeds (math, datetime, uuid, artifact_meta)
        resolved_text, processed_until, _ = await resolve_embeds_in_string(
            text=chunk,
            context=resolution_context,
            resolver_func=evaluate_embed,
            types_to_resolve=EARLY_EMBED_TYPES,  # Only resolve early embeds
            resolution_mode=ResolutionMode.ARTIFACT_STREAMING,  # New mode
            log_identifier=log_identifier,
            config=None,  # Could pass host_component config if needed
        )

        # SAFETY CHECK: If resolver buffered something, parser has a bug
        if processed_until < len(chunk):
            log.error(
                "%s PARSER BUG DETECTED: Resolver buffered partial embed. "
                "Chunk ends with: %r. Returning unresolved chunk to avoid corruption.",
                log_identifier,
                chunk[-50:] if len(chunk) > 50 else chunk,
            )
            # Fallback: return original unresolved chunk (degraded but not corrupted)
            return chunk

        return resolved_text

    except Exception as e:
        log.error("%s Error resolving embeds in chunk: %s", log_identifier, e, exc_info=True)
        return chunk  # Return original chunk on error


async def process_artifact_blocks_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    host_component: "SamAgentComponent",
) -> Optional[LlmResponse]:
    """
    Orchestrates the parsing of fenced artifact blocks from an LLM stream
    by delegating to a FencedBlockStreamParser instance.
    This callback is stateful across streaming chunks within a single turn.
    """
    log_identifier = "[Callback:ProcessArtifactBlocks]"
    parser_state_key = "fenced_block_parser"
    session = get_session_from_callback_context(callback_context)

    parser: FencedBlockStreamParser = session.state.get(parser_state_key)
    if parser is None:
        log.debug("%s New turn. Creating new FencedBlockStreamParser.", log_identifier)
        parser = FencedBlockStreamParser(progress_update_interval_bytes=50)
        session.state[parser_state_key] = parser
        session.state["completed_artifact_blocks_list"] = []
        session.state["completed_template_blocks_list"] = []
        session.state["artifact_chars_sent"] = 0  # Reset character tracking for new turn

    stream_chunks_were_processed = callback_context.state.get(
        A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY, False
    )
    if llm_response.partial:
        callback_context.state[A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY] = True

    if llm_response.partial or not stream_chunks_were_processed:
        processed_parts: List[adk_types.Part] = []
        original_parts = llm_response.content.parts if llm_response.content else []
        a2a_context = callback_context.state.get("a2a_context")

        for part in original_parts:
            if part.text is not None:
                parser_result = parser.process_chunk(part.text)

                if llm_response.partial:
                    if parser_result.user_facing_text:
                        processed_parts.append(
                            adk_types.Part(text=parser_result.user_facing_text)
                        )
                else:
                    processed_parts.append(part)

                for event in parser_result.events:
                    if isinstance(event, BlockStartedEvent):
                        log.info(
                            "%s Event: BlockStarted. Params: %s",
                            log_identifier,
                            event.params,
                        )
                        # Reset character tracking for this new artifact block
                        session.state["artifact_chars_sent"] = 0

                        filename = event.params.get("filename", "unknown_artifact")
                        if filename == "unknown_artifact":
                            log.warning(
                                "%s Fenced artifact block started without a 'filename' parameter.",
                                log_identifier,
                            )
                        description = event.params.get("description")
                        if filename == "unknown_artifact":
                            log.warning(
                                "%s Fenced artifact block started without a 'filename' parameter.",
                                log_identifier,
                            )
                        if a2a_context:
                            status_text = f"Receiving artifact `{filename}`..."
                            if description:
                                status_text = (
                                    f"Receiving artifact `{filename}`: {description}"
                                )
                            progress_data = AgentProgressUpdateData(
                                status_text=status_text
                            )
                            await _publish_data_part_status_update(
                                host_component, a2a_context, progress_data
                            )
                            # Also send an initial in-progress event to create the UI bubble
                            artifact_progress_data = ArtifactCreationProgressData(
                                filename=filename,
                                description=description,
                                status="in-progress",
                                bytes_transferred=0,
                                artifact_chunk=None,
                            )

                            await _publish_data_part_status_update(
                                host_component, a2a_context, artifact_progress_data
                            )
                        params_str = " ".join(
                            [f'{k}="{v}"' for k, v in event.params.items()]
                        )
                        original_text = f"{ARTIFACT_BLOCK_DELIMITER_OPEN}save_artifact: {params_str}\n"
                        session.state["artifact_block_original_text"] = original_text

                    elif isinstance(event, BlockProgressedEvent):
                        log.debug(
                            "%s Event: BlockProgressed. Size: %d",
                            log_identifier,
                            event.buffered_size,
                        )
                        params = event.params
                        filename = params.get("filename", "unknown_artifact")
                        if filename == "unknown_artifact":
                            log.warning(
                                "%s Fenced artifact block progressed without a 'filename' parameter.",
                                log_identifier,
                            )
                        if a2a_context:
                            # Resolve early embeds in the chunk before streaming
                            resolved_chunk = await _resolve_early_embeds_in_chunk(
                                chunk=event.chunk,
                                callback_context=callback_context,
                                host_component=host_component,
                                log_identifier=f"{log_identifier}[ResolveChunk]",
                            )

                            progress_data = ArtifactCreationProgressData(
                                filename=filename,
                                description=params.get("description"),
                                status="in-progress",
                                bytes_transferred=event.buffered_size,
                                artifact_chunk=resolved_chunk,  # Resolved chunk
                            )

                            # Track the cumulative character count of what we've sent
                            # We need character count (not bytes) to slice correctly later
                            previous_char_count = session.state.get("artifact_chars_sent", 0)
                            new_char_count = previous_char_count + len(event.chunk)
                            session.state["artifact_chars_sent"] = new_char_count

                            await _publish_data_part_status_update(
                                host_component, a2a_context, progress_data
                            )

                    elif isinstance(event, BlockCompletedEvent):
                        log.debug(
                            "%s Event: BlockCompleted. Content length: %d",
                            log_identifier,
                            len(event.content),
                        )
                        original_text = session.state.get(
                            "artifact_block_original_text", ""
                        )
                        original_text += event.content
                        original_text += "»»»"

                        tool_context_for_call = ToolContext(
                            callback_context._invocation_context
                        )

                        params = event.params
                        filename = params.get("filename")
                        if not filename or not filename.strip():
                            log.warning(
                                "%s Fenced artifact block is missing a valid 'filename'. Failing operation.",
                                log_identifier,
                            )
                            session.state["completed_artifact_blocks_list"].append(
                                {
                                    "filename": (
                                        "unknown_artifact"
                                        if filename is None
                                        else filename
                                    ),
                                    "version": 0,
                                    "status": "error",
                                    "original_text": original_text,
                                }
                            )
                            if a2a_context:
                                if not filename or not filename.strip():
                                    filename = "unknown_artifact"
                                progress_data = ArtifactCreationProgressData(
                                    filename=filename or "unknown_artifact",
                                    description=params.get("description"),
                                    status="failed",
                                    bytes_transferred=0,
                                )
                                await _publish_data_part_status_update(
                                    host_component, a2a_context, progress_data
                                )
                            continue

                        kwargs_for_call = {
                            "filename": filename,
                            "content": event.content,
                            "mime_type": params.get("mime_type"),
                            "description": params.get("description"),
                            "metadata_json": params.get("metadata"),
                            "tool_context": tool_context_for_call,
                        }
                        if "schema_max_keys" in params:
                            try:
                                kwargs_for_call["schema_max_keys"] = int(
                                    params["schema_max_keys"]
                                )
                            except (ValueError, TypeError):
                                log.warning(
                                    "%s Invalid 'schema_max_keys' value '%s'. Ignoring.",
                                    log_identifier,
                                    params["schema_max_keys"],
                                )
                        wrapped_creator = ADKToolWrapper(
                            original_func=_internal_create_artifact,
                            tool_config=None,  # No specific config for this internal tool
                            tool_name="_internal_create_artifact",
                            origin="internal",
                            resolution_type="early",
                        )
                        save_result = await wrapped_creator(**kwargs_for_call)

                        if save_result.get("status") in ["success", "partial_success"]:
                            status_for_tool = "success"
                            version_for_tool = save_result.get("data_version", 1)
                            try:
                                logical_task_id = a2a_context.get("logical_task_id")
                                if logical_task_id:
                                    with host_component.active_tasks_lock:
                                        task_context = host_component.active_tasks.get(
                                            logical_task_id
                                        )
                                    if task_context:
                                        task_context.register_produced_artifact(
                                            filename, version_for_tool
                                        )
                                        log.info(
                                            "%s Registered inline artifact '%s' v%d for task %s.",
                                            log_identifier,
                                            filename,
                                            version_for_tool,
                                            logical_task_id,
                                        )
                                else:
                                    log.warning(
                                        "%s No logical_task_id, cannot register inline artifact.",
                                        log_identifier,
                                    )
                            except Exception as e_track:
                                log.error(
                                    "%s Failed to track inline artifact: %s",
                                    log_identifier,
                                    e_track,
                                )

                            # Send final progress update with any remaining content not yet sent
                            if a2a_context:
                                # Check if there's unsent content (content after last progress event)
                                total_bytes = len(event.content.encode("utf-8"))
                                chars_already_sent = session.state.get("artifact_chars_sent", 0)

                                if chars_already_sent < len(event.content):
                                    # There's unsent content - send it as a final progress update
                                    final_chunk = event.content[chars_already_sent:]

                                    # Resolve embeds in final chunk
                                    resolved_final_chunk = await _resolve_early_embeds_in_chunk(
                                        chunk=final_chunk,
                                        callback_context=callback_context,
                                        host_component=host_component,
                                        log_identifier=f"{log_identifier}[ResolveFinalChunk]",
                                    )

                                    final_progress_data = ArtifactCreationProgressData(
                                        filename=filename,
                                        description=params.get("description"),
                                        status="in-progress",
                                        bytes_transferred=total_bytes,
                                        artifact_chunk=resolved_final_chunk,  # Resolved final chunk
                                    )

                                    await _publish_data_part_status_update(
                                        host_component, a2a_context, final_progress_data
                                    )

                            # Publish completion status immediately via SSE
                            if a2a_context:
                                progress_data = ArtifactCreationProgressData(
                                    filename=filename,
                                    description=params.get("description"),
                                    status="completed",
                                    bytes_transferred=len(event.content),
                                    mime_type=params.get("mime_type"),
                                    version=version_for_tool,
                                )

                                await _publish_data_part_status_update(
                                    host_component, a2a_context, progress_data
                                )
                        else:
                            status_for_tool = "error"
                            version_for_tool = 0
                            # Publish failure status immediately via SSE
                            if a2a_context:
                                progress_data = ArtifactCreationProgressData(
                                    filename=filename,
                                    description=params.get("description"),
                                    status="failed",
                                    bytes_transferred=len(event.content),
                                )
                                await _publish_data_part_status_update(
                                    host_component, a2a_context, progress_data
                                )

                        session.state["completed_artifact_blocks_list"].append(
                            {
                                "filename": filename,
                                "version": version_for_tool,
                                "status": status_for_tool,
                                "original_text": original_text,
                            }
                        )

                    elif isinstance(event, TemplateBlockStartedEvent):
                        log.debug(
                            "%s Event: TemplateBlockStarted. Params: %s",
                            log_identifier,
                            event.params,
                        )

                    elif isinstance(event, TemplateBlockCompletedEvent):
                        log.debug(
                            "%s Event: TemplateBlockCompleted. Template length: %d",
                            log_identifier,
                            len(event.template_content),
                        )

                        # Create a TemplateBlockData message to send to the gateway
                        template_id = str(uuid.uuid4())
                        params = event.params

                        data_artifact = params.get("data")
                        if not data_artifact:
                            log.warning(
                                "%s Template block is missing 'data' parameter. Skipping.",
                                log_identifier,
                            )
                            continue

                        template_data = TemplateBlockData(
                            template_id=template_id,
                            data_artifact=data_artifact,
                            jsonpath=params.get("jsonpath"),
                            limit=(
                                int(params.get("limit"))
                                if params.get("limit")
                                else None
                            ),
                            template_content=event.template_content,
                        )

                        # Publish A2A status update with template metadata
                        if a2a_context:
                            await _publish_data_part_status_update(
                                host_component, a2a_context, template_data
                            )
                            log.info(
                                "%s Published TemplateBlockData with ID: %s",
                                log_identifier,
                                template_id,
                            )

                        # Store template_id in session for potential future use
                        # (Gateway will handle the actual resolution)
                        if (
                            "completed_template_blocks_list" not in session.state
                            or session.state["completed_template_blocks_list"] is None
                        ):
                            session.state["completed_template_blocks_list"] = []
                        session.state["completed_template_blocks_list"].append(
                            {
                                "template_id": template_id,
                                "data_artifact": data_artifact,
                            }
                        )

                    elif isinstance(event, BlockInvalidatedEvent):
                        log.debug(
                            "%s Event: BlockInvalidated. Rolled back: '%s'",
                            log_identifier,
                            event.rolled_back_text,
                        )
            else:
                processed_parts.append(part)

        if llm_response.partial:
            if llm_response.content:
                llm_response.content.parts = processed_parts
            elif processed_parts:
                llm_response.content = adk_types.Content(parts=processed_parts)
    else:
        log.debug(
            "%s Ignoring text content of final aggregated response because stream was already processed.",
            log_identifier,
        )

    if not llm_response.partial and not llm_response.interrupted:
        log.debug(
            "%s Final, non-interrupted stream chunk received. Finalizing parser.",
            log_identifier,
        )
        final_parser_result = parser.finalize()

        for event in final_parser_result.events:
            if isinstance(event, BlockCompletedEvent):
                log.warning(
                    "%s Unterminated artifact block detected at end of turn.",
                    log_identifier,
                )
                params = event.params
                filename = params.get("filename", "unknown_artifact")
                if filename == "unknown_artifact":
                    log.warning(
                        "%s Unterminated fenced artifact block is missing a valid 'filename'. Failing operation.",
                        log_identifier,
                    )
                if (
                    "completed_artifact_blocks_list" not in session.state
                    or session.state["completed_artifact_blocks_list"] is None
                ):
                    session.state["completed_artifact_blocks_list"] = []
                session.state["completed_artifact_blocks_list"].append(
                    {
                        "filename": filename,
                        "version": 0,
                        "status": "error",
                        "original_text": session.state.get(
                            "artifact_block_original_text", ""
                        )
                        + event.content,
                    }
                )

        # If there was any rolled-back text from finalization, append it
        if final_parser_result.user_facing_text:
            if (
                llm_response.content
                and llm_response.content.parts
                and llm_response.content.parts[-1].text is not None
            ):
                llm_response.content.parts[
                    -1
                ].text += final_parser_result.user_facing_text
            else:
                if llm_response.content is None:
                    llm_response.content = adk_types.Content(parts=[])
                elif llm_response.content.parts is None:
                    llm_response.content.parts = []
                llm_response.content.parts.append(
                    adk_types.Part(text=final_parser_result.user_facing_text)
                )

        # Check if any blocks were completed and need to be injected into the final response
        completed_blocks_list = session.state.get("completed_artifact_blocks_list")
        if completed_blocks_list:
            log.info(
                "%s Injecting info for %d saved artifact(s) into final LlmResponse.",
                log_identifier,
                len(completed_blocks_list),
            )

            tool_call_parts = []
            for block_info in completed_blocks_list:
                notify_tool_call = adk_types.FunctionCall(
                    name="_notify_artifact_save",
                    args={
                        "filename": block_info["filename"],
                        "version": block_info["version"],
                        "status": block_info["status"],
                    },
                    id=f"host-notify-{uuid.uuid4()}",
                )
                tool_call_parts.append(adk_types.Part(function_call=notify_tool_call))

            existing_parts = llm_response.content.parts if llm_response.content else []
            final_existing_parts = existing_parts

            if llm_response.content is None:
                llm_response.content = adk_types.Content(parts=[])

            llm_response.content.parts = tool_call_parts + final_existing_parts

            llm_response.turn_complete = True
            llm_response.partial = False

        session.state[parser_state_key] = None
        session.state["completed_artifact_blocks_list"] = None
        session.state["artifact_block_original_text"] = None
        session.state["completed_template_blocks_list"] = None
        log.debug("%s Cleaned up parser session state.", log_identifier)

    return None


def create_dangling_tool_call_repair_content(
    dangling_calls: List[adk_types.FunctionCall], error_message: str
) -> adk_types.Content:
    """
    Creates a synthetic ADK Content object to repair a dangling tool call.

    Args:
        dangling_calls: The list of FunctionCall objects that need a response.
        error_message: The error message to include in the response.

    Returns:
        An ADK Content object with role='tool' containing the error response.
    """
    error_response_parts = []
    for fc in dangling_calls:
        error_response_part = adk_types.Part.from_function_response(
            name=fc.name,
            response={"status": "error", "message": error_message},
        )
        error_response_part.function_response.id = fc.id
        error_response_parts.append(error_response_part)

    return adk_types.Content(role="tool", parts=error_response_parts)


def repair_history_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    ADK before_model_callback to proactively check for and repair dangling
    tool calls in the conversation history before it's sent to the LLM.
    This acts as a "suspender" to catch any history corruption.
    """
    log_identifier = "[Callback:RepairHistory]"
    if not llm_request.contents:
        return None

    history_modified = False
    i = 0
    while i < len(llm_request.contents):
        content = llm_request.contents[i]
        function_calls = []
        if content.role == "model" and content.parts:
            function_calls = [p.function_call for p in content.parts if p.function_call]

        if function_calls:
            next_content_is_valid_response = False
            if (i + 1) < len(llm_request.contents):
                next_content = llm_request.contents[i + 1]
                if (
                    next_content.role in ["user", "tool"]
                    and next_content.parts
                    and any(p.function_response for p in next_content.parts)
                ):
                    next_content_is_valid_response = True

            if not next_content_is_valid_response:
                log.warning(
                    "%s Found dangling tool call in history for tool(s): %s. Repairing.",
                    log_identifier,
                    [fc.name for fc in function_calls],
                )
                repair_content = create_dangling_tool_call_repair_content(
                    dangling_calls=function_calls,
                    error_message="The previous tool call did not complete successfully and was automatically repaired.",
                )
                llm_request.contents.insert(i + 1, repair_content)
                history_modified = True
                i += 1
        i += 1

    if history_modified:
        log.info(
            "%s History was modified to repair dangling tool calls.", log_identifier
        )

    return None


def _recursively_clean_pydantic_types(data: Any) -> Any:
    """
    Recursively traverses a data structure (dicts, lists) and converts
    Pydantic-specific types like AnyUrl to their primitive string representation
    to ensure JSON serializability.
    """
    if isinstance(data, dict):
        return {
            key: _recursively_clean_pydantic_types(value) for key, value in data.items()
        }
    elif isinstance(data, list):
        return [_recursively_clean_pydantic_types(item) for item in data]
    # Check for Pydantic's AnyUrl without a direct import to avoid dependency issues.
    elif type(data).__name__ == "AnyUrl" and hasattr(data, "__str__"):
        return str(data)
    return data


def _mcp_response_contains_non_text(mcp_response_dict: Dict[str, Any]) -> bool:
    """
    Checks if the 'content' list in an MCP response dictionary contains any
    items that are not of type 'text'.
    """
    if not isinstance(mcp_response_dict, dict):
        return False

    content_list = mcp_response_dict.get("content")
    if not isinstance(content_list, list):
        return False

    for item in content_list:
        if isinstance(item, dict) and item.get("type") != "text":
            return True
    return False


async def manage_large_mcp_tool_responses_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
    host_component: "SamAgentComponent",
) -> Optional[Dict[str, Any]]:
    """
    Manages large or non-textual responses from MCP tools.

    This callback intercepts the response from an MCPTool. Based on the response's
    size and content type, it performs one or more of the following actions:
    1.  **Saves as Artifact:** If the response size exceeds a configured threshold,
        or if it contains non-textual content (like images), it calls the
        `save_mcp_response_as_artifact_intelligent` function to save the
        response as one or more typed artifacts.
    2.  **Truncates for LLM:** If the response size exceeds a configured limit for
        the LLM, it truncates the content to a preview string.
    3.  **Constructs Final Response:** It builds a new dictionary to be returned
        to the LLM, which includes:
        - A `message_to_llm` summarizing what was done (e.g., saved, truncated).
        - `saved_mcp_response_artifact_details` with the result of the save operation.
        - `mcp_tool_output` containing either the original response or the truncated preview.
        - A `status` field indicating the outcome (e.g., 'processed_and_saved').

    The `tool_response` is the direct output from the tool's `run_async` method.
    """
    log_identifier = f"[Callback:ManageLargeMCPResponse:{tool.name}]"
    log.info(
        "%s Starting callback for tool response, type: %s",
        log_identifier,
        type(tool_response).__name__,
    )

    if tool_response is None:
        return None

    if not isinstance(tool, MCPTool):
        log.debug(
            "%s Tool is not an MCPTool. Skipping large response handling.",
            log_identifier,
        )
        return (
            tool_response
            if isinstance(tool_response, dict)
            else {"result": tool_response}
        )

    log.debug(
        "%s Tool is an MCPTool. Proceeding with large response handling.",
        log_identifier,
    )

    if hasattr(tool_response, "model_dump"):
        mcp_response_dict = tool_response.model_dump(exclude_none=True)
        log.debug("%s Converted MCPTool response object to dictionary.", log_identifier)
    elif isinstance(tool_response, dict):
        mcp_response_dict = tool_response
        log.debug("%s MCPTool response is already a dictionary.", log_identifier)
    else:
        log.warning(
            "%s MCPTool response is not a Pydantic model or dict (type: %s). Attempting to proceed, but serialization might fail.",
            log_identifier,
            type(tool_response),
        )
        mcp_response_dict = tool_response

    # Clean any Pydantic-specific types before serialization
    mcp_response_dict = _recursively_clean_pydantic_types(mcp_response_dict)
    cleaned_args = _recursively_clean_pydantic_types(args)

    try:
        save_threshold = host_component.get_config(
            "mcp_tool_response_save_threshold_bytes", 2048
        )
        llm_max_bytes = host_component.get_config("mcp_tool_llm_return_max_bytes", 4096)
        log.debug(
            "%s Config: save_threshold=%d bytes, llm_max_bytes=%d bytes.",
            log_identifier,
            save_threshold,
            llm_max_bytes,
        )
    except Exception as e:
        log.error(
            "%s Error retrieving configuration: %s. Using defaults.", log_identifier, e
        )
        save_threshold = 2048
        llm_max_bytes = 4096

    contains_non_text_content = _mcp_response_contains_non_text(mcp_response_dict)
    if not contains_non_text_content:
        try:
            serialized_original_response_str = json.dumps(mcp_response_dict)
            original_response_bytes = len(
                serialized_original_response_str.encode("utf-8")
            )
            log.debug(
                "%s Original response size: %d bytes.",
                log_identifier,
                original_response_bytes,
            )
        except TypeError as e:
            log.error(
                "%s Failed to serialize original MCP tool response dictionary: %s. Returning original response object.",
                log_identifier,
                e,
            )
            return tool_response
        needs_truncation_for_llm = original_response_bytes > llm_max_bytes
        needs_saving_as_artifact = (
            original_response_bytes > save_threshold
        ) or needs_truncation_for_llm
    else:
        needs_truncation_for_llm = False
        needs_saving_as_artifact = True

    save_result = None
    if needs_saving_as_artifact:
        save_result = await save_mcp_response_as_artifact_intelligent(
            tool, tool_context, host_component, mcp_response_dict, cleaned_args
        )
        if save_result.status == McpSaveStatus.ERROR:
            log.warning(
                "%s Failed to save artifact: %s. Proceeding without saved artifact details.",
                log_identifier,
                save_result.message,
            )

    final_llm_response_dict: Dict[str, Any] = {}
    message_parts_for_llm: list[str] = []

    if needs_truncation_for_llm:
        truncation_suffix = "... [Response truncated due to size limit.]"
        adjusted_max_bytes = llm_max_bytes - len(truncation_suffix.encode("utf-8"))
        if adjusted_max_bytes < 0:
            adjusted_max_bytes = 0

        truncated_bytes = serialized_original_response_str.encode("utf-8")[
            :adjusted_max_bytes
        ]
        truncated_preview_str = (
            truncated_bytes.decode("utf-8", "ignore") + truncation_suffix
        )

        final_llm_response_dict["mcp_tool_output"] = {
            "type": "truncated_json_string",
            "content": truncated_preview_str,
        }
        message_parts_for_llm.append(
            f"The response from tool '{tool.name}' was too large ({original_response_bytes} bytes) for direct display and has been truncated."
        )
        log.debug("%s MCP tool output truncated for LLM.", log_identifier)

    if needs_saving_as_artifact:
        if save_result and save_result.status in [
            McpSaveStatus.SUCCESS,
            McpSaveStatus.PARTIAL_SUCCESS,
        ]:
            final_llm_response_dict["saved_mcp_response_artifact_details"] = (
                save_result.model_dump(exclude_none=True)
            )

            total_artifacts = len(save_result.artifacts_saved)
            if total_artifacts > 0:
                first_artifact = save_result.artifacts_saved[0]
                filename = first_artifact.data_filename
                version = first_artifact.data_version
                if total_artifacts > 1:
                    message_parts_for_llm.append(
                        f"The full response has been saved as {total_artifacts} artifacts, starting with '{filename}' (version {version})."
                    )
                else:
                    message_parts_for_llm.append(
                        f"The full response has been saved as artifact '{filename}' (version {version})."
                    )
            elif save_result.fallback_artifact:
                filename = save_result.fallback_artifact.data_filename
                version = save_result.fallback_artifact.data_version
                message_parts_for_llm.append(
                    f"The full response has been saved as artifact '{filename}' (version {version})."
                )

            log.debug(
                "%s Added saved artifact details to LLM response.", log_identifier
            )
        else:
            message_parts_for_llm.append(
                "Saving the full response as an artifact failed."
            )
            if save_result:
                final_llm_response_dict["saved_mcp_response_artifact_details"] = (
                    save_result.model_dump(exclude_none=True)
                )
            log.warning(
                "%s Artifact save failed, error details included in LLM response.",
                log_identifier,
            )
    else:
        final_llm_response_dict["mcp_tool_output"] = mcp_response_dict

    if needs_saving_as_artifact and (
        save_result
        and save_result.status in [McpSaveStatus.SUCCESS, McpSaveStatus.PARTIAL_SUCCESS]
    ):
        if needs_truncation_for_llm:
            final_llm_response_dict["status"] = "processed_saved_and_truncated"
        else:
            final_llm_response_dict["status"] = "processed_and_saved"
    elif needs_saving_as_artifact:
        if needs_truncation_for_llm:
            final_llm_response_dict["status"] = "processed_truncated_save_failed"
        else:
            final_llm_response_dict["status"] = "processed_save_failed"
    elif needs_truncation_for_llm:
        final_llm_response_dict["status"] = "processed_truncated"
    else:
        final_llm_response_dict["status"] = "processed"

    if not message_parts_for_llm:
        message_parts_for_llm.append(f"Response from tool '{tool.name}' processed.")
    final_llm_response_dict["message_to_llm"] = " ".join(message_parts_for_llm)

    log.info(
        "%s Returning processed response for LLM. Final status: %s",
        log_identifier,
        final_llm_response_dict.get("status", "unknown"),
    )
    return final_llm_response_dict


def _generate_fenced_block_syntax_rules() -> str:
    """Generates the shared syntax rules for all fenced blocks."""
    open_delim = ARTIFACT_BLOCK_DELIMITER_OPEN
    close_delim = ARTIFACT_BLOCK_DELIMITER_CLOSE
    return f"""
**Fenced Block Syntax Rules (Applies to `save_artifact` and `template_liquid`):**
To create content blocks, you MUST use the EXACT syntax shown below.

**EXACT SYNTAX (copy this pattern exactly):**
{open_delim}keyword: parameter="value" ...
The content for the block goes here.
It can span multiple lines.
{close_delim}

**CRITICAL FORMATTING RULES:**
  1. The opening delimiter MUST be EXACTLY `{open_delim}`.
  2. Immediately after the delimiter, write the keyword (`save_artifact` or `template_liquid`) followed by a colon, with NO space before the colon (e.g., `{open_delim}save_artifact:`).
  3. All parameters (like `filename`, `data`, `mime_type`) must be on the SAME line as the opening delimiter.
  4. All parameter values **MUST** be enclosed in double quotes (e.g., `filename="example.txt"`).
  5. You **MUST NOT** use double quotes `"` inside parameter values. Use single quotes or rephrase instead.
  6. The block's content begins on the line immediately following the parameters.
  7. Close the block with EXACTLY `{close_delim}` (three angle brackets) on its own line.
  8. Do NOT surround the block with triple backticks (```). The `{open_delim}` and `{close_delim}` delimiters are sufficient.

**COMMON ERRORS TO AVOID:**
  ❌ WRONG: `{open_delim[0:1]}template_liquid:` (only 1 angle brackets)
  ❌ WRONG: `{open_delim[0:2]}save_artifact:` (only 2 angle brackets)
  ❌ WRONG: `{open_delim}save_artifact` (missing colon)
  ✅ CORRECT: `{open_delim}save_artifact: filename="test.txt" mime_type="text/plain"`
"""


def _generate_fenced_artifact_instruction() -> str:
    """Generates the instruction text for using fenced artifact blocks."""
    open_delim = ARTIFACT_BLOCK_DELIMITER_OPEN
    return f"""\
**Creating Text-Based Artifacts (`{open_delim}save_artifact: ...`):**

When to Create Artifacts:
Create an artifact when the content provides value as a standalone file, such as:
- Content with special formatting (HTML, Markdown, CSS).
- Documents intended for use outside the conversation (reports, emails).
- Structured reference content (schedules, guides, templates).
- Substantial text documents or technical documentation.

When NOT to Create Artifacts:
- Simple answers, explanations, or conversational responses.
- Brief advice, opinions, or short lists.

Behavior of Created Artifacts:
- They are sent to the user as an interactive file component.
- The user can see the content, so there is no need to return or embed it again.

Parameters for `{open_delim}save_artifact: ...`:
- `filename="your_filename.ext"` (REQUIRED)
- `mime_type="text/plain"` (optional, defaults to text/plain)
- `description="A brief description."` (optional)

The system will automatically save the content and confirm it in the next turn.
"""


def _generate_inline_template_instruction() -> str:
    """Generates the instruction text for using inline Liquid templates."""
    open_delim = ARTIFACT_BLOCK_DELIMITER_OPEN
    close_delim = ARTIFACT_BLOCK_DELIMITER_CLOSE
    return f"""\
**Inline Liquid Templates (`{open_delim}template_liquid: ...`):**

Use inline Liquid templates to dynamically render data from artifacts for user-friendly display. This is faster and more accurate than reading the artifact and reformatting it yourself.

IMPORTANT: Template Format
- Templates use Liquid template syntax (same as Shopify templates - NOTE that Jekyll extensions are NOT supported).

When to Use Inline Templates:
- Formatting CSV, JSON, or YAML data into tables or lists.
- Applying simple transformations (filtering, limiting rows).

Parameters for `{open_delim}template_liquid: ...`:
- `data="filename.ext"` (REQUIRED): The data artifact to render. Can include version: `data="file.csv:2"`.
- `jsonpath="$.expression"` (optional): JSONPath to extract a subset of JSON/YAML data.
- `limit="N"` (optional): Limit to the first N rows (CSV) or items (JSON/YAML arrays).

Data Context for Liquid Templates:
- CSV data: Available as `headers` (array of column names) and `data_rows` (array of row arrays).
- JSON/YAML arrays: Available as `items`.
- JSON/YAML objects: Keys are directly available (e.g., `name`, `email`).

Example - CSV Table:
{open_delim}template_liquid: data="sales_data.csv" limit="5"
| {{% for h in headers %}}{{{{ h }}}} | {{% endfor %}}
|{{% for h in headers %}}---|{{% endfor %}}
{{% for row in data_rows %}}| {{% for cell in row %}}{{{{ cell }}}} | {{% endfor %}}{{% endfor %}}
{close_delim}

Negative Examples
Use {{ issues.size }} instead of {{ issues|length }}
Use {{ forloop.index }} instead of {{ loop.index }} (Liquid uses forloop not loop)
Use {{ issue.fields.description | truncate: 200 }} instead of slicing with [:200]
Do not use Jekyll-specific tags or filters (e.g., `{{% assign %}}`, `{{% capture %}}`, `where`, `sort`, `where_exp`, etc.)

The rendered output will appear inline in your response automatically.
"""


def _generate_artifact_creation_instruction() -> str:
    return """
    **Creating Text-Based Artifacts:**

    When to Create Text-based Artifacts:
    Create an artifact when the content provides value as a standalone file:
    - Content with special formatting (HTML, Markdown, CSS, structured markup) that requires proper rendering
    - Content explicitly intended for use outside this conversation (reports, emails, presentations, reference documents)
    - Structured reference content users will save or follow (schedules, guides, templates)
    - Content that will be edited, expanded, or reused
    - Substantial text documents
    - Technical documentation meant as reference material

    When NOT to Create Text-based Artifacts:
    - Simple answers, explanations, or conversational responses
    - Brief advice, opinions, or quick information
    - Short lists, summaries, or single paragraphs
    - Temporary content only relevant to the immediate conversation
    - Basic explanations that don't require reference material
    """


def _generate_examples_instruction() -> str:
    open_delim = ARTIFACT_BLOCK_DELIMITER_OPEN
    close_delim = ARTIFACT_BLOCK_DELIMITER_CLOSE
    embed_open_delim = EMBED_DELIMITER_OPEN
    embed_close_delim = EMBED_DELIMITER_CLOSE

    return (
        f"""\
    Example 1:
    - User: "Create a markdown file with your two csv files as tables."
    <note>There are two csv files already uploaded: data1.csv and data2.csv</note>
    - OrchestratorAgent:
    {embed_open_delim}status_update:Creating Markdown tables from CSV files...{embed_close_delim}
    {open_delim}save_artifact: filename="data_tables.md" mime_type="text/markdown" description="Markdown tables from CSV files"
    # Data Tables
    ## Data 1
    {open_delim}template_liquid: data="data1.csv"
    """
        + """| {% for h in headers %}{{ h }} | {% endfor %}
    |{% for h in headers %}---|{% endfor %}
    {% for row in data_rows %}| {% for cell in row %}{{ cell }} | {% endfor %}{% endfor %}
    """
        + f"""{close_delim}
    ## Data 2
    {open_delim}template_liquid: data="data2.csv"
    """
        + """| {% for h in headers %}{{ h }} | {% endfor %}
    |{% for h in headers %}---|{% endfor %}
    {% for row in data_rows %}| {% for cell in row %}{{ cell }} | {% endfor %}{% endfor %}
    """
        + f"""{close_delim}
    {close_delim}
    Example 2:
    - User: "Create a text file with the result of sqrt(12345) + sqrt(67890) + sqrt(13579) + sqrt(24680)."
    - OrchestratorAgent:
    {embed_open_delim}status_update:Calculating and creating text file...{embed_close_delim}
    {open_delim}save_artifact: filename="math.txt" mime_type="text/plain" description="Result of sqrt(12345) + sqrt(67890) + sqrt(13579) + sqrt(24680)"
    result = {embed_open_delim}math: sqrt(12345) + sqrt(67890) + sqrt(13579) + sqrt(24680) | .2f{embed_close_delim}
    {close_delim}
    
    Example 3:
    - User: "Show me the first 10 entries from data1.csv"
    - OrchestratorAgent:
    {embed_open_delim}status_update:Loading CSV data...{embed_close_delim}
    {open_delim}template_liquid: data="data1.csv" limit="10"
    """
        + """| {% for h in headers %}{{ h }} | {% endfor %}
    |{% for h in headers %}---|{% endfor %}
    {% for row in data_rows %}| {% for cell in row %}{{ cell }} | {% endfor %}{% endfor %}
    """
        + f"""{close_delim}

    Example 4:
    - User: "Search the database for all orders from last month"
    - OrchestratorAgent:
    {embed_open_delim}status_update:Querying order database...{embed_close_delim}
    [calls search_database tool with no visible text]
    [After getting results:]
    Found 247 orders from last month totaling $45,231.

    Example 5:
    - User: "Create an HTML with the chart image you just generated with the customer data."
    - OrchestratorAgent:
    {embed_open_delim}status_update:Generating HTML report with chart...{embed_close_delim}
    {open_delim}save_artifact: filename="customer_analysis.html" mime_type="text/html" description="Interactive customer analysis dashboard"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Customer Chart - {embed_open_delim}datetime:%Y-%m-%d{embed_close_delim}</title>
    """
        + """
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            .metric { background: #f0f0f0; padding: 10px; margin: 10px 0; }
            img { max-width: 100%; height: auto; }
    """
        + f"""    </style>
        </head>
    <body>
    <h1>Customer Analysis Report</h1>
    <p>Generated: {embed_open_delim}datetime:iso{embed_close_delim}</p>
        
    <h2>Customer Distribution Chart</h2>
    <img src="{embed_open_delim}artifact_content:customer_chart.png >>> format:datauri{embed_close_delim}" alt="Customer Distribution">
    
    </body>
    </html>
    {close_delim}

    """
    )


def _generate_embed_instruction(
    include_artifact_content: bool,
    log_identifier: str,
) -> Optional[str]:
    """Generates the instruction text for using embeds."""
    open_delim = EMBED_DELIMITER_OPEN
    close_delim = EMBED_DELIMITER_CLOSE
    chain_delim = EMBED_CHAIN_DELIMITER
    early_types = "`math`, `datetime`, `uuid`, `artifact_meta`"

    modifier_list = MODIFIER_IMPLEMENTATIONS.keys()
    # Remove apply_to_template from the modifier list as it's been deprecated
    if "apply_to_template" in modifier_list:
        modifier_list = list(modifier_list)
        modifier_list.remove("apply_to_template")
    modifier_list = ", ".join([f"`{prefix}`" for prefix in modifier_list])

    base_instruction = f"""\
**Using Dynamic Embeds in Responses:**

You can use dynamic embeds in your text responses and tool parameters using the syntax {open_delim}type:expression {chain_delim} format{close_delim}. NOTE that this differs from 'save_artifact', which has  different delimiters. This allows you to
always have correct information in your output. Specifically, make sure you always use embeds for math, even if it is simple. You will make mistakes if you try to do math yourself.
Use HTML entities to escape the delimiters.
This host resolves the following embed types *early* (before sending to the LLM or tool): {early_types}. This means the embed is replaced with its resolved value.
- `{open_delim}math:expression | .2f{close_delim}`: Evaluates the math expression using asteval - this must just be plain math (plus random(), randint() and uniform()), don't import anything. Optional format specifier follows Python's format(). Use this for all math calculations rather than doing it yourself. Don't give approximations.
- `{open_delim}datetime:format_or_keyword{close_delim}`: Inserts current date/time. Use Python strftime format (e.g., `%Y-%m-%d`) or keywords (`iso`, `timestamp`, `date`, `time`, `now`).
- `{open_delim}uuid:{close_delim}`: Inserts a random UUID.
- `{open_delim}artifact_meta:filename[:version]{close_delim}`: Inserts a summary of the artifact's metadata (latest version if unspecified).
- `{open_delim}status_update:Your message here{close_delim}`: Generates an immediate, distinct status message event that is displayed to the user (e.g., 'Thinking...', 'Searching database...'). This message appears in a status area, not as part of the main chat conversation. Use this to provide interim feedback during processing.

Examples:
- `{open_delim}status_update:Analyzing data...{close_delim}` (Shows 'Analyzing data...' as a status update)
- `The result of 23.5 * 4.2 is {open_delim}math:23.5 * 4.2 | .2f{close_delim}` (Embeds calculated result with 2 decimal places)

The following embeds are resolved *late* (by the gateway before final display):
- `{open_delim}artifact_return:filename[:version]{close_delim}`: This is the primary way to return an artifact to the user. It attaches the specified artifact to the message. The embed itself is removed from the text. Use this instead of describing a file and expecting the user to download it. Note: artifact_return is not necessary if the artifact was just created by you in this same response, since newly created artifacts are automatically attached to your message.
"""

    artifact_content_instruction = f"""
- `{open_delim}artifact_content:filename[:version] {chain_delim} modifier1:value1 {chain_delim} ... {chain_delim} format:output_format{close_delim}`: Embeds artifact content after applying a chain of modifiers. This is resolved *late* (typically by a gateway before final display).
    - If this embed resolves to binary content (like an image), it will be automatically converted into an attached file, similar to `artifact_return`.
    - Use `{chain_delim}` to separate the artifact identifier from the modifier steps and the final format step.
    - Available modifiers: {modifier_list}.
    - The `format:output_format` step *must* be the last step in the chain. Supported formats include `text`, `datauri`, `json`, `json_pretty`, `csv`. Formatting as datauri, will include the data URI prefix, so do not add it yourself.
    - Use `artifact_meta` first to check size; embedding large files may fail.
    - Efficient workflows for large artifacts:
        - To extract specific line ranges: `load_artifact(filename, version, include_line_numbers=True)` to identify lines, then use `slice_lines:start:end` modifier to extract that range.
        - To fill templates with many placeholders: use `artifact_search_and_replace_regex` with `replacements` array (single atomic operation instead of multiple calls).
        - Line numbers are display-only; `slice_lines` always operates on original content.
    - Examples:
        - `<img src="{open_delim}artifact_content:image.png {chain_delim} format:datauri{close_delim}`"> (Embed image as data URI - NOTE that this includes the datauri prefix. Do not add it yourself.)
        - `{open_delim}artifact_content:data.json {chain_delim} jsonpath:$.items[*] {chain_delim} select_fields:name,status {chain_delim} format:json_pretty{close_delim}` (Extract and format JSON fields)
        - `{open_delim}artifact_content:logs.txt {chain_delim} grep:ERROR {chain_delim} head:10 {chain_delim} format:text{close_delim}` (Get first 10 error lines)
        - `{open_delim}artifact_content:config.json {chain_delim} jsonpath:$.userPreferences.theme {chain_delim} format:text{close_delim}` (Extract a single value from a JSON artifact)
        - `{open_delim}artifact_content:server.log {chain_delim} tail:100 {chain_delim} grep:WARN {chain_delim} format:text{close_delim}` (Get warning lines from the last 100 lines of a log file)
        - `{open_delim}artifact_content:template.html {chain_delim} slice_lines:10:50 {chain_delim} format:text{close_delim}` (Extract lines 10-50 from a large file)
        - `<img src="{open_delim}artifact_content:diagram.png {chain_delim} format:datauri{close_delim}`"> (Embed an PNG diagram as a data URI)`
"""

    final_instruction = base_instruction
    if include_artifact_content:
        final_instruction += artifact_content_instruction

    final_instruction += f"""
Ensure the syntax is exactly `{open_delim}type:expression{close_delim}` or `{open_delim}type:expression {chain_delim} ... {chain_delim} format:output_format{close_delim}` with no extra spaces around delimiters (`{open_delim}`, `{close_delim}`, `{chain_delim}`, `:`, `|`). Malformed directives will be ignored."""

    return final_instruction


def _generate_conversation_flow_instruction() -> str:
    """Generates instruction text for conversation flow and response formatting."""
    open_delim = EMBED_DELIMITER_OPEN
    close_delim = EMBED_DELIMITER_CLOSE
    return f"""\
**Conversation Flow and Response Formatting:**

**CRITICAL: Minimize Narration - Maximize Results**

You do NOT need to produce visible text on every turn. Many turns should contain ONLY status updates and tool calls, with NO visible text at all.
Only produce visible text when you have actual results, answers, or insights to share with the user.

Response Content Rules:
1. Visible responses should contain ONLY:
   - Direct answers to the user's question
   - Analysis and insights derived from tool results
   - Final results and data
   - Follow-up questions when needed
   - Plans for complex multi-step tasks

2. DO NOT include visible text for:
   - Process narration ("Let me...", "I'll...", "Now I will...")
   - Acknowledgments of tool calls ("I'm calling...", "Searching...")
   - Descriptions of what you're about to do
   - Play-by-play commentary on your actions
   - Transitional phrases between tool calls

3. Use invisible status_update embeds for ALL process updates:
   - "Searching for..."
   - "Analyzing..."
   - "Creating..."
   - "Querying..."
   - "Calling agent X..."

4. NEVER mix process narration with status updates - if you use a status_update embed, do NOT repeat that information in visible text.

Examples:

**Excellent (no visible text, just status and tools):**
"{open_delim}status_update:Retrieving sales data...{close_delim}" [then calls tool, no visible text]

**Good (visible text only contains results):**
"{open_delim}status_update:Analyzing Q4 sales...{close_delim}" [calls tool]
"Sales increased 23% in Q4, driven primarily by enterprise accounts."

**Bad (unnecessary narration):**
"Let me retrieve the sales data for you." [then calls tool]

**Bad (narration mixed with results):**
"I've analyzed the data and found that sales increased 23% in Q4."

**Bad (play-by-play commentary):**
"Now I'll search for the information. After that I'll analyze it."

Remember: The user can see status updates and tool calls. You don't need to announce them in visible text.
"""


def _generate_tool_instructions_from_registry(
    active_tools: List[BuiltinTool],
    log_identifier: str,
) -> str:
    """Generates instruction text from a list of BuiltinTool definitions."""
    if not active_tools:
        return ""

    instructions_by_category = defaultdict(list)
    for tool in sorted(active_tools, key=lambda t: (t.category, t.name)):
        # Skip internal tools (those starting with underscore)
        if tool.name.startswith("_"):
            continue

        param_parts = []
        if tool.parameters and tool.parameters.properties:
            for name, schema in tool.parameters.properties.items():
                is_optional = name not in (tool.parameters.required or [])
                type_name = "any"
                if schema and hasattr(schema, "type") and schema.type:
                    type_name = schema.type.name.lower()

                param_str = f"{name}: {type_name}"
                if is_optional:
                    param_str = f"Optional[{param_str}]"
                param_parts.append(param_str)

        signature = f"`{tool.name}({', '.join(param_parts)})`"
        description = tool.description or "No description available."

        instructions_by_category[tool.category].append(f"- {signature}: {description}")

    full_instruction_list = []
    for category, tool_instructions in sorted(instructions_by_category.items()):
        category_display_name = category.replace("_", " ").title()
        full_instruction_list.append(
            f"You have access to the following '{category_display_name}' tools:"
        )
        full_instruction_list.extend(tool_instructions)

    return "\n".join(full_instruction_list)


def inject_dynamic_instructions_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
    host_component: "SamAgentComponent",
    active_builtin_tools: List[BuiltinTool],
) -> Optional[LlmResponse]:
    """
    ADK before_model_callback to inject instructions based on host config.
    Modifies the llm_request directly.
    """
    log_identifier = "[Callback:InjectInstructions]"
    log.debug("%s Running instruction injection callback...", log_identifier)

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot inject instructions.",
            log_identifier,
        )
        return None

    injected_instructions = []

    planning_instruction = """\
Parallel Tool Calling:
The system is capable of calling multiple tools in parallel to speed up processing. Please try to run tools in parallel when they don't depend on each other. This saves money and time, providing faster results to the user.

**Response Formatting - CRITICAL**:
In most cases when calling tools, you should produce NO visible text at all - only status_update embeds and the tool calls themselves.
The user can see your tool calls and status updates, so narrating your actions is redundant and creates noise.

If you do include visible text:
- It must contain actual results, insights, or answers - NOT process narration
- Do NOT end with a colon (":") before tool calls, as this leaves it hanging
- Prefer ending with a period (".") if you must include visible text

Examples:
 - BEST: "{open_delim}status_update:Searching database...{close_delim}" [then calls tool, NO visible text]
 - BAD: "Let me search for that information." [then calls tool]
 - BAD: "Searching for information..." [then calls tool]

Embeds in responses from agents:
To be efficient, peer agents may respond with artifact_content in their responses. These will not be resolved until they are sent back to a gateway. If it makes
sense, just carry that embed forward to your response to the user. For example, if you ask for an org chart from another agent and its response contains an embed like
`{open_delim}artifact_content:org_chart.md{close_delim}`, you can just include that embed in your response to the user. The gateway will resolve it and display the org chart.

Similarly, template_liquid blocks in peer agent responses can be carried forward to your response to the user for resolution by the gateway.

When faced with a complex goal or request that involves multiple steps, data retrieval, or artifact summarization to produce a new report or document, you MUST first create a plan.
Simple, direct requests like 'create an image of a dog' or 'write an email to thank my boss' do not require a plan.

If a plan is created:
1. It should be a terse, hierarchical list describing the steps needed, with each checkbox item on its own line.
2. Use '⬜' for pending items, '✅' for completed items, and '❌' for cancelled items.
3. If the plan changes significantly during execution, restate the updated plan.
4. As items are completed, update the plan to check them off.

"""
    injected_instructions.append(planning_instruction)

    # Add the consolidated block instructions
    injected_instructions.append(_generate_fenced_artifact_instruction())
    injected_instructions.append(_generate_inline_template_instruction())
    injected_instructions.append(_generate_fenced_block_syntax_rules())

    agent_instruction_str: Optional[str] = None
    if host_component._agent_system_instruction_callback:
        log.debug(
            "%s Calling agent-provided system instruction callback.", log_identifier
        )
        try:
            agent_instruction_str = host_component._agent_system_instruction_callback(
                callback_context, llm_request
            )
            if agent_instruction_str and isinstance(agent_instruction_str, str):
                injected_instructions.append(agent_instruction_str)
                log.info(
                    "%s Injected instructions from agent callback.", log_identifier
                )
            elif agent_instruction_str:
                log.warning(
                    "%s Agent instruction callback returned non-string type: %s. Ignoring.",
                    log_identifier,
                    type(agent_instruction_str),
                )
        except Exception as e_cb:
            log.error(
                "%s Error in agent-provided system instruction callback: %s. Skipping.",
                log_identifier,
                e_cb,
            )
    if host_component._agent_system_instruction_string:
        log.debug(
            "%s Using agent-provided static system instruction string.", log_identifier
        )
        agent_instruction_str = host_component._agent_system_instruction_string
        if agent_instruction_str and isinstance(agent_instruction_str, str):
            injected_instructions.append(agent_instruction_str)
            log.info("%s Injected static instructions from agent.", log_identifier)

    contents = llm_request.contents
    if contents:
        log.debug("\n\n### LLM Request Contents ###")
        for content in contents:
            if content.parts:
                for part in content.parts:
                    if part.text:
                        log.debug("Content part: %s", part.text)
                    elif part.function_call:
                        log.debug("Function call: %s", part.function_call.name)
                    elif part.function_response:
                        log.debug("Function response: %s", part.function_response)
                    else:
                        log.debug("raw: %s", part)
        log.debug("### End LLM Request Contents ###\n\n")

    if host_component.get_config("enable_embed_resolution", True):
        include_artifact_content_instr = host_component.get_config(
            "enable_artifact_content_instruction", True
        )
        instruction = _generate_embed_instruction(
            include_artifact_content_instr, log_identifier
        )
        if instruction:
            injected_instructions.append(instruction)
            log.debug(
                "%s Prepared embed instructions (artifact_content included: %s).",
                log_identifier,
                include_artifact_content_instr,
            )

        instruction = _generate_conversation_flow_instruction()
        if instruction:
            injected_instructions.append(instruction)
            log.debug("%s Prepared conversation flow instructions.", log_identifier)

    if active_builtin_tools:
        instruction = _generate_tool_instructions_from_registry(
            active_builtin_tools, log_identifier
        )
        if instruction:
            injected_instructions.append(instruction)
            log.debug(
                "%s Prepared instructions for %d active built-in tools.",
                log_identifier,
                len(active_builtin_tools),
            )

    peer_instructions = callback_context.state.get("peer_tool_instructions")
    if peer_instructions and isinstance(peer_instructions, str):
        injected_instructions.append(peer_instructions)
        log.debug(
            "%s Injected peer discovery instructions from callback state.",
            log_identifier,
        )

    last_call_notification_message_added = False
    try:
        invocation_context = callback_context._invocation_context
        if invocation_context and invocation_context.run_config:
            current_llm_calls = (
                invocation_context._invocation_cost_manager._number_of_llm_calls
            )
            max_llm_calls = invocation_context.run_config.max_llm_calls

            log.debug(
                "%s Checking for last LLM call: current_calls=%d, max_calls=%s",
                log_identifier,
                current_llm_calls,
                max_llm_calls,
            )

            if (
                max_llm_calls
                and max_llm_calls > 0
                and current_llm_calls >= (max_llm_calls - 1)
            ):
                last_call_text = (
                    "IMPORTANT: This is your final allowed interaction for the current request. "
                    "Please inform the user that to continue this line of inquiry, they will need to "
                    "make a new request or explicitly ask to continue if the interface supports it. "
                    "Summarize your current findings and conclude your response."
                )
                if llm_request.contents is None:
                    llm_request.contents = []

                last_call_content = adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text=last_call_text)],
                )
                llm_request.contents.append(last_call_content)
                last_call_notification_message_added = True
                log.info(
                    "%s Added 'last LLM call' notification as a 'model' message to llm_request.contents. Current calls (%d) reached max_llm_calls (%d).",
                    log_identifier,
                    current_llm_calls,
                    max_llm_calls,
                )
    except Exception as e_last_call:
        log.error(
            "%s Error checking/injecting last LLM call notification message: %s",
            log_identifier,
            e_last_call,
        )

    injected_instructions.append(_generate_examples_instruction())

    if injected_instructions:
        combined_instructions = "\n\n---\n\n".join(injected_instructions)
        if llm_request.config is None:
            log.warning(
                "%s llm_request.config is None, cannot append system instructions.",
                log_identifier,
            )
        else:
            if llm_request.config.system_instruction is None:
                llm_request.config.system_instruction = ""

            if llm_request.config.system_instruction:
                llm_request.config.system_instruction += (
                    "\n\n---\n\n" + combined_instructions
                )
            else:
                llm_request.config.system_instruction = combined_instructions
            log.info(
                "%s Injected %d dynamic instruction block(s) into llm_request.config.system_instruction.",
                log_identifier,
                len(injected_instructions),
            )
    elif not last_call_notification_message_added:
        log.debug(
            "%s No dynamic instructions (system or last_call message) were injected based on config.",
            log_identifier,
        )

    return None


async def after_tool_callback_inject_metadata(
    tool: BaseTool,
    args: Dict,
    tool_context: ToolContext,
    tool_response: Dict,
    host_component: "SamAgentComponent",
) -> Optional[Dict]:
    """
    ADK after_tool_callback to automatically load and inject metadata for
    newly created artifacts into the tool's response dictionary.
    """
    log_identifier = f"[Callback:InjectMetadata:{tool.name}]"
    log.info(
        "%s Starting metadata injection for tool response, type: %s",
        log_identifier,
        type(tool_response).__name__,
    )

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot proceed.",
            log_identifier,
        )
        return None

    if not tool_context.actions.artifact_delta:
        log.debug(
            "%s No artifact delta found. Skipping metadata injection.", log_identifier
        )
        return None

    artifact_service: Optional[BaseArtifactService] = (
        tool_context._invocation_context.artifact_service
    )
    if not artifact_service:
        log.error(
            "%s ArtifactService not available. Cannot load metadata.",
            log_identifier,
        )
        return None

    app_name = tool_context._invocation_context.app_name
    user_id = tool_context._invocation_context.user_id
    session_id = get_original_session_id(tool_context._invocation_context)

    metadata_texts = []

    for filename, version in tool_context.actions.artifact_delta.items():
        if filename.endswith(METADATA_SUFFIX):
            log.debug(
                "%s Skipping metadata artifact '%s' itself.", log_identifier, filename
            )
            continue

        metadata_filename = f"{filename}{METADATA_SUFFIX}"
        log.debug(
            "%s Found data artifact '%s' v%d. Attempting to load metadata '%s' v%d.",
            log_identifier,
            filename,
            version,
            metadata_filename,
            version,
        )

        try:
            metadata_part = await artifact_service.load_artifact(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=metadata_filename,
                version=version,
            )

            if metadata_part and metadata_part.inline_data:
                try:
                    metadata_dict = json.loads(
                        metadata_part.inline_data.data.decode("utf-8")
                    )
                    metadata_dict["version"] = version
                    metadata_dict["filename"] = filename
                    formatted_text = format_metadata_for_llm(metadata_dict)
                    metadata_texts.append(formatted_text)
                    log.info(
                        "%s Successfully loaded and formatted metadata for '%s' v%d.",
                        log_identifier,
                        filename,
                        version,
                    )
                except json.JSONDecodeError as json_err:
                    log.warning(
                        "%s Failed to parse metadata JSON for '%s' v%d: %s",
                        log_identifier,
                        metadata_filename,
                        version,
                        json_err,
                    )
                except Exception as fmt_err:
                    log.warning(
                        "%s Failed to format metadata for '%s' v%d: %s",
                        log_identifier,
                        metadata_filename,
                        version,
                        fmt_err,
                    )
            else:
                log.warning(
                    "%s Companion metadata artifact '%s' v%d not found or empty.",
                    log_identifier,
                    metadata_filename,
                    version,
                )

        except Exception as load_err:
            log.error(
                "%s Error loading companion metadata artifact '%s' v%d: %s",
                log_identifier,
                metadata_filename,
                version,
                load_err,
            )

    if metadata_texts:
        if not isinstance(tool_response, dict):
            log.error(
                "%s Tool response is not a dictionary. Cannot inject metadata. Type: %s",
                log_identifier,
                type(tool_response),
            )
            return None

        combined_metadata_text = "\n\n".join(metadata_texts)
        tool_response[METADATA_RESPONSE_KEY] = combined_metadata_text
        log.info(
            "%s Injected metadata for %d artifact(s) into tool response key '%s'.",
            log_identifier,
            len(metadata_texts),
            METADATA_RESPONSE_KEY,
        )
        return tool_response
    else:
        log.debug(
            "%s No metadata loaded or formatted. Returning original tool response.",
            log_identifier,
        )
        return None


async def track_produced_artifacts_callback(
    tool: BaseTool,
    args: Dict,
    tool_context: ToolContext,
    tool_response: Dict,
    host_component: "SamAgentComponent",
) -> Optional[Dict]:
    """
    ADK after_tool_callback to automatically track all artifacts created by a tool.
    It inspects the artifact_delta and registers the created artifacts in the
    TaskExecutionContext.
    """
    log_identifier = f"[Callback:TrackArtifacts:{tool.name}]"
    log.debug("%s Starting artifact tracking for tool response.", log_identifier)

    if not tool_context.actions.artifact_delta:
        log.debug("%s No artifact delta found. Skipping tracking.", log_identifier)
        return None

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot proceed.", log_identifier
        )
        return None

    try:
        a2a_context = tool_context.state.get("a2a_context", {})
        logical_task_id = a2a_context.get("logical_task_id")
        if not logical_task_id:
            log.warning(
                "%s Could not find logical_task_id in tool_context. Cannot track artifacts.",
                log_identifier,
            )
            return None

        with host_component.active_tasks_lock:
            task_context = host_component.active_tasks.get(logical_task_id)

        if not task_context:
            log.warning(
                "%s TaskExecutionContext not found for task %s. Cannot track artifacts.",
                log_identifier,
                logical_task_id,
            )
            return None

        for filename, version in tool_context.actions.artifact_delta.items():
            if filename.endswith(METADATA_SUFFIX):
                continue
            log.info(
                "%s Registering produced artifact '%s' v%d for task %s.",
                log_identifier,
                filename,
                version,
                logical_task_id,
            )
            task_context.register_produced_artifact(filename, version)

    except Exception as e:
        log.exception(
            "%s Error during artifact tracking callback: %s", log_identifier, e
        )

    return None


def log_streaming_chunk_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    host_component: "SamAgentComponent",
) -> Optional[LlmResponse]:
    """
    ADK after_model_callback to log the content of each LLM response chunk
    *after* potential modification by other callbacks (like embed resolution).
    """
    log_identifier = "[Callback:LogChunk]"
    try:
        content_str = "None"
        is_partial = llm_response.partial
        is_final = llm_response.turn_complete
        if llm_response.content and llm_response.content.parts:
            texts = [p.text for p in llm_response.content.parts if p.text]
            content_str = '"' + "".join(texts) + '"' if texts else "[Non-text parts]"
        elif llm_response.error_message:
            content_str = f"[ERROR: {llm_response.error_message}]"

    except Exception as e:
        log.error("%s Error logging LLM chunk: %s", log_identifier, e)

    return None


def solace_llm_invocation_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
    host_component: "SamAgentComponent",
) -> Optional[LlmResponse]:
    """
    ADK before_model_callback to send a Solace message when an LLM is invoked,
    using the host_component's process_and_publish_adk_event method.
    """
    log_identifier = "[Callback:SolaceLLMInvocation]"
    log.debug(
        "%s Running Solace LLM invocation notification callback...", log_identifier
    )

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot send Solace message.",
            log_identifier,
        )
        return None

    callback_context.state[A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY] = False
    log.debug(
        "%s Reset %s to False.", log_identifier, A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY
    )

    try:
        a2a_context = callback_context.state.get("a2a_context")
        if not a2a_context:
            log.error(
                "%s a2a_context not found in callback_context.state. Cannot send Solace message.",
                log_identifier,
            )
            return None

        logical_task_id = a2a_context.get("logical_task_id")
        context_id = a2a_context.get("contextId")

        # Store model name in callback state for later use in response callback
        model_name = host_component.model_config
        if isinstance(model_name, dict):
            model_name = model_name.get("model", "unknown")
        callback_context.state["model_name"] = model_name

        llm_data = LlmInvocationData(request=llm_request.model_dump(exclude_none=True))
        status_update_event = a2a.create_data_signal_event(
            task_id=logical_task_id,
            context_id=context_id,
            signal_data=llm_data,
            agent_name=host_component.agent_name,
        )

        loop = host_component.get_async_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                host_component._publish_status_update_with_buffer_flush(
                    status_update_event,
                    a2a_context,
                    skip_buffer_flush=False,
                ),
                loop,
            )
            log.debug(
                "%s Scheduled LLM invocation status update with buffer flush.",
                log_identifier,
            )
        else:
            log.error(
                "%s Async loop not available. Cannot publish LLM invocation status update.",
                log_identifier,
            )

    except Exception as e:
        log.error(
            "%s Error during Solace LLM invocation notification: %s", log_identifier, e
        )

    return None


def solace_llm_response_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    host_component: "SamAgentComponent",
) -> Optional[LlmResponse]:
    """
    ADK after_model_callback to send a Solace message with the LLM's response
    and token usage information.
    """
    log_identifier = "[Callback:SolaceLLMResponse]"
    if llm_response.partial:  # Don't send partial responses for this notification
        log.debug("%s Skipping partial response", log_identifier)
        return None

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot send Solace message.",
            log_identifier,
        )
        return None

    try:
        a2a_context = callback_context.state.get("a2a_context")
        if not a2a_context:
            log.error(
                "%s a2a_context not found in callback_context.state. Cannot send Solace message.",
                log_identifier,
            )
            return None

        agent_name = host_component.get_config("agent_name", "unknown_agent")
        logical_task_id = a2a_context.get("logical_task_id")

        llm_response_data = {
            "type": "llm_response",
            "data": llm_response.model_dump(exclude_none=True),
        }

        # Extract and record token usage
        if llm_response.usage_metadata:
            usage = llm_response.usage_metadata
            model_name = callback_context.state.get("model_name", "unknown")

            usage_dict = {
                "input_tokens": usage.prompt_token_count,
                "output_tokens": usage.candidates_token_count,
                "model": model_name,
            }

            # Check for cached tokens (provider-specific)
            cached_tokens = 0
            if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
                cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0)
                if cached_tokens > 0:
                    usage_dict["cached_input_tokens"] = cached_tokens

            # Add to response data
            llm_response_data["usage"] = usage_dict

            # Record in task context for aggregation
            with host_component.active_tasks_lock:
                task_context = host_component.active_tasks.get(logical_task_id)

            if task_context:
                task_context.record_token_usage(
                    input_tokens=usage.prompt_token_count,
                    output_tokens=usage.candidates_token_count,
                    model=model_name,
                    source="agent",
                    cached_input_tokens=cached_tokens,
                )
                log.debug(
                    "%s Recorded token usage: input=%d, output=%d, cached=%d, model=%s",
                    log_identifier,
                    usage.prompt_token_count,
                    usage.candidates_token_count,
                    cached_tokens,
                    model_name,
                )

        # This signal doesn't have a dedicated Pydantic model, so we create the
        # DataPart directly and use the lower-level helpers.
        data_part = a2a.create_data_part(data=llm_response_data)
        a2a_message = a2a.create_agent_parts_message(
            parts=[data_part],
            task_id=logical_task_id,
            context_id=a2a_context.get("contextId"),
        )
        status_update_event = a2a.create_status_update(
            task_id=logical_task_id,
            context_id=a2a_context.get("contextId"),
            message=a2a_message,
            is_final=False,
            metadata={"agent_name": agent_name},
        )
        loop = host_component.get_async_loop()
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                host_component._publish_status_update_with_buffer_flush(
                    status_update_event,
                    a2a_context,
                    skip_buffer_flush=False,
                ),
                loop,
            )
            log.debug(
                "%s Scheduled LLM response status update with buffer flush (final_chunk=%s).",
                log_identifier,
                llm_response.turn_complete,
            )
        else:
            log.error(
                "%s Async loop not available. Cannot publish LLM response status update.",
                log_identifier,
            )

    except Exception as e:
        log.error(
            "%s Error during Solace LLM response notification: %s", log_identifier, e
        )

    return None


def notify_tool_invocation_start_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    host_component: "SamAgentComponent",
) -> None:
    """
    ADK before_tool_callback to send an A2A status message indicating
    that a tool is about to be invoked.
    """
    log_identifier = f"[Callback:NotifyToolInvocationStart:{tool.name}]"
    log.debug(
        "%s Triggered for tool '%s' with args: %s", log_identifier, tool.name, args
    )

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot send notification.",
            log_identifier,
        )
        return

    a2a_context = tool_context.state.get("a2a_context")
    if not a2a_context:
        log.error(
            "%s a2a_context not found in tool_context.state. Cannot send notification.",
            log_identifier,
        )
        return

    try:
        serializable_args = {}
        for k, v in args.items():
            try:
                json.dumps(v)
                serializable_args[k] = v
            except TypeError:
                serializable_args[k] = str(v)

        tool_data = ToolInvocationStartData(
            tool_name=tool.name,
            tool_args=serializable_args,
            function_call_id=tool_context.function_call_id,
        )
        asyncio.run_coroutine_threadsafe(
            _publish_data_part_status_update(host_component, a2a_context, tool_data),
            host_component.get_async_loop(),
        )
        log.debug(
            "%s Scheduled tool_invocation_start notification.",
            log_identifier,
        )

    except Exception as e:
        log.exception(
            "%s Error publishing tool_invocation_start status update: %s",
            log_identifier,
            e,
        )

    return None


def notify_tool_execution_result_callback(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
    host_component: "SamAgentComponent",
) -> None:
    """
    ADK after_tool_callback to send an A2A status message with the result
    of a tool's execution.
    """
    log_identifier = f"[Callback:NotifyToolResult:{tool.name}]"
    log.debug("%s Triggered for tool '%s'", log_identifier, tool.name)

    if not host_component:
        log.error(
            "%s Host component instance not provided. Cannot send notification.",
            log_identifier,
        )
        return

    a2a_context = tool_context.state.get("a2a_context")
    if not a2a_context:
        log.error(
            "%s a2a_context not found in tool_context.state. Cannot send notification.",
            log_identifier,
        )
        return

    if tool.is_long_running and not tool_response:
        log.debug(
            "%s Tool is long-running and is not yet complete. Don't notify its completion",
            log_identifier,
        )
        return

    try:
        # Attempt to make the response JSON serializable
        serializable_response = tool_response
        if hasattr(tool_response, "model_dump"):
            serializable_response = tool_response.model_dump(exclude_none=True)
        else:
            try:
                # A simple check to see if it can be dumped.
                # This isn't perfect but catches many non-serializable types.
                json.dumps(tool_response)
            except (TypeError, OverflowError):
                serializable_response = str(tool_response)

        tool_data = ToolResultData(
            tool_name=tool.name,
            result_data=serializable_response,
            function_call_id=tool_context.function_call_id,
        )
        asyncio.run_coroutine_threadsafe(
            _publish_data_part_status_update(host_component, a2a_context, tool_data),
            host_component.get_async_loop(),
        )
        log.debug(
            "%s Scheduled tool_result notification for function call ID %s.",
            log_identifier,
            tool_context.function_call_id,
        )

    except Exception as e:
        log.exception(
            "%s Error publishing tool_result status update: %s",
            log_identifier,
            e,
        )

    return None


def auto_continue_on_max_tokens_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
    host_component: "SamAgentComponent",
) -> Optional[LlmResponse]:
    """
    ADK after_model_callback to automatically continue an LLM response that
    was interrupted. This handles two interruption signals:
    1. The explicit `llm_response.interrupted` flag from the ADK.
    2. An implicit signal where the model itself calls a `_continue` tool.
    """
    log_identifier = "[Callback:AutoContinue]"

    if not host_component.get_config("enable_auto_continuation", True):
        log.debug("%s Auto-continuation is disabled. Skipping.", log_identifier)
        return None

    # An interruption is signaled by either the explicit flag or an implicit tool call.
    was_explicitly_interrupted = llm_response.interrupted
    was_implicitly_interrupted = False
    if llm_response.content and llm_response.content.parts:
        if any(
            p.function_call and p.function_call.name == "_continue"
            for p in llm_response.content.parts
        ):
            was_implicitly_interrupted = True

    if not was_explicitly_interrupted and not was_implicitly_interrupted:
        return None

    log.info(
        "%s Interruption signal detected (explicit: %s, implicit: %s). Triggering auto-continuation.",
        log_identifier,
        was_explicitly_interrupted,
        was_implicitly_interrupted,
    )

    # Get existing parts from the response, but filter out any `_continue` calls
    # the model might have added.
    existing_parts = []
    if llm_response.content and llm_response.content.parts:
        existing_parts = [
            p
            for p in llm_response.content.parts
            if not (p.function_call and p.function_call.name == "_continue")
        ]
        if was_implicitly_interrupted:
            log.debug(
                "%s Removed implicit '_continue' tool call from response parts.",
                log_identifier,
            )

    continue_tool_call = adk_types.FunctionCall(
        name="_continue_generation",
        args={},
        id=f"host-continue-{uuid.uuid4()}",
    )
    continue_part = adk_types.Part(function_call=continue_tool_call)

    all_parts = existing_parts + [continue_part]

    # If there was no text content in the interrupted part, add a space to ensure
    # the event is not filtered out by history processing logic.
    if not any(p.text for p in existing_parts):
        all_parts.insert(0, adk_types.Part(text=" "))
        log.debug(
            "%s Prepended empty text part to ensure event is preserved.", log_identifier
        )

    # Create a new, non-interrupted LlmResponse containing all parts.
    # This ensures the partial text is saved to history and the tool call is executed.
    hijacked_response = LlmResponse(
        content=adk_types.Content(role="model", parts=all_parts),
        partial=False,
        custom_metadata={
            "was_interrupted": True,
        },
    )

    return hijacked_response
