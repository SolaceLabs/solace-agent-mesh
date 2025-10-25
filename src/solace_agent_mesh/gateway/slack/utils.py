"""
Utility functions for the Slack Gateway adapter.
"""

import json
import logging
import re
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .adapter import SlackAdapter

log = logging.getLogger(__name__)


def create_slack_session_id(channel_id: str, thread_ts: str) -> str:
    """Creates a safe session ID from Slack channel and thread timestamp."""
    safe_thread_ts = thread_ts.replace(".", "_")
    return f"slack-{channel_id}-{safe_thread_ts}"

# Block and Action IDs
STATUS_BLOCK_ID = "a2a_status_block"
CONTENT_BLOCK_ID = "a2a_content_block"
FEEDBACK_BLOCK_ID = "a2a_feedback_block"
CANCEL_BUTTON_ACTION_ID = "a2a_cancel_request_button"
CANCEL_ACTION_BLOCK_ID = "a2a_task_cancel_actions"
THUMBS_UP_ACTION_ID = "thumbs_up_action"
THUMBS_DOWN_ACTION_ID = "thumbs_down_action"
SUBMIT_FEEDBACK_ACTION_ID = "submit_feedback_action"
CANCEL_FEEDBACK_ACTION_ID = "cancel_feedback_action"
FEEDBACK_COMMENT_INPUT_ACTION_ID = "feedback_comment_input"
FEEDBACK_COMMENT_BLOCK_ID = "feedback_comment_block"


def correct_slack_markdown(text: str) -> str:
    """
    Converts common Markdown to Slack's mrkdwn format, avoiding changes inside code blocks.
    """
    if not isinstance(text, str):
        return text
    try:
        # Split text by code blocks to avoid formatting inside them
        parts = re.split(r"(```.*?```)", text, flags=re.DOTALL)
        processed_parts = []

        def heading_replacer(match: re.Match) -> str:
            title = match.group(1).strip()
            return f"\n*{title}*"

        for i, part in enumerate(parts):
            # If it's a code block part (odd index), just clean it up and add it
            if i % 2 == 1:
                # Code blocks: ```lang\ncode``` -> ```\ncode```
                cleaned_code_block = re.sub(r"```[a-zA-Z0-9_-]+\n", "```\n", part)
                processed_parts.append(cleaned_code_block)
            # If it's a non-code block part (even index), apply formatting
            else:
                # Links: [Text](URL) -> <URL|Text>
                part = re.sub(r"\[(.*?)\]\((http.*?)\)", r"<\2|\1>", part)
                # Bold: **Text** -> *Text*
                part = re.sub(r"\*\*(.*?)\*\*", r"*\1*", part)
                # Headings: ### Title -> *Title* with underline
                part = re.sub(
                    r"^\s*#{1,6}\s+(.*)", heading_replacer, part, flags=re.MULTILINE
                )
                processed_parts.append(part)

        text = "".join(processed_parts)

    except Exception as e:
        log.warning("[SlackUtil:correct_markdown] Error during formatting: %s", e)
    return text


