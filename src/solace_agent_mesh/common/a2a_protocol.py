"""
Handles A2A topic construction and translation between A2A and ADK message formats.
Consolidated from src/a2a_adk_host/a2a_protocol.py and src/tools/common/a2a_protocol.py.
"""

from typing import Any, Dict, List, Optional, Tuple
import json
import base64
import re
from datetime import datetime, timezone
from solace_ai_connector.common.log import log
from google.genai import types as adk_types
from google.adk.events import Event as ADKEvent

from .types import (
    Message as A2AMessage,
    TextPart,
    FilePart,
    DataPart,
    Part as A2APart,
    JSONRPCResponse,
    InternalError,
    TaskStatus,
    TaskState,
    TaskStatusUpdateEvent,
)

A2A_VERSION = "v1"
A2A_BASE_PATH = f"a2a/{A2A_VERSION}"
A2A_LLM_STREAM_CHUNKS_PROCESSED_KEY = "temp:llm_stream_chunks_processed"
A2A_STATUS_SIGNAL_STORAGE_KEY = "temp:a2a_status_signals_collected"


def get_a2a_base_topic(namespace: str) -> str:
    """Returns the base topic prefix for all A2A communication."""
    if not namespace:
        raise ValueError("A2A namespace cannot be empty.")
    return f"{namespace.rstrip('/')}/{A2A_BASE_PATH}"


def get_discovery_topic(namespace: str) -> str:
    """Returns the topic for agent card discovery."""
    return f"{get_a2a_base_topic(namespace)}/discovery/agentcards"


