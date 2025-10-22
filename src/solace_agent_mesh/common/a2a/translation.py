"""
Helpers for translating between A2A protocol objects and other domains,
such as the Google ADK.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING
import json
import base64
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from google.genai import types as adk_types
from google.adk.events import Event as ADKEvent

from a2a.types import (
    Message as A2AMessage,
    TextPart,
    FilePart,
    FileWithBytes,
    FileWithUri,
    DataPart,
    JSONRPCResponse,
    InternalError,
)

from .. import a2a
from ...agent.utils.context_helpers import get_original_session_id

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from google.adk.artifacts import BaseArtifactService
    from ...agent.sac.component import SamAgentComponent


A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY = "temp:llm_stream_chunks_processed"
A2A_STATUS_SIGNAL_STORAGE_KEY = "temp:a2a_status_signals_collected"


async def _prepare_a2a_filepart_for_adk(
    part: FilePart,
    component: "SamAgentComponent",
    user_id: str,
    session_id: str,
) -> Optional[adk_types.Part]:
    """
    Prepares an incoming A2A FilePart for the ADK by converting it into a
    textual summary of its metadata.

    - If the part has bytes, it saves it to the artifact store first.
    - If the part has a URI, it loads metadata from the store.
    - It then formats this information into a text string for the LLM.
    """
    from ...agent.utils.artifact_helpers import (
        save_artifact_with_metadata,
        load_artifact_content_or_metadata,
        format_metadata_for_llm,
    )

    log_id = f"{component.log_identifier}[PrepareFilePartForADK]"
    app_name = component.get_config("agent_name")
    artifact_service = component.artifact_service

    if not artifact_service:
        log.error(
            "%s Artifact service is not configured. Cannot process FilePart.", log_id
        )
        return adk_types.Part(
            text="[System Note: File part ignored due to missing artifact service.]"
        )

    filename = None
    version = None
    mime_type = None

    try:
        if isinstance(part.file, FileWithBytes):
            log.debug("%s FilePart contains bytes. Saving to artifact store.", log_id)
            filename = part.file.name or f"upload-{uuid.uuid4().hex}"
            mime_type = part.file.mime_type or "application/octet-stream"
            content_bytes = base64.b64decode(part.file.bytes)

            save_result = await save_artifact_with_metadata(
                artifact_service=artifact_service,
                app_name=app_name,
                user_id=user_id,
                session_id=session_id,
                filename=filename,
                content_bytes=content_bytes,
                mime_type=mime_type,
                metadata_dict={"source": "a2a_filepart_upload"},
                timestamp=datetime.now(timezone.utc),
            )
            if save_result["status"] == "success":
                version = save_result["data_version"]
                log.info(
                    "%s Saved incoming file '%s' as version %d.",
                    log_id,
                    filename,
                    version,
                )
            else:
                raise IOError(
                    f"Failed to save artifact and its metadata: {save_result['message']}"
                )

        elif isinstance(part.file, FileWithUri):
            log.debug("%s FilePart contains URI. Loading metadata.", log_id)
            uri = part.file.uri
            parsed_uri = urlparse(uri)
            path_parts = parsed_uri.path.strip("/").split("/")
            if len(path_parts) < 3:
                raise ValueError(f"Invalid artifact URI format: {uri}")
            filename = path_parts[-1]
            version_str = parse_qs(parsed_uri.query).get("version", [None])[0]
            version = int(version_str) if version_str else None
            mime_type = part.file.mime_type

        else:
            raise TypeError("FilePart contains neither bytes nor a valid URI.")

        # At this point, we must have filename and version to proceed
        if filename is None or version is None:
            raise ValueError("Could not determine filename and version for artifact.")

        # Fetch metadata only.
        load_result = await load_artifact_content_or_metadata(
            artifact_service=artifact_service,
            app_name=app_name,
            user_id=user_id,
            session_id=get_original_session_id(session_id),
            filename=filename,
            version=version,
            load_metadata_only=True,
        )

        if load_result["status"] != "success":
            raise RuntimeError(f"Failed to load metadata: {load_result['message']}")

        metadata_dict = load_result.get("metadata", {})
        metadata_dict["filename"] = filename
        metadata_dict["version"] = version

        # Format the final text for the LLM
        formatted_summary = format_metadata_for_llm(metadata_dict)
        final_text = (
            "The user has provided the following file as context for your task. "
            "Use the information contained within its metadata to complete your objective. "
            "You can access the full content using your tools if necessary.\n\n"
            f"{formatted_summary}"
        )
        return adk_types.Part(text=final_text)

    except Exception as e:
        log.exception("%s Error processing FilePart for ADK: %s", log_id, e)
        failed_filename = filename or (part.file.name if part.file else "unknown file")
        return adk_types.Part(
            text=f"[System Note: The file '{failed_filename}' could not be processed. Error: {e}]"
        )


async def translate_a2a_to_adk_content(
    a2a_message: A2AMessage,
    component: "SamAgentComponent",
    user_id: str,
    session_id: str,
) -> adk_types.Content:
    """
    Translates an A2A Message object to ADK Content.
    FileParts are converted to textual metadata summaries.
    """
    adk_parts: List[adk_types.Part] = []
    unwrapped_parts = a2a.get_parts_from_message(a2a_message)
    log_identifier = component.log_identifier

    for part in unwrapped_parts:
        try:
            if isinstance(part, TextPart):
                adk_parts.append(adk_types.Part(text=a2a.get_text_from_text_part(part)))
            elif isinstance(part, FilePart):
                adk_part = await _prepare_a2a_filepart_for_adk(
                    part, component, user_id, session_id
                )
                if adk_part:
                    adk_parts.append(adk_part)
            elif isinstance(part, DataPart):
                try:
                    data_str = json.dumps(a2a.get_data_from_data_part(part), indent=2)
                    adk_parts.append(
                        adk_types.Part(text=f"Received data:\n```json\n{data_str}\n```")
                    )
                except Exception as e:
                    log.warning(
                        "%s Could not serialize DataPart for ADK: %s",
                        log_identifier,
                        e,
                    )
                    adk_parts.append(
                        adk_types.Part(text="Received unserializable structured data.")
                    )
            else:
                log.warning(
                    "%s Unsupported A2A part type: %s", log_identifier, type(part)
                )
        except Exception as e:
            log.exception("%s Error translating A2A part: %s", log_identifier, e)
            adk_parts.append(adk_types.Part(text="[Error processing received part]"))

    adk_role = "user" if a2a_message.role == "user" else "model"
    return adk_types.Content(role=adk_role, parts=adk_parts)


def translate_adk_function_response_to_a2a_parts(
    adk_part: adk_types.Part,
) -> List[a2a.ContentPart]:
    """
    Translates an ADK Part containing a function_response into a list of A2A Parts.
    - If the response is a dict, it becomes a DataPart.
    - Otherwise, it becomes a TextPart.
    """
    if not adk_part.function_response:
        return []

    a2a_parts: List[a2a.ContentPart] = []
    try:
        response_data = adk_part.function_response.response
        tool_name = adk_part.function_response.name
        if isinstance(response_data, dict):
            a2a_parts.append(
                a2a.create_data_part(
                    data=response_data,
                    metadata={"tool_name": tool_name},
                )
            )
        else:
            a2a_parts.append(
                a2a.create_text_part(
                    text=f"Tool {tool_name} result: {str(response_data)}"
                )
            )
    except Exception:
        # Ensure tool_name is available even if accessing .response fails
        tool_name = "unknown_tool"
        if hasattr(adk_part.function_response, "name"):
            tool_name = adk_part.function_response.name
        a2a_parts.append(
            a2a.create_text_part(text=f"[Tool {tool_name} result omitted]")
        )
    return a2a_parts


def _extract_text_from_parts(parts: List[a2a.ContentPart]) -> str:
    """
    Extracts and combines text/file info from a list of A2A parts
    into a single string for display or logging.

    Note: This function intentionally ignores DataPart types.
    """
    output_parts = []
    for part in parts:
        if isinstance(part, TextPart):
            output_parts.append(a2a.get_text_from_text_part(part))
        elif isinstance(part, DataPart):
            log.debug("Skipping DataPart in _extract_text_from_parts")
            continue
        elif isinstance(part, FilePart):
            file = a2a.get_file_from_file_part(part)
            file_info = "File: '%s' (%s)" % (
                a2a.get_filename_from_file_part(part) or "unknown",
                a2a.get_mimetype_from_file_part(part) or "unknown",
            )
            if isinstance(file, FileWithUri) and a2a.get_uri_from_file_part(part):
                file_info += " URI: %s" % a2a.get_uri_from_file_part(part)
            elif isinstance(file, FileWithBytes) and a2a.get_bytes_from_file_part(part):
                try:
                    size = len(base64.b64decode(a2a.get_bytes_from_file_part(part)))
                    file_info += " (Size: %d bytes)" % size
                except Exception:
                    file_info += " (Encoded Bytes)"
            output_parts.append(file_info)
        else:
            if isinstance(part, dict):
                part_type = part.get("type")
                if part_type == "text":
                    output_parts.append(part.get("text", "[Missing text content]"))
                elif part_type == "data":
                    log.debug("Skipping DataPart (dict) in _extract_text_from_parts")
                    continue
                elif part_type == "file":
                    file_content = part.get("file", {})
                    file_info = "File: '%s' (%s)" % (
                        file_content.get("name", "unknown"),
                        file_content.get("mime_type", "unknown"),
                    )
                    if file_content.get("uri"):
                        file_info += " URI: %s" % file_content["uri"]
                    elif file_content.get("bytes"):
                        try:
                            size = len(base64.b64decode(file_content["bytes"]))
                            file_info += " (Size: %d bytes)" % size
                        except Exception:
                            file_info += " (Encoded Bytes)"
                    output_parts.append(file_info)
                else:
                    output_parts.append(
                        "[Unsupported part type in dict: %s]" % part_type
                    )
            else:
                output_parts.append("[Unsupported part type: %s]" % type(part))

    return "\n".join(output_parts)


def format_adk_event_as_a2a(
    adk_event: ADKEvent,
    a2a_context: Dict,
    log_identifier: str,
) -> Tuple[Optional[JSONRPCResponse], List[Tuple[int, Any]]]:
    """
    Translates an intermediate ADK Event (containing content or errors during the run)
    into an A2A JSON-RPC message payload (TaskStatusUpdateEvent or InternalError).
    Also extracts any "a2a_status_signals_collected" from the event's state_delta.
    Returns None if the event should not result in an intermediate A2A message (e.g., empty, non-streaming final).
    Artifact updates are handled separately by the calling component.

    Note: This function preserves DataPart from function responses.
    """
    jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
    logical_task_id = a2a_context.get("logical_task_id")
    is_streaming = a2a_context.get("is_streaming", False)

    if adk_event.error_code or adk_event.error_message:
        error_msg = f"Agent error during execution: {adk_event.error_message or adk_event.error_code}"
        log.error("%s ADK Event contains error: %s", log_identifier, error_msg)
        a2a_error = InternalError(
            message=error_msg,
            data={
                "adk_error_code": adk_event.error_code,
                "taskId": logical_task_id,
            },
        )
        return JSONRPCResponse(id=jsonrpc_request_id, error=a2a_error), []

    signals_to_forward: List[Tuple[int, Any]] = []
    is_final_adk_event = (
        # We have a different definition of final for ADK events:
        # For now, the only long running tool IDs are peer agent tasks, which we
        # need to wait for before considering the event final.
        adk_event.is_final_response()
        and (
            not hasattr(adk_event, "long_running_tool_ids")
            or not adk_event.long_running_tool_ids
        )
    )

    unwrapped_a2a_parts: List[a2a.ContentPart] = []
    if adk_event.content and adk_event.content.parts:
        for part in adk_event.content.parts:
            try:
                if part.text:
                    unwrapped_a2a_parts.append(a2a.create_text_part(text=part.text))
                elif part.inline_data:
                    log.debug(
                        "%s Skipping ADK inline_data part in status update translation.",
                        log_identifier,
                    )
                elif part.function_call or part.function_response:
                    log.debug(
                        "%s Skipping ADK function call part in A2A translation.",
                        log_identifier,
                    )
                else:
                    log.warning(
                        "%s Skipping unknown ADK part type during A2A translation: %s",
                        log_identifier,
                        part,
                    )
            except Exception as e:
                log.exception("%s Error translating ADK part: %s", log_identifier, e)
                unwrapped_a2a_parts.append(
                    a2a.create_text_part(text="[Error processing agent output part]")
                )

    if is_final_adk_event and not is_streaming:
        if not unwrapped_a2a_parts:
            log.debug(
                "%s Skipping non-streaming final ADK event %s with no content in format_adk_event_as_a2a.",
                log_identifier,
                adk_event.id,
            )
            return None, signals_to_forward
        else:
            log.debug(
                "%s Processing non-streaming final ADK event %s with content in format_adk_event_as_a2a.",
                log_identifier,
                adk_event.id,
            )

    should_send_status = (is_streaming and bool(unwrapped_a2a_parts)) or (
        is_final_adk_event and bool(unwrapped_a2a_parts)
    )

    if not should_send_status:
        log.debug(
            "%s ADK event %s resulted in no intermediate A2A status update to send. Skipping.",
            log_identifier,
            adk_event.id,
        )
        return None, signals_to_forward

    a2a_message = a2a.create_agent_parts_message(
        parts=unwrapped_a2a_parts,
        message_id=uuid.uuid4().hex,
    )
    is_final_update_for_this_event = is_final_adk_event

    host_agent_name = a2a_context.get("host_agent_name", "unknown_agent")
    event_metadata = {"agent_name": host_agent_name}

    intermediate_result_obj = a2a.create_status_update(
        task_id=logical_task_id,
        context_id=a2a_context.get("contextId"),
        message=a2a_message,
        is_final=is_final_update_for_this_event,
        metadata=event_metadata,
    )
    log.debug(
        "%s Formatting intermediate A2A response (TaskStatusUpdateEvent, final=%s) for Task ID %s",
        log_identifier,
        is_final_update_for_this_event,
        logical_task_id,
    )
    json_rpc_response_obj = JSONRPCResponse(
        id=jsonrpc_request_id, result=intermediate_result_obj
    )
    return json_rpc_response_obj, signals_to_forward


async def format_and_route_adk_event(
    adk_event: ADKEvent,
    a2a_context: Dict,
    component,
) -> Tuple[Optional[Dict], Optional[str], Optional[Dict], List[Tuple[int, Any]]]:
    """
    Formats an intermediate ADK event (content or error) to an A2A payload dict,
    and determines the target status topic.
    Returns (None, None, []) if no intermediate message should be sent.
    Signal extraction from state_delta is REMOVED as it's handled upstream by SamAgentComponent.
    Final responses and artifact updates are handled elsewhere.
    """
    signals_found: List[Tuple[int, Any]] = []
    try:
        a2a_response_obj, _ = format_adk_event_as_a2a(
            adk_event, a2a_context, component.log_identifier
        )

        if not a2a_response_obj:
            return None, None, None, []

        a2a_payload = a2a_response_obj.model_dump(exclude_none=True)
        target_topic = None
        logical_task_id = a2a_context.get("logical_task_id")
        peer_status_topic = a2a_context.get("statusTopic")
        namespace = component.get_config("namespace")

        if peer_status_topic:
            target_topic = peer_status_topic
            log.debug(
                "%s Determined status update topic (to peer delegator): %s",
                component.log_identifier,
                target_topic,
            )
        else:
            gateway_id = component.get_gateway_id()
            target_topic = a2a.get_gateway_status_topic(
                namespace, gateway_id, logical_task_id
            )
            log.debug(
                "%s Determined status update topic (to gateway): %s",
                component.log_identifier,
                target_topic,
            )

        user_properties = {}
        if a2a_context.get("a2a_user_config"):
            user_properties["a2aUserConfig"] = a2a_context["a2a_user_config"]

        return a2a_payload, target_topic, user_properties, signals_found

    except Exception as e:
        log.exception(
            "%s Error formatting or routing intermediate ADK event %s: %s",
            component.log_identifier,
            adk_event.id,
            e,
        )
        try:
            jsonrpc_request_id = a2a_context.get("jsonrpc_request_id")
            logical_task_id = a2a_context.get("logical_task_id")
            namespace = component.get_config("namespace")
            gateway_id = component.get_gateway_id()
            peer_reply_topic = a2a_context.get("replyToTopic")

            error_response = JSONRPCResponse(
                id=jsonrpc_request_id,
                error=InternalError(
                    message=f"Error processing agent event: {e}",
                    data={"taskId": logical_task_id},
                ),
            )
            if peer_reply_topic:
                target_topic = peer_reply_topic
            else:
                target_topic = a2a.get_gateway_response_topic(
                    namespace, gateway_id, logical_task_id
                )
            user_properties = {}
            if a2a_context.get("a2a_user_config"):
                user_properties["a2aUserConfig"] = a2a_context["a2a_user_config"]

            return (
                error_response.model_dump(exclude_none=True),
                target_topic,
                user_properties,
                [],
            )
        except Exception as inner_e:
            log.error(
                "%s Failed to generate error response after formatting error: %s",
                component.log_identifier,
                inner_e,
            )
            return None, None, None, []


async def translate_adk_part_to_a2a_filepart(
    adk_part: adk_types.Part,
    filename: str,
    a2a_context: Dict,
    artifact_service: "BaseArtifactService",
    artifact_handling_mode: str,
    adk_app_name: str,
    log_identifier: str,
    version: Optional[int] = None,
) -> Optional[FilePart]:
    """
    Translates a loaded ADK Part (with inline_data) to an A2A FilePart
    based on the configured artifact_handling_mode.
    If version is not provided, it will be resolved to the latest.
    """
    from ...common.utils.artifact_utils import get_latest_artifact_version
    from a2a.types import FilePart, FileWithBytes, FileWithUri

    if artifact_handling_mode == "ignore":
        log.debug(
            "%s Artifact handling mode is 'ignore'. Skipping translation for '%s'.",
            log_identifier,
            filename,
        )
        return None

    if not adk_part or not adk_part.inline_data:
        log.warning(
            "%s Cannot translate artifact '%s': ADK Part is missing or has no inline_data.",
            log_identifier,
            filename,
        )
        return None

    resolved_version = version
    if resolved_version is None:
        try:
            resolved_version = await get_latest_artifact_version(
                artifact_service=artifact_service,
                app_name=adk_app_name,
                user_id=a2a_context.get("user_id"),
                session_id=a2a_context.get("session_id"),
                filename=filename,
            )
            if resolved_version is None:
                log.error(
                    "%s Could not resolve latest version for artifact '%s'.",
                    log_identifier,
                    filename,
                )
                return None
        except Exception as e:
            log.exception(
                "%s Failed to resolve latest version for artifact '%s': %s",
                log_identifier,
                filename,
                e,
            )
            return None

    mime_type = adk_part.inline_data.mime_type
    data_bytes = adk_part.inline_data.data
    file_content: Optional[Union[FileWithBytes, FileWithUri]] = None

    try:
        if artifact_handling_mode == "embed":
            encoded_bytes = base64.b64encode(data_bytes).decode("utf-8")
            file_content = FileWithBytes(
                name=filename, mime_type=mime_type, bytes=encoded_bytes
            )
            log.debug(
                "%s Embedding artifact '%s' (size: %d bytes) for A2A message.",
                log_identifier,
                filename,
                len(data_bytes),
            )

        elif artifact_handling_mode == "reference":
            user_id = a2a_context.get("user_id")
            original_session_id = a2a_context.get("session_id")

            if not all([adk_app_name, user_id, original_session_id]):
                log.error(
                    "%s Cannot create artifact reference URI: missing context (app_name, user_id, or session_id).",
                    log_identifier,
                )
                return None

            artifact_uri = f"artifact://{adk_app_name}/{user_id}/{original_session_id}/{filename}?version={resolved_version}"

            log.info(
                "%s Creating reference URI for artifact: %s",
                log_identifier,
                artifact_uri,
            )
            file_content = FileWithUri(
                name=filename, mime_type=mime_type, uri=artifact_uri
            )

        if file_content:
            return FilePart(file=file_content)
        else:
            log.warning(
                "%s No FileContent created for artifact '%s' despite mode '%s'.",
                log_identifier,
                filename,
                artifact_handling_mode,
            )
            return None

    except Exception as e:
        log.exception(
            "%s Error translating artifact '%s' to A2A FilePart (mode: %s): %s",
            log_identifier,
            filename,
            artifact_handling_mode,
            e,
        )
        return None
