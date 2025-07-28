"""
This module contains functions for translating between the legacy SAM A2A protocol
and the modern, standardized A2A protocol.
"""

import uuid
from typing import Any, Dict, Union

import a2a.types as modern_types
from a2a.types import (
    CancelTaskRequest,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task as ModernTask,
    TaskArtifactUpdateEvent as ModernTaskArtifactUpdateEvent,
    TaskStatusUpdateEvent as ModernTaskStatusUpdateEvent,
)
from pydantic import TypeAdapter
from solace_ai_connector.common.log import log

# This maps legacy methods to their modern equivalents.
METHOD_MAP = {
    "tasks/send": "message/send",
    "tasks/sendSubscribe": "message/stream",
}


def translate_sam_to_modern_request(
    legacy_payload: Dict[str, Any]
) -> modern_types.A2ARequest:
    """
    Translates a legacy SAM A2A request payload to the modern A2A spec.

    Args:
        legacy_payload: The incoming request dictionary from a legacy SAM component.

    Returns:
        A validated Pydantic model instance conforming to the modern A2A spec.

    Raises:
        ValueError: If the method is unknown or translation fails.
        pydantic.ValidationError: If the constructed modern request is invalid.
    """
    log_identifier = "[A2ATranslation:Inbound]"
    legacy_method = legacy_payload.get("method")
    modern_method = METHOD_MAP.get(legacy_method)

    if not modern_method:
        # For methods that are compatible or don't need translation (e.g., tasks/cancel),
        # we can try to validate directly.
        if legacy_method == "tasks/cancel":
            log.debug("%s Passing through compatible method '%s'.", log_identifier, legacy_method)
            return CancelTaskRequest.model_validate(legacy_payload)
        raise ValueError(f"Unknown or untranslatable legacy method: {legacy_method}")

    log.info(
        "%s Translating legacy method '%s' to modern method '%s'.",
        log_identifier,
        legacy_method,
        modern_method,
    )

    legacy_params = legacy_payload.get("params", {})
    legacy_message = legacy_params.get("message", {})

    # 2.3.2: Create modern Message
    modern_message = Message(
        message_id=str(uuid.uuid4()),
        task_id=legacy_params.get("id"),
        context_id=legacy_params.get("sessionId"),
        role=legacy_message.get("role"),
        parts=legacy_message.get("parts", []),
        metadata=legacy_message.get("metadata"),
    )

    # 2.3.3: Create modern MessageSendConfiguration
    push_notification_config = None
    if legacy_params.get("pushNotification"):
        push_notification_config = modern_types.PushNotificationConfig(
            **legacy_params["pushNotification"]
        )

    modern_config = MessageSendConfiguration(
        push_notification_config=push_notification_config,
        history_length=legacy_params.get("historyLength"),
        blocking=True,  # Legacy SAM protocol implies blocking behavior
    )

    # 2.3.4: Create modern MessageSendParams
    modern_params = MessageSendParams(
        message=modern_message,
        configuration=modern_config,
        metadata=legacy_params.get("metadata"),
    )

    # 2.4: Request Assembly
    if modern_method == "message/send":
        return SendMessageRequest(
            id=legacy_payload.get("id"),
            params=modern_params,
        )
    elif modern_method == "message/stream":
        return SendStreamingMessageRequest(
            id=legacy_payload.get("id"),
            params=modern_params,
        )
    else:
        # This case should not be reached due to the initial check
        raise ValueError(f"Internal error: No constructor for method {modern_method}")


def translate_modern_to_sam_response(
    modern_event: Union[
        ModernTask, ModernTaskStatusUpdateEvent, ModernTaskArtifactUpdateEvent
    ]
) -> Dict[str, Any]:
    """
    Translates a modern A2A response/event object to a legacy SAM A2A dictionary.

    Args:
        modern_event: The modern Pydantic event object from the a2a-python SDK.

    Returns:
        A dictionary conforming to the legacy SAM A2A protocol structure.
    """
    log_identifier = "[A2ATranslation:Outbound]"

    # Get a dictionary representation of the modern object
    modern_dict = modern_event.model_dump(mode="json", exclude_none=True)
    legacy_dict = modern_dict.copy()  # Start with a copy

    if isinstance(modern_event, ModernTask):
        log.debug("%s Translating modern Task to legacy Task.", log_identifier)
        if "context_id" in legacy_dict:
            legacy_dict["sessionId"] = legacy_dict.pop("context_id")
        # Note: Message structure is compatible enough that recursive translation
        # of history/status.message is not needed for field mapping.
        return legacy_dict

    elif isinstance(modern_event, ModernTaskStatusUpdateEvent):
        log.debug(
            "%s Translating modern TaskStatusUpdateEvent to legacy.", log_identifier
        )
        if "task_id" in legacy_dict:
            legacy_dict["id"] = legacy_dict.pop("task_id")
        if "context_id" in legacy_dict:
            del legacy_dict["context_id"]  # No equivalent in legacy event
        return legacy_dict

    elif isinstance(modern_event, ModernTaskArtifactUpdateEvent):
        log.debug(
            "%s Translating modern TaskArtifactUpdateEvent to legacy.", log_identifier
        )
        if "task_id" in legacy_dict:
            legacy_dict["id"] = legacy_dict.pop("task_id")
        if "context_id" in legacy_dict:
            del legacy_dict["context_id"]  # No equivalent in legacy event
        return legacy_dict

    else:
        log.warning(
            "%s Received unhandled modern event type for translation: %s",
            log_identifier,
            type(modern_event).__name__,
        )
        # Return the original dict as a fallback
        return modern_dict