def get_agent_request_topic(namespace: str, agent_name: str) -> str:
    """Returns the topic for sending requests to a specific agent."""
    if not agent_name:
        raise ValueError("Agent name cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/agent/request/{agent_name}"


def get_gateway_status_topic(namespace: str, gateway_id: str, task_id: str) -> str:
    """
    Returns the specific topic for an agent to publish status updates TO a specific gateway instance.
    """
    if not gateway_id:
        raise ValueError("Gateway ID cannot be empty.")
    if not task_id:
        raise ValueError("Task ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/gateway/status/{gateway_id}/{task_id}"


def get_gateway_response_topic(namespace: str, gateway_id: str, task_id: str) -> str:
    """
    Returns the specific topic for an agent to publish the final response TO a specific gateway instance.
    Includes task_id for potential correlation/filtering, though gateway might subscribe more broadly.
    """
    if not gateway_id:
        raise ValueError("Gateway ID cannot be empty.")
    if not task_id:
        raise ValueError("Task ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/gateway/response/{gateway_id}/{task_id}"


def get_gateway_status_subscription_topic(namespace: str, self_gateway_id: str) -> str:
    """
    Returns the wildcard topic for a gateway instance to subscribe to receive status updates
    intended for it.
    """
    if not self_gateway_id:
        raise ValueError("Gateway ID is required for gateway status subscription")
    return f"{get_a2a_base_topic(namespace)}/gateway/status/{self_gateway_id}/>"


def get_gateway_response_subscription_topic(
    namespace: str, self_gateway_id: str
) -> str:
    """
    Returns the wildcard topic for a gateway instance to subscribe to receive final responses
    intended for it.
    """
    if not self_gateway_id:
        raise ValueError("Gateway ID is required for gateway response subscription")
    return f"{get_a2a_base_topic(namespace)}/gateway/response/{self_gateway_id}/>"


def get_peer_agent_status_topic(
    namespace: str, delegating_agent_name: str, sub_task_id: str
) -> str:
    """
    Returns the topic for publishing status updates for a sub-task *back to the delegating agent*.
    This topic includes the delegating agent's name.
    """
    if not delegating_agent_name:
        raise ValueError("delegating_agent_name is required for peer status topic")
    return f"{get_a2a_base_topic(namespace)}/agent/status/{delegating_agent_name}/{sub_task_id}"


def get_agent_response_topic(
    namespace: str, delegating_agent_name: str, sub_task_id: str
) -> str:
    """
    Returns the specific topic for publishing the final response for a sub-task
    back to the delegating agent. Includes the delegating agent's name.
    """
    if not delegating_agent_name:
        raise ValueError("delegating_agent_name is required for peer response topic")
    if not sub_task_id:
        raise ValueError("sub_task_id is required for peer response topic")
    return f"{get_a2a_base_topic(namespace)}/agent/response/{delegating_agent_name}/{sub_task_id}"


def get_agent_response_subscription_topic(namespace: str, self_agent_name: str) -> str:
    """
    Returns the wildcard topic for an agent to subscribe to receive responses
    for tasks it delegated. Includes the agent's own name.
    """
    if not self_agent_name:
        raise ValueError("self_agent_name is required for agent response subscription")
    return f"{get_a2a_base_topic(namespace)}/agent/response/{self_agent_name}/>"


def get_agent_status_subscription_topic(namespace: str, self_agent_name: str) -> str:
    """
    Returns the wildcard topic for an agent to subscribe to receive status updates
    for tasks it delegated. Includes the agent's own name.
    """
    if not self_agent_name:
        raise ValueError("self_agent_name is required for agent status subscription")
    return f"{get_a2a_base_topic(namespace)}/agent/status/{self_agent_name}/>"


def get_client_response_topic(namespace: str, client_id: str) -> str:
    """Returns the topic for publishing the final response TO a specific client."""
    if not client_id:
        raise ValueError("Client ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/client/response/{client_id}"


def get_client_status_topic(namespace: str, client_id: str, task_id: str) -> str:
    """
    Returns the specific topic for publishing status updates for a task *to the original client*.
    This topic is client and task-specific.
    """
    if not client_id:
        raise ValueError("Client ID cannot be empty.")
    if not task_id:
        raise ValueError("Task ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/client/status/{client_id}/{task_id}"


def get_client_status_subscription_topic(namespace: str, client_id: str) -> str:
    """
    Returns the wildcard topic for a client to subscribe to receive status updates
    for tasks it initiated. Includes the client's own ID.
    """
    if not client_id:
        raise ValueError("Client ID cannot be empty.")
    return f"{get_a2a_base_topic(namespace)}/client/status/{client_id}/>"


def _subscription_to_regex(subscription: str) -> str:
    """Converts a Solace topic subscription string to a regex pattern."""
    # Escape regex special characters except for Solace wildcards
    pattern = re.escape(subscription)
    # Replace Solace single-level wildcard '*' with regex equivalent '[^/]+'
    pattern = pattern.replace(r"\*", r"[^/]+")
    # Replace Solace multi-level wildcard '>' at the end with regex equivalent '.*'
    if pattern.endswith(r"/>"):
        pattern = pattern[:-1] + r".*"  # Remove escaped '>' and add '.*'
    return pattern


def _topic_matches_subscription(topic: str, subscription: str) -> bool:
    """Checks if a topic matches a Solace subscription pattern."""
    regex_pattern = _subscription_to_regex(subscription)
    return re.fullmatch(regex_pattern, topic) is not None


def translate_a2a_to_adk_content(
    a2a_message: A2AMessage, log_identifier: str
) -> adk_types.Content:
    """Translates an A2A Message object to ADK Content."""
    adk_parts: List[adk_types.Part] = []
    for part in a2a_message.parts:
        try:
            if isinstance(part, TextPart):
                adk_parts.append(adk_types.Part(text=part.text))
            elif isinstance(part, FilePart):
                file_info = f"Received file: name='{part.file.name}', mimeType='{part.file.mimeType}'"
                if part.file.uri:
                    file_info += f", uri='{part.file.uri}'"
                elif part.file.bytes:
                    try:
                        byte_len = len(base64.b64decode(part.file.bytes))
                        file_info += f", size={byte_len} bytes (base64 encoded)"
                    except Exception:
                        file_info += ", size=unknown (base64 encoded)"
                adk_parts.append(adk_types.Part(text=file_info))
            elif isinstance(part, DataPart):
                try:
                    data_str = json.dumps(part.data, indent=2)
                    adk_parts.append(
                        adk_types.Part(text=f"Received data:\n```json\n{data_str}\n```")
                    )
                except Exception as e:
                    log.warning(
                        "%s Could not serialize DataPart for ADK: %s", log_identifier, e
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


def _extract_text_from_parts(parts: List[A2APart]) -> str:
    """
    Extracts and combines text/file info from a list of A2A parts
    into a single string for display or logging.

    Note: This function intentionally ignores DataPart types.
    """
    output_parts = []
    for part in parts:
        if isinstance(part, TextPart):
            output_parts.append(part.text)
        elif isinstance(part, DataPart):
            log.debug("Skipping DataPart in _extract_text_from_parts")
            continue
        elif isinstance(part, FilePart):
            file_info = "File: '%s' (%s)" % (
                part.file.name or "unknown",
                part.file.mimeType or "unknown",
            )
            if part.file.uri:
                file_info += " URI: %s" % part.file.uri
            elif part.file.bytes:
                try:
                    size = len(base64.b64decode(part.file.bytes))
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
                        file_content.get("mimeType", "unknown"),
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
        and (not hasattr(adk_event, 'long_running_tool_ids') or not adk_event.long_running_tool_ids)
    )

    a2a_parts: List[A2APart] = []
    if adk_event.content and adk_event.content.parts:
        for part in adk_event.content.parts:
            try:
                if part.text:
                    a2a_parts.append(TextPart(text=part.text))
                elif part.inline_data:
                    log.debug(
                        "%s Skipping ADK inline_data part in status update translation.",
                        log_identifier,
                    )
                elif part.function_call:
                    log.debug(
                        "%s Skipping ADK function call part in A2A translation.",
                        log_identifier,
                    )
                elif part.function_response:
                    try:
                        response_data = part.function_response.response
                        tool_metadata = {
                            "tool_name": part.function_response.name,
                            "function_call_id": part.function_response.id,
                            "status_from_tool": "success",
                        }
                        if isinstance(response_data, dict):
                            a2a_parts.append(
                                DataPart(data=response_data, metadata=tool_metadata)
                            )
                        elif isinstance(response_data, str):
                            a2a_parts.append(
                                DataPart(
                                    data={"text": response_data}, metadata=tool_metadata
                                )
                            )
                        else:
                            a2a_parts.append(
                                DataPart(
                                    data={"value": str(response_data)},
                                    metadata=tool_metadata,
                                )
                            )
                    except Exception as func_resp_ex:
                        log.warning(
                            "%s Could not process function response for tool %s: %s. Creating error TextPart.",
                            log_identifier,
                            part.function_response.name,
                            func_resp_ex,
                        )
                        a2a_parts.append(
                            TextPart(
                                text=f"[Error processing tool response for {part.function_response.name}: {func_resp_ex}]"
                            )
                        )
                else:
                    log.warning(
                        "%s Skipping unknown ADK part type during A2A translation: %s",
                        log_identifier,
                        part,
                    )
            except Exception as e:
                log.exception("%s Error translating ADK part: %s", log_identifier, e)
                a2a_parts.append(TextPart(text="[Error processing agent output part]"))

    if is_final_adk_event and not is_streaming:
        if not a2a_parts:
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

    is_function_response_event = any(
        p.function_response
        for p in (adk_event.content.parts if adk_event.content else [])
    )
    should_send_status = (
        (is_streaming and bool(a2a_parts))
        or is_function_response_event
        or (is_final_adk_event and bool(a2a_parts))
    )

    if not should_send_status:
        log.debug(
            "%s ADK event %s resulted in no intermediate A2A status update to send. Skipping.",
            log_identifier,
            adk_event.id,
        )
        return None, signals_to_forward

    message_metadata = None
    if is_function_response_event:
        message_metadata = {"type": "tool_response_content"}
        log.debug(
            "%s Prepared message metadata for tool_response_content.", log_identifier
        )

    a2a_message = A2AMessage(role="agent", parts=a2a_parts, metadata=message_metadata)
    task_status = TaskStatus(
        state=TaskState.WORKING,
        message=a2a_message,
        timestamp=datetime.now(timezone.utc),
    )

    is_final_update_for_this_event = is_final_adk_event

    host_agent_name = a2a_context.get("host_agent_name", "unknown_agent")
    event_metadata = {"agent_name": host_agent_name}

    intermediate_result_obj = TaskStatusUpdateEvent(
        id=logical_task_id,
        status=task_status,
        final=is_final_update_for_this_event,
        metadata=event_metadata,
    )
    log.debug(
        "%s Formatting intermediate A2A response (TaskStatusUpdateEvent, final=%s) for Task ID %s. Event type: %s",
        log_identifier,
        is_final_update_for_this_event,
        logical_task_id,
        message_metadata.get("type") if message_metadata else "llm_stream_chunk",
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
            target_topic = get_gateway_status_topic(
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
                target_topic = get_gateway_response_topic(
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
