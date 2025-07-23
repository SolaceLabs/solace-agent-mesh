"""
Utility functions for the Slack Gateway component, including session ID generation,
topic extraction, Slack formatting, and API call wrappers.
"""

import re
import json
from typing import TYPE_CHECKING, Optional, List, Tuple, Any, Dict
from solace_ai_connector.common.log import log
from solace_agent_mesh.common.types import DataPart
from solace_agent_mesh.common.utils.embeds import (
    resolve_embeds_in_string,
    evaluate_embed,
    LATE_EMBED_TYPES,
    EMBED_DELIMITER_OPEN,
)
from solace_agent_mesh.common.a2a_protocol import _subscription_to_regex

if TYPE_CHECKING:
    from .component import SlackGatewayComponent


def generate_a2a_session_id(channel_id: str, thread_ts: str, agent_name: str) -> str:
    """
    Generates a deterministic A2A session ID based on Slack context.
    Format: slack_{channel_id}__{thread_ts_sanitized}_agent_{agent_name}
    """
    if not all([channel_id, thread_ts, agent_name]):
        raise ValueError(
            "Channel ID, Thread TS, and Agent Name are required to generate session ID."
        )
    thread_ts_sanitized = thread_ts.replace(".", "_")
    return f"slack_{channel_id}__{thread_ts_sanitized}_agent_{agent_name}"


def extract_task_id_from_topic(topic: str, subscription_pattern: str) -> Optional[str]:
    """
    Extracts the task ID from the end of a topic string based on the subscription pattern.
    (Copied/adapted from Web UI MessageProcessor)
    """
    log_id = "[SlackUtil:extract_task_id]"
    try:
        base_regex_str = _subscription_to_regex(subscription_pattern).replace(r".*", "")
        base_regex = re.compile(base_regex_str)
        match = base_regex.match(topic)
        if match:
            task_id_part = topic[match.end() :]
            task_id = task_id_part.lstrip("/")
            if task_id:
                log.debug(
                    "%s Extracted Task ID '%s' from topic '%s'", log_id, task_id, topic
                )
                return task_id
        log.warning(
            "%s Could not extract Task ID from topic '%s' using pattern '%s'",
            log_id,
            topic,
            subscription_pattern,
        )
        return None
    except Exception as e:
        log.error("%s Error extracting task ID from topic '%s': %s", log_id, topic, e)
        return None


def correct_slack_markdown(text: str) -> str:
    """
    Attempts to convert common Markdown formats to Slack's mrkdwn format.
    - Links: [Text](URL) -> <URL|Text>
    - Code blocks: ```lang\ncode``` -> ```\ncode```
    - Bold: **Text** -> *Text*
    """
    if not isinstance(text, str):
        return text

    try:
        text = re.sub(r"\[(.*?)\]\((http.*?)\)", r"<\2|\1>", text)
        text = re.sub(r"```[a-zA-Z0-9_-]+\n", "```\n", text)
        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    except Exception as e:
        log.warning("[SlackUtil:correct_markdown] Error during formatting: %s", e)
    return text


def format_data_part_for_slack(data_part: DataPart) -> str:
    """Formats an A2A DataPart for display in Slack (e.g., as a JSON code block)."""
    try:
        if data_part.data.get("a2a_signal_type") == "agent_status_message":
            status_text = data_part.data.get("text", "[Agent status update]")
            log.debug(
                "[SlackUtil:format_data_part] Extracted agent_status_message text: '%s'",
                status_text,
            )
            return status_text

        json_string = json.dumps(data_part.data, indent=2)
        header = "Received Data"
        if data_part.metadata:
            tool_name = data_part.metadata.get("tool_name")
            if tool_name:
                header = f"Result from Tool: `{tool_name}`"

        return f"{header}:\n```json\n{json_string}\n```"
    except Exception as e:
        log.warning("[SlackUtil:format_data_part] Error formatting DataPart: %s", e)
        return f"Received Data:\n```\n[Error formatting data: {e}]\n```"


STATUS_BLOCK_ID = "a2a_status_block"
CONTENT_BLOCK_ID = "a2a_content_block"
FEEDBACK_BLOCK_ID = "a2a_feedback_block"
CANCEL_BUTTON_ACTION_ID = "a2a_cancel_request_button"
CANCEL_ACTION_BLOCK_ID = "a2a_task_cancel_actions"


