"""
Event handlers for incoming Slack events, delegating to the Generic Gateway.
"""

import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict

from ..adapter.types import ResponseContext
from . import utils

if TYPE_CHECKING:
    from .adapter import SlackAdapter

log = logging.getLogger(__name__)


# --- Command Framework ---

# Type hint for a command handler function
CommandHandler = Callable[["SlackAdapter", Dict, Any, logging.Logger], Awaitable[None]]

# Registry for bot commands
COMMAND_REGISTRY: Dict[str, CommandHandler] = {}


def register_command(name: str) -> Callable[[CommandHandler], CommandHandler]:
    """Decorator to register a new bot command."""

    def decorator(func: CommandHandler) -> CommandHandler:
        log.info(f"Registering Slack command: !{name}")
        COMMAND_REGISTRY[name] = func
        return func

    return decorator


# --- Command Implementations ---


@register_command("artifacts")
async def handle_artifacts_command(
    adapter: "SlackAdapter", event: Dict, client: Any, logger: logging.Logger
):
    """Handles the !artifacts command to list session artifacts."""
    logger.info(f"Handling '!artifacts' command for user {event['user']}")
    try:
        auth_claims = await adapter.extract_auth_claims(event)
        if not auth_claims or not auth_claims.id:
            raise ValueError("Could not determine user identity for artifact listing.")

        user_id = auth_claims.id
        session_id = utils.create_slack_session_id(
            event["channel"], event.get("thread_ts") or event.get("ts")
        )

        response_context = ResponseContext(
            task_id=f"slack-cmd-{event['ts']}",
            session_id=session_id,
            user_id=user_id,
            platform_context={
                "channel_id": event["channel"],
                "thread_ts": event.get("thread_ts") or event.get("ts"),
            },
        )

        artifacts = await adapter.context.list_artifacts(response_context)

        if not artifacts:
            await client.chat_postEphemeral(
                channel=event["channel"],
                user=event["user"],
                text="No artifacts found in this session.",
            )
            return

        blocks = []
        for artifact in artifacts:
            blocks.append({"type": "divider"})
            button_value = json.dumps(
                {"filename": artifact.filename, "version": artifact.version}
            )
            last_modified_str = "N/A"
            if artifact.last_modified:
                try:
                    dt_obj = datetime.fromisoformat(
                        artifact.last_modified.replace("Z", "+00:00")
                    )
                    last_modified_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S UTC")
                except (ValueError, TypeError):
                    last_modified_str = artifact.last_modified

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📄 *{artifact.filename}* (v{artifact.version})\n"
                        f"_{artifact.description or 'No description'}_\n"
                        f"Created: {last_modified_str}",
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Download"},
                        "action_id": "download_artifact_button",
                        "value": button_value,
                    },
                }
            )

        await client.chat_postEphemeral(
            channel=event["channel"],
            user=event["user"],
            blocks=blocks,
            text=f"Found {len(artifacts)} artifacts.",
        )

    except Exception as e:
        logger.error(f"Error handling '!artifacts' command: {e}", exc_info=True)
        await client.chat_postEphemeral(
            channel=event["channel"],
            user=event["user"],
            text=f"An error occurred: {e}",
        )


# --- Main Event Processor ---


async def _process_slack_event(adapter: "SlackAdapter", event: Dict, say: Any):
    """
    Common logic to process a Slack message or mention event.
    Checks for special keywords before delegating to the generic gateway.
    """
    try:
        text = event.get("text", "")
        # Remove the bot's mention to get the clean text
        clean_text = re.sub(r"<@.*?>", "", text).strip()

        # Check if it's a command
        if clean_text.startswith("!"):
            command_parts = clean_text[1:].split()
            command_name = command_parts[0].lower()

            if command_name in COMMAND_REGISTRY:
                handler = COMMAND_REGISTRY[command_name]
                # Use the client from the adapter's app instance
                await handler(adapter, event, adapter.slack_app.client, log)
            else:
                await adapter.slack_app.client.chat_postEphemeral(
                    channel=event["channel"],
                    user=event["user"],
                    text=f"Unknown command: `!{command_name}`. Try `!help` for a list of commands.",
                )
            return

        # Default behavior: process as a task for an agent
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
