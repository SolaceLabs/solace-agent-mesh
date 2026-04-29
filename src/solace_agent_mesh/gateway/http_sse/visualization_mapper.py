"""
Pure mapping utilities for the visualization SSE stream.

This module exposes the logic that turns a raw broker `(topic, payload)` pair
into the `details` dict consumed by the frontend visualizer (see
`A2AEventSSEPayload` on the frontend). It is intentionally framework-agnostic
so other producers — notably the eval pipeline, which captures the same
broker events but cannot piggyback on the live SSE stream — can reuse it
verbatim and persist results that match the chat shape exactly.
"""

import json
import logging
from typing import Any

from a2a.types import (
    A2ARequest,
    AgentCard,
    JSONRPCResponse,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)

from ...common import a2a

log = logging.getLogger(__name__)


def infer_visualization_event_details(
    topic: str,
    payload: dict[str, Any],
    log_identifier: str = "",
) -> dict[str, Any]:
    """
    Infer details for the visualization SSE payload from a Solace topic and A2A message.

    This implementation parses the official A2A SDK message formats. It is a pure
    function: it does not touch component state and is safe to call from any thread
    or async context. `log_identifier` is an optional prefix for warning logs so the
    caller's context (e.g. component name) shows up in diagnostic output.
    """
    details: dict[str, Any] = {
        "direction": "unknown",
        "source_entity": "unknown",
        "target_entity": "unknown",
        "debug_type": "unknown",
        "message_id": payload.get("id"),
        "task_id": None,
        "payload_summary": {
            "method": payload.get("method", "N/A"),
            "params_preview": None,
        },
    }

    # --- Phase 1: Parse the payload to extract core info ---
    try:
        # Handle SAM Events (system events)
        event_type = payload.get("event_type")
        if event_type:
            details["direction"] = "system_event"
            details["debug_type"] = "sam_event"
            details["payload_summary"]["method"] = event_type
            details["source_entity"] = payload.get("source_component", "unknown")
            details["target_entity"] = "system"
            return details

        # Try to parse as a JSON-RPC response first
        if "result" in payload or "error" in payload:
            rpc_response = JSONRPCResponse.model_validate(payload)
            result = a2a.get_response_result(rpc_response)
            error = a2a.get_response_error(rpc_response)
            details["message_id"] = a2a.get_response_id(rpc_response)

            if result:
                kind = getattr(result, "kind", None)
                details["direction"] = kind or "response"
                details["task_id"] = getattr(result, "task_id", None) or getattr(
                    result, "id", None
                )

                if isinstance(result, TaskStatusUpdateEvent):
                    details["source_entity"] = (
                        result.metadata.get("agent_name")
                        if result.metadata
                        else None
                    )
                    message = a2a.get_message_from_status_update(result)
                    if message:
                        if not details["source_entity"]:
                            details["source_entity"] = (
                                message.metadata.get("agent_name")
                                if message.metadata
                                else None
                            )
                        data_parts = a2a.get_data_parts_from_message(message)
                        if data_parts:
                            details["debug_type"] = data_parts[0].data.get(
                                "type", "unknown"
                            )
                        elif a2a.get_text_from_message(message):
                            details["debug_type"] = "streaming_text"
                elif isinstance(result, Task):
                    details["source_entity"] = (
                        result.metadata.get("agent_name")
                        if result.metadata
                        else None
                    )
                    task_status = a2a.get_task_status(result)
                    # Guard against task_status being an Enum (TaskState) instead of TaskStatus object
                    if (
                        task_status
                        and not isinstance(task_status, TaskState)
                        and hasattr(task_status, "message")
                    ):
                        data_parts = a2a.get_data_parts_from_message(
                            task_status.message
                        )
                        if data_parts:
                            details["debug_type"] = data_parts[0].data.get(
                                "type", "task_result"
                            )
                elif isinstance(result, TaskArtifactUpdateEvent):
                    artifact = a2a.get_artifact_from_artifact_update(result)
                    if artifact:
                        details["source_entity"] = (
                            artifact.metadata.get("agent_name")
                            if artifact.metadata
                            else None
                        )
            elif error:
                details["direction"] = "error_response"
                details["task_id"] = (
                    error.data.get("taskId")
                    if isinstance(error.data, dict)
                    else None
                )
                details["debug_type"] = "error"

        # Try to parse as a JSON-RPC request
        elif "method" in payload:
            rpc_request = A2ARequest.model_validate(payload)
            method = a2a.get_request_method(rpc_request)
            details["direction"] = "request"
            details["payload_summary"]["method"] = method
            details["message_id"] = a2a.get_request_id(rpc_request)

            if method in ["message/send", "message/stream"]:
                details["debug_type"] = method
                message = a2a.get_message_from_send_request(rpc_request)
                details["task_id"] = a2a.get_request_id(rpc_request)
                if message:
                    details["target_entity"] = (
                        message.metadata.get("agent_name")
                        if message.metadata
                        else None
                    )
                    data_parts = a2a.get_data_parts_from_message(message)
                    if data_parts:
                        details["debug_type"] = data_parts[0].data.get(
                            "type", method
                        )
            elif method == "tasks/cancel":
                details["task_id"] = a2a.get_task_id_from_cancel_request(rpc_request)

        # Handle Discovery messages (which are not JSON-RPC)
        elif "/a2a/v1/discovery/" in topic:
            agent_card = AgentCard.model_validate(payload)
            details["direction"] = "discovery"
            details["source_entity"] = agent_card.name
            details["target_entity"] = "broadcast"
            details["message_id"] = None  # Discovery has no ID

    except Exception as e:
        log.warning(
            "[%s] Failed to parse A2A payload for visualization details: %s",
            log_identifier,
            e,
        )

    # --- Phase 2: Refine details using topic information as a fallback ---
    if details["direction"] == "unknown":
        if "request" in topic:
            details["direction"] = "request"
        elif "response" in topic:
            details["direction"] = "response"
        elif "status" in topic:
            details["direction"] = "status_update"
            # TEMP - add debug_type based on the type in the data
            details["debug_type"] = "unknown"

    # --- Phase 3: Create a payload summary ---
    try:
        summary_source = (
            payload.get("result")
            or payload.get("params")
            or payload.get("error")
            or payload
        )
        summary_str = json.dumps(summary_source)
        details["payload_summary"]["params_preview"] = (
            (summary_str[:100] + "...") if len(summary_str) > 100 else summary_str
        )
    except Exception:
        details["payload_summary"]["params_preview"] = "[Could not serialize payload]"

    return details