def _build_current_slack_blocks(
    status_text: Optional[str] = None,
    content_text: Optional[str] = None,
    feedback_elements: Optional[List[Dict]] = None,
    cancel_button_action_elements: Optional[List[Dict]] = None,
) -> List[Dict]:
    """
    Builds the complete list of Slack blocks based on the current state.
    This replaces _build_slack_blocks and _update_slack_blocks.
    """
    blocks = []

    if status_text:
        blocks.append(
            {
                "type": "context",
                "block_id": STATUS_BLOCK_ID,
                "elements": [{"type": "mrkdwn", "text": status_text}],
            }
        )

    display_content = content_text if content_text else " "
    blocks.append(
        {
            "type": "markdown",
            "block_id": CONTENT_BLOCK_ID,
            "text": display_content,
        }
    )

    if feedback_elements:
        blocks.append(
            {
                "type": "actions",
                "block_id": FEEDBACK_BLOCK_ID,
                "elements": feedback_elements,
            }
        )

    if cancel_button_action_elements:
        blocks.append(
            {
                "type": "actions",
                "block_id": CANCEL_ACTION_BLOCK_ID,
                "elements": cancel_button_action_elements,
            }
        )

    return blocks


async def send_slack_message(
    component: "SlackGatewayComponent",
    channel: str,
    thread_ts: Optional[str],
    text: str,
    blocks: Optional[List[Dict]] = None,
) -> Optional[str]:
    """Wrapper for chat.postMessage with error handling. Returns message TS if successful."""
    log_id = component.log_identifier
    try:
        response = await component.slack_app.client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks,
        )
        message_ts = response.get("ts")
        if message_ts:
            log.debug(
                "%s Successfully sent message to channel %s (Thread: %s, TS: %s)",
                log_id,
                channel,
                thread_ts,
                message_ts,
            )
            return message_ts
        else:
            log.error(
                "%s chat.postMessage response missing 'ts'. Response: %s",
                log_id,
                response,
            )
            return None
    except Exception as e:
        log.error(
            "%s Failed to send Slack message to channel %s (Thread: %s): %s",
            log_id,
            channel,
            thread_ts,
            e,
        )
        return None


async def update_slack_message(
    component: "SlackGatewayComponent",
    channel: str,
    ts: str,
    text: str,
    blocks: Optional[List[Dict]] = None,
):
    """Wrapper for chat.update with error handling."""
    log_id = component.log_identifier
    try:
        await component.slack_app.client.chat_update(
            channel=channel,
            ts=ts,
            text=text,
            blocks=blocks,
        )
        log.debug(
            "%s Successfully updated message %s in channel %s", log_id, ts, channel
        )
    except Exception as e:
        log.warning(
            "%s Failed to update Slack message %s in channel %s: %s",
            log_id,
            ts,
            channel,
            e,
        )


async def upload_slack_file(
    component: "SlackGatewayComponent",
    channel: str,
    thread_ts: Optional[str],
    filename: str,
    content_bytes: bytes,
    mime_type: Optional[str],
):
    """Wrapper for files_upload_v2 with error handling."""
    log_id = component.log_identifier
    try:
        await component.slack_app.client.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            filename=filename,
            content=content_bytes,
        )
        log.info(
            "%s Successfully uploaded file '%s' (%d bytes) to channel %s (Thread: %s)",
            log_id,
            filename,
            len(content_bytes),
            channel,
            thread_ts,
        )
    except Exception as e:
        log.error(
            "%s Failed to upload Slack file '%s' to channel %s (Thread: %s): %s",
            log_id,
            filename,
            channel,
            thread_ts,
            e,
        )
        try:
            error_text = f":warning: Failed to upload file: {filename}"
            await send_slack_message(component, channel, thread_ts, error_text)
        except Exception as notify_err:
            log.error(
                "%s Failed to send file upload error notification: %s",
                log_id,
                notify_err,
            )


