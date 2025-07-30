"""
This module contains functions for translating between the legacy SAM A2A protocol
and the modern, standardized A2A protocol.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

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

from ....common import types as sam_types

# This maps legacy methods to their modern equivalents.
METHOD_MAP = {
    "tasks/send": "message/send",
    "tasks/sendSubscribe": "message/stream",
}


def _translate_modern_parts_to_sam(parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Recursively translates modern Part dictionaries to legacy SAM format."""
    if not parts:
        return []
    translated_parts = []
    for part in parts:
        translated_part = part.copy()
        if "kind" in translated_part:
            translated_part["type"] = translated_part.pop("kind")

        if (
            translated_part.get("type") == "file"
            and "file" in translated_part
            and isinstance(translated_part["file"], dict)
        ):
            file_content = translated_part["file"]
            if "mime_type" in file_content:
                file_content["mimeType"] = file_content.pop("mime_type")

        translated_parts.append(translated_part)
    return translated_parts


def translate_modern_card_to_sam_card(
    modern_card: modern_types.AgentCard,
) -> sam_types.AgentCard:
    """
    Translates a modern A2A AgentCard to the legacy SAM AgentCard format.

    Args:
        modern_card: The agent card object conforming to the modern a2a-python spec.

    Returns:
        An agent card object conforming to the legacy SAM spec.
    """
    log_identifier = "[A2ATranslation:Card]"
    log.debug(
        "%s Translating modern AgentCard for '%s' to legacy SAM format.",
        log_identifier,
        modern_card.name,
    )

    # Translate capabilities
    sam_capabilities = sam_types.AgentCapabilities(
        streaming=modern_card.capabilities.streaming or False,
        pushNotifications=modern_card.capabilities.push_notifications or False,
        stateTransitionHistory=modern_card.capabilities.state_transition_history
        or False,
    )

    # Translate skills (assuming the AgentSkill model is compatible)
    sam_skills = (
        [sam_types.AgentSkill(**skill.model_dump()) for skill in modern_card.skills]
        if modern_card.skills
        else []
    )

    # Translate provider (assuming the AgentProvider model is compatible)
    sam_provider = (
        sam_types.AgentProvider(**modern_card.provider.model_dump())
        if modern_card.provider
        else None
    )

    # Construct the legacy SAM AgentCard
    sam_card = sam_types.AgentCard(
        name=modern_card.name,
        display_name=modern_card.name,  # Use name as display_name for compatibility
        description=modern_card.description,
        url=modern_card.url,
        provider=sam_provider,
        version=modern_card.version,
        documentationUrl=modern_card.documentation_url,
        capabilities=sam_capabilities,
        defaultInputModes=modern_card.default_input_modes,
        defaultOutputModes=modern_card.default_output_modes,
        skills=sam_skills,
        # Fields from modern spec not in legacy spec are omitted:
        # - security_schemes, protocol_version, etc.
        # Fields from legacy spec not in modern spec are omitted or defaulted:
        # - authentication, tools, peer_agents
        peer_agents={},
    )

    return sam_card