def build_slack_blocks(
    status_text: Optional[str] = None,
    content_text: Optional[str] = None,
    feedback_elements: Optional[List[Dict]] = None,
    cancel_button_action_elements: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Builds the complete list of Slack blocks based on the current state."""
    blocks = []
    if status_text:
        blocks.append(
            {
                "type": "context",
                "block_id": f"{STATUS_BLOCK_ID}_{uuid.uuid4().hex[:8]}",
                "elements": [{"type": "mrkdwn", "text": status_text}],
            }
        )

    # Only add a content block if content_text is provided.
    if content_text is not None:
        # Slack requires non-empty text for markdown blocks
        display_content = content_text if content_text.strip() else " "
        blocks.append(
            {
                "type": "section",
                "block_id": f"{CONTENT_BLOCK_ID}_{uuid.uuid4().hex[:8]}",
                "text": {"type": "mrkdwn", "text": display_content},
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

    if feedback_elements:
        blocks.append(
            {
                "type": "actions",
                "block_id": FEEDBACK_BLOCK_ID,
                "elements": feedback_elements,
            }
        )
    return blocks


async def send_slack_message(
    adapter: "SlackAdapter",
    channel: str,
    thread_ts: Optional[str],
    text: str,
    blocks: Optional[List[Dict]] = None,
) -> Optional[str]:
    """Wrapper for chat.postMessage with error handling."""
    try:
        response = await adapter.slack_app.client.chat_postMessage(
            channel=channel, text=text, thread_ts=thread_ts, blocks=blocks
        )
        message_ts = response.get("ts")
        if message_ts:
            log.debug(
                "Successfully sent message to channel %s (Thread: %s, TS: %s)",
                channel,
                thread_ts,
                message_ts,
            )
            return message_ts
        log.error("chat.postMessage response missing 'ts'. Response: %s", response)
        return None
    except Exception as e:
        log.error(
            "Failed to send Slack message to channel %s (Thread: %s): %s",
            channel,
            thread_ts,
            e,
        )
        return None


async def update_slack_message(
    adapter: "SlackAdapter",
    channel: str,
    ts: str,
    text: str,
    blocks: Optional[List[Dict]] = None,
):
    """Wrapper for chat.update with error handling."""
    try:
        await adapter.slack_app.client.chat_update(
            channel=channel, ts=ts, text=text, blocks=blocks
        )
        log.debug("Successfully updated message %s in channel %s", ts, channel)
    except Exception as e:
        log.warning(
            "Failed to update Slack message %s in channel %s: %s", ts, channel, e
        )


async def upload_slack_file(
    adapter: "SlackAdapter",
    channel: str,
    thread_ts: Optional[str],
    filename: str,
    content_bytes: bytes,
):
    """Wrapper for files_upload_v2 with error handling."""
    try:
        await adapter.slack_app.client.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            filename=filename,
            content=content_bytes,
        )
        log.info(
            "Successfully uploaded file '%s' (%d bytes) to channel %s (Thread: %s)",
            filename,
            len(content_bytes),
            channel,
            thread_ts,
        )
    except Exception as e:
        log.error(
            "Failed to upload Slack file '%s' to channel %s (Thread: %s): %s",
            filename,
            channel,
            thread_ts,
            e,
        )
        try:
            error_text = f":warning: Failed to upload file: {filename}"
            await send_slack_message(adapter, channel, thread_ts, error_text)
        except Exception as notify_err:
            log.error("Failed to send file upload error notification: %s", notify_err)


def create_feedback_input_blocks(
    rating: str, original_payload: Dict
) -> List[Dict]:
    """Creates the Slack blocks for text feedback input."""
    submit_payload = {**original_payload, "rating": rating}
    submit_value_string = json.dumps(submit_payload)

    cancel_value_string = json.dumps(original_payload)

    if len(submit_value_string) > 2000 or len(cancel_value_string) > 2000:
        log.error("Feedback payload exceeds 2000 chars. Cannot create input form.")
        return [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": ":warning: Could not load feedback form (payload too large).",
                    }
                ],
            }
        ]

    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Thanks! Any additional comments?"},
        },
        {
            "type": "input",
            "block_id": FEEDBACK_COMMENT_BLOCK_ID,
            "element": {
                "type": "plain_text_input",
                "action_id": FEEDBACK_COMMENT_INPUT_ACTION_ID,
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Let us know what you think...",
                },
            },
            "label": {"type": "plain_text", "text": "Comment"},
        },
        {
            "type": "actions",
            "block_id": f"feedback_actions_{uuid.uuid4().hex[:8]}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Submit"},
                    "style": "primary",
                    "value": submit_value_string,
                    "action_id": SUBMIT_FEEDBACK_ACTION_ID,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "value": cancel_value_string,
                    "action_id": CANCEL_FEEDBACK_ACTION_ID,
                },
            ],
        },
    ]


def create_feedback_blocks(task_id: str, user_id: str, session_id: str) -> List[Dict]:
    """Creates the Slack action blocks for thumbs up/down feedback."""
    try:
        # The value payload for buttons is limited to 2000 characters.
        # We only need the task_id to correlate feedback.
        value_payload = {
            "task_id": task_id,
            "user_id": user_id,
            "session_id": session_id,
        }
        value_string = json.dumps(value_payload)
        if len(value_string) > 2000:
            log.error(
                "Feedback value payload exceeds 2000 chars. Cannot create buttons."
            )
            return []

        return [
            {
                "type": "button",
                "text": {"type": "plain_text", "emoji": True, "text": "👍"},
                "value": value_string,
                "action_id": THUMBS_UP_ACTION_ID,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "emoji": True, "text": "👎"},
                "value": value_string,
                "action_id": THUMBS_DOWN_ACTION_ID,
            },
        ]
    except Exception as e:
        log.error("Failed to create feedback blocks: %s", e)
        return []