async def resolve_and_format_for_slack(
    component: "SlackGatewayComponent", text: str, task_id: str
) -> Tuple[str, int, List[Tuple[int, Any]]]:
    """
    Resolves late-stage embeds in text and applies Slack markdown correction.
    Now runs synchronously and returns processed_until_index.
    """
    log_id = f"{component.log_identifier}[ResolveSlack:{task_id}]"
    resolved_text = text
    signals_found: List[Tuple[int, Any]] = []
    processed_until_index = len(text)

    if component.enable_embed_resolution and text and EMBED_DELIMITER_OPEN in text:
        log.debug(
            "%s Performing late-stage embed resolution for Slack output...", log_id
        )
        session_context = None
        with component.context_lock:
            slack_context = component.task_slack_context.get(task_id)
            if slack_context:
                session_context = {
                    "app_name": component.gateway_id,
                    "user_id": slack_context.get("user", "unknown_slack_user"),
                    "session_id": generate_a2a_session_id(
                        slack_context.get("channel"),
                        slack_context.get("thread_ts"),
                        component.default_agent_name or "UnknownAgent",
                    ),
                }
            else:
                log.warning(
                    "%s Slack context not found for Task ID: %s during embed resolution.",
                    log_id,
                    task_id,
                )

        if not session_context:
            log.warning(
                "%s Cannot resolve embeds: Session context could not be constructed for Task ID: %s",
                log_id,
                task_id,
            )
            return text, len(text), []
        elif not component.shared_artifact_service:
            log.warning(
                "%s Cannot resolve artifact_content embeds: ArtifactService not available.",
                log_id,
            )
            types_to_resolve = {"status_update"}
        else:
            types_to_resolve = LATE_EMBED_TYPES.union({"status_update"})

            gateway_context = {
                "artifact_service": component.shared_artifact_service,
                "session_context": session_context,
            }
            embed_config = {
                "gateway_artifact_content_limit_bytes": component.gateway_artifact_content_limit_bytes,
                "gateway_recursive_embed_depth": component.gateway_recursive_embed_depth,
            }

            try:
                resolved_text, processed_until_index, signals_found = (
                    resolve_embeds_in_string(
                        text=text,
                        context=gateway_context,
                        resolver_func=evaluate_embed,
                        types_to_resolve=types_to_resolve,
                        log_identifier=log_id,
                        config=embed_config,
                    )
                )

                if resolved_text != text or signals_found:
                    log.info(
                        "%s Embed/signal resolution complete (Processed Index: %d, Signals: %d).",
                        log_id,
                        processed_until_index,
                        len(signals_found),
                    )
                else:
                    log.debug("%s No embeds/signals resolved.", log_id)

            except Exception as e:
                log.exception("%s Error during embed resolution: %s", log_id, e)
                resolved_text = (
                    text + f"\n\n[:warning: Error resolving dynamic content: {e}]"
                )
                processed_until_index = len(text)
                signals_found = []

    if component.correct_markdown_formatting:
        formatted_text = correct_slack_markdown(resolved_text)
        if formatted_text != resolved_text:
            log.debug("%s Applied Slack markdown corrections.", log_id)
        return (
            formatted_text,
            processed_until_index,
            signals_found,
        )
    else:
        return (
            resolved_text,
            processed_until_index,
            signals_found,
        )


def create_feedback_blocks(
    feedback_data: Dict, channel: str, thread_ts: Optional[str]
) -> List[Dict]:
    """Creates the Slack action blocks for thumbs up/down feedback."""
    log_id = "[SlackUtil:create_feedback]"
    try:
        value_payload = {
            "channel": channel,
            "thread_ts": thread_ts,
            "feedback_data": feedback_data,
        }

        data_str = json.dumps(value_payload, sort_keys=True)
        block_id_suffix = str(hash(data_str))[-8:]
        block_id = f"{FEEDBACK_BLOCK_ID}_{block_id_suffix}"
        value_payload["feedback_data"]["block_id"] = block_id

        value_string = json.dumps(value_payload)
        if len(value_string) > 2000:
            log.warning(
                "%s Feedback value payload exceeds 2000 chars. Truncating feedback_data.",
                log_id,
            )
            value_payload["feedback_data"] = {
                "task_id": feedback_data.get("task_id", "unknown"),
                "truncated": True,
            }
            value_string = json.dumps(value_payload)
            if len(value_string) > 2000:
                log.error(
                    "%s Feedback value payload still exceeds 2000 chars after truncation. Cannot create buttons.",
                    log_id,
                )
                return []

        log.debug("%s Creating feedback blocks with block_id: %s", log_id, block_id)
        return [
            {
                "type": "actions",
                "block_id": block_id,
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "emoji": True, "text": "👍"},
                        "value": value_string,
                        "action_id": "thumbs_up_action",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "emoji": True, "text": "👎"},
                        "value": value_string,
                        "action_id": "thumbs_down_action",
                    },
                ],
            }
        ]
    except Exception as e:
        log.error("%s Failed to create feedback blocks: %s", log_id, e)
        return []
