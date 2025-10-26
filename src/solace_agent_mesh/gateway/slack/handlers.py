"""
Event handlers for incoming Slack events, delegating to the Generic Gateway.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .adapter import SlackAdapter

log = logging.getLogger(__name__)


async def _process_slack_event(adapter: "SlackAdapter", event: Dict, say: Any):
    """
    Common logic to process a Slack message or mention event.
    This now simply calls the generic gateway's handle_external_input method.
    """
    try:
        await adapter.context.handle_external_input(event)
    except Exception as e:
        log.exception("Error processing Slack event via handle_external_input: %s", e)
        try:
            reply_target_ts = event.get("thread_ts") or event.get("ts")
            await say(
                text=f"Sorry, I encountered an error processing your request: {e}",
                thread_ts=reply_target_ts,
            )
        except Exception as say_err:
            log.error("Failed to send submission error to Slack: %s", say_err)


async def handle_slack_message(adapter: "SlackAdapter", event: Dict, say: Any):
    """Handles 'message' events from Slack (DMs, potentially thread messages)."""
    # Filter out bot messages and message change events
    if event.get("bot_id") or event.get("subtype") in [
        "bot_message",
        "message_changed",
        "message_deleted",
    ]:
        log.debug(f"Ignoring event with subtype: {event.get('subtype')}")
        return

    channel_type = event.get("channel_type")
    if channel_type == "im":
        log.debug("Handling Direct Message event.")
        await _process_slack_event(adapter, event, say)
    elif event.get("thread_ts") and channel_type in ["channel", "group"]:
        log.debug("Ignoring non-mention message in channel/group thread.")
    else:
        log.debug(
            "Ignoring message event type: %s in channel type: %s",
            event.get("subtype", "message"),
            channel_type,
        )


async def handle_slack_mention(adapter: "SlackAdapter", event: Dict, say: Any):
    """Handles 'app_mention' events from Slack."""
    log.debug("Handling App Mention event.")
    await _process_slack_event(adapter, event, say)
