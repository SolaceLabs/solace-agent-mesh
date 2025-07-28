"""
This module contains functions for translating between the legacy SAM A2A protocol
and the modern, standardized A2A protocol.
"""

import uuid
from typing import Any, Dict

import a2a.types as modern_types
from a2a.types import (
    CancelTaskRequest,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    SendMessageRequest,
    SendStreamingMessageRequest,
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