def translate_sam_to_modern_request(
    legacy_payload: Dict[str, Any], is_new_task: bool = False
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
            log.debug(
                "%s Passing through compatible method '%s'.",
                log_identifier,
                legacy_method,
            )
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

    task_id_for_modern_message = legacy_params.get("id")
    if is_new_task:
        log.info(
            "%s Detected new task. Setting task_id to None for modern request.",
            log_identifier,
        )
        task_id_for_modern_message = None

    # 2.3.2: Create modern Message
    modern_message = Message(
        message_id=str(uuid.uuid4()),
        task_id=task_id_for_modern_message,
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
    ],
    produced_artifacts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Translates a modern A2A response/event object to a legacy SAM A2A dictionary
    by constructing a new dictionary from scratch.

    Args:
        modern_event: The modern Pydantic event object from the a2a-python SDK.
        produced_artifacts: A list of artifacts produced by the proxy, to be
                            added to the task's metadata.

    Returns:
        A dictionary conforming to the legacy SAM A2A protocol structure.
    """
    log_identifier = "[A2ATranslation:Outbound]"
    log.debug(
        "%s Translating modern event of type %s to legacy SAM dictionary.",
        log_identifier,
        type(modern_event).__name__,
    )

    def _translate_modern_message_to_sam_dict(
        modern_message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Translates a modern Message dictionary to a legacy SAM Message dictionary."""
        if not modern_message:
            return {}
        legacy_message = {
            "role": modern_message.get("role"),
            "parts": _translate_modern_parts_to_sam(modern_message.get("parts", [])),
        }
        if "metadata" in modern_message and modern_message["metadata"] is not None:
            legacy_message["metadata"] = modern_message["metadata"]
        return legacy_message

    def _translate_modern_status_to_sam_dict(
        modern_status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Translates a modern TaskStatus dictionary to a legacy SAM TaskStatus dictionary."""
        if not modern_status:
            return {}

        timestamp = modern_status.get("timestamp")
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        legacy_status = {
            "state": str(modern_status.get("state", "unknown")).lower(),
            "timestamp": timestamp,
        }
        if "message" in modern_status and modern_status["message"]:
            legacy_status["message"] = _translate_modern_message_to_sam_dict(
                modern_status["message"]
            )
        return legacy_status

    def _translate_modern_artifact_to_sam_dict(
        modern_artifact_event: ModernTaskArtifactUpdateEvent,
    ) -> Dict[str, Any]:
        """Translates a modern TaskArtifactUpdateEvent to a legacy SAM Artifact dictionary."""
        modern_artifact = modern_artifact_event.artifact
        legacy_artifact = {
            "name": modern_artifact.name,
            "description": modern_artifact.description,
            "parts": _translate_modern_parts_to_sam(
                modern_artifact.model_dump(mode="json").get("parts", [])
            ),
            "metadata": modern_artifact.metadata,
            "append": modern_artifact_event.append,
            "lastChunk": modern_artifact_event.last_chunk,
        }
        return {k: v for k, v in legacy_artifact.items() if v is not None}

    if isinstance(modern_event, ModernTask):
        modern_dict = modern_event.model_dump(mode="json", exclude_none=True)
        legacy_task = {
            "id": modern_dict.get("id"),
            "sessionId": modern_dict.get("context_id"),
            "status": _translate_modern_status_to_sam_dict(
                modern_dict.get("status", {})
            ),
        }
        if "history" in modern_dict and modern_dict["history"]:
            legacy_task["history"] = [
                _translate_modern_message_to_sam_dict(msg)
                for msg in modern_dict["history"]
            ]
        if "metadata" in modern_dict:
            legacy_task["metadata"] = modern_dict["metadata"]
        if "artifacts" in modern_dict and modern_dict["artifacts"]:
            legacy_artifacts = []
            for modern_artifact_dict in modern_dict["artifacts"]:
                legacy_artifacts.append(
                    {
                        "name": modern_artifact_dict.get("name"),
                        "description": modern_artifact_dict.get("description"),
                        "parts": _translate_modern_parts_to_sam(
                            modern_artifact_dict.get("parts", [])
                        ),
                        "metadata": modern_artifact_dict.get("metadata"),
                    }
                )
            legacy_task["artifacts"] = legacy_artifacts

        if produced_artifacts:
            if "metadata" not in legacy_task or legacy_task["metadata"] is None:
                legacy_task["metadata"] = {}
            legacy_task["metadata"]["produced_artifacts"] = produced_artifacts

        return {k: v for k, v in legacy_task.items() if v is not None}

    elif isinstance(modern_event, ModernTaskStatusUpdateEvent):
        modern_dict = modern_event.model_dump(mode="json", exclude_none=True)
        legacy_event = {
            "id": modern_dict.get("task_id"),
            "status": _translate_modern_status_to_sam_dict(
                modern_dict.get("status", {})
            ),
            "final": modern_dict.get("final", False),
        }
        if "metadata" in modern_dict:
            legacy_event["metadata"] = modern_dict["metadata"]
        return {k: v for k, v in legacy_event.items() if v is not None}

    elif isinstance(modern_event, ModernTaskArtifactUpdateEvent):
        legacy_event = {
            "id": modern_event.task_id,
            "artifact": _translate_modern_artifact_to_sam_dict(modern_event),
        }
        if modern_event.metadata:
            legacy_event["metadata"] = modern_event.metadata
        return {k: v for k, v in legacy_event.items() if v is not None}

    else:
        log.warning(
            "%s Received unhandled modern event type for translation: %s",
            log_identifier,
            type(modern_event).__name__,
        )
        return modern_event.model_dump(mode="json", exclude_none=True)
