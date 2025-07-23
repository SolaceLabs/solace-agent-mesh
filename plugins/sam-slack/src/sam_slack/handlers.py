"""
Event handlers for incoming Slack events (messages, mentions).
Translates Slack events into A2A task submissions.
"""

import asyncio
from typing import TYPE_CHECKING, Dict, Any, Optional
from solace_ai_connector.common.log import log
from .utils import (
    send_slack_message,
    _build_current_slack_blocks,
)

if TYPE_CHECKING:
    from .component import SlackGatewayComponent


async def _process_slack_event(
    component: "SlackGatewayComponent", event: Dict, say: Any, client: Any
):
    """
    Common logic to process a Slack message or mention event.
    It now calls the component's _translate_external_input method and then submits the task.
    """
    log_id = component.log_identifier
    task_id_for_ack: Optional[str] = None

    try:
        user_identity = await component.authenticate_and_enrich_user(event)
        if user_identity is None:
            log.warning("%s Slack user authentication failed. Denying request.", log_id)
            try:
                reply_target_ts = event.get("thread_ts") or event.get("ts")
                channel_id = event.get("channel")
                if channel_id and reply_target_ts:
                    if asyncio.iscoroutinefunction(say):
                        await say(
                            text="Sorry, I could not authenticate your request. Please try again or contact support.",
                            thread_ts=reply_target_ts,
                        )
                    else:
                        say(
                            text="Sorry, I could not authenticate your request. Please try again or contact support.",
                            thread_ts=reply_target_ts,
                        )
            except Exception as say_err:
                log.error(
                    "%s Failed to send authentication error to Slack: %s",
                    log_id,
                    say_err,
                )
            return

        log.info(
            "%s Authenticated Slack user identity: %s",
            log_id,
            user_identity.get("id", "unknown"),
        )

        log.debug("%s Calling _translate_external_input for Slack event...", log_id)
        target_agent_name, a2a_parts, external_request_context = (
            await component._translate_external_input(event, user_identity)
        )
        log.info(
            "%s Translation complete. Target: %s, Parts: %d",
            log_id,
            target_agent_name,
            len(a2a_parts),
        )

        task_id_for_ack = await component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=a2a_parts,
            external_request_context=external_request_context,
            user_identity=user_identity,
            is_streaming=True,
        )
        log.info(
            "%s Submitted A2A task %s for agent %s via GDK.",
            log_id,
            task_id_for_ack,
            target_agent_name,
        )

        with component.context_lock:
            component.active_cancellable_tasks.add(task_id_for_ack)
        log.debug(
            "%s Added task %s to active_cancellable_tasks.", log_id, task_id_for_ack
        )

        if component.slack_initial_status_message:
            reply_thread_ts = external_request_context.get("slack_thread_ts")
            channel_id = external_request_context.get("slack_channel_id")

            if not channel_id or not reply_thread_ts:
                log.error(
                    "%s Missing channel_id or reply_thread_ts in external_request_context for ack. Cannot send.",
                    log_id,
                )
                return

            try:
                blocks = _build_current_slack_blocks(
                    component.slack_initial_status_message
                )
                ack_ts = await send_slack_message(
                    component=component,
                    channel=channel_id,
                    thread_ts=reply_thread_ts,
                    text=component.slack_initial_status_message,
                    blocks=blocks,
                )
                if ack_ts and task_id_for_ack:
                    component.set_status_ts(task_id_for_ack, ack_ts)
                    component.set_current_status(
                        task_id_for_ack, component.slack_initial_status_message
                    )
                    log.debug(
                        "%s Sent Slack acknowledgement for task %s and set active TS: %s",
                        log_id,
                        task_id_for_ack,
                        ack_ts,
                    )
                    await component._update_slack_ui_state(
                        task_id=task_id_for_ack,
                        external_request_context=external_request_context,
                        text_to_display=None,
                        data_parts_for_slack=[],
                        file_infos_for_slack=[],
                        status_signal_text=component.slack_initial_status_message,
                        is_final_event=False,
                    )
                    log.debug(
                        "%s Triggered immediate UI update for task %s to add cancel button.",
                        log_id,
                        task_id_for_ack,
                    )
                elif task_id_for_ack:
                    log.error(
                        "%s Failed to get TS from Slack acknowledgement post for task %s.",
                        log_id,
                        task_id_for_ack,
                    )
            except Exception as ack_err:
                log.error(
                    "%s Failed to send Slack acknowledgement for task %s: %s",
                    log_id,
                    task_id_for_ack,
                    ack_err,
                )
        elif task_id_for_ack:
            component.set_status_ts(task_id_for_ack, None)
            component.set_current_status(task_id_for_ack, None)
            log.debug(
                "%s No Slack initial status message configured for task %s. Status TS will be set on first update. Cancel button will appear then.",
                log_id,
                task_id_for_ack,
            )

    except ValueError as ve:
        log.warning("%s Input translation failed or event ignored: %s", log_id, ve)
        if "Cannot determine target agent" in str(ve):
            try:
                reply_target_ts = event.get("thread_ts") or event.get("ts")
                channel_id = event.get("channel")
                if channel_id and reply_target_ts:
                    if asyncio.iscoroutinefunction(say):
                        await say(
                            text="Sorry, I couldn't determine which agent to send your request to.",
                            thread_ts=reply_target_ts,
                        )
                    else:
                        say(
                            text="Sorry, I couldn't determine which agent to send your request to.",
                            thread_ts=reply_target_ts,
                        )
            except Exception as say_err:
                log.error(
                    "%s Failed to send error message to Slack: %s", log_id, say_err
                )
    except PermissionError as pe:
        log.warning("%s Permission denied during task submission: %s", log_id, str(pe))
        try:
            reply_target_ts = event.get("thread_ts") or event.get("ts")
            channel_id = event.get("channel")
            if channel_id and reply_target_ts:
                if asyncio.iscoroutinefunction(say):
                    await say(
                        text=f"Sorry, your request was denied: {str(pe)}",
                        thread_ts=reply_target_ts,
                    )
                else:
                    say(
                        text=f"Sorry, your request was denied: {str(pe)}",
                        thread_ts=reply_target_ts,
                    )
        except Exception as say_err:
            log.error(
                "%s Failed to send permission error to Slack: %s", log_id, say_err
            )

    except Exception as e:
        log.exception(
            "%s Failed to process Slack event and submit A2A task: %s", log_id, e
        )
        try:
            reply_target_ts = event.get("thread_ts") or event.get("ts")
            channel_id = event.get("channel")
            if channel_id and reply_target_ts:
                if asyncio.iscoroutinefunction(say):
                    await say(
                        text=f"Sorry, I encountered an error processing your request: {e}",
                        thread_ts=reply_target_ts,
                    )
                else:
                    say(
                        text=f"Sorry, I encountered an error processing your request: {e}",
                        thread_ts=reply_target_ts,
                    )
        except Exception as say_err:
            log.error(
                "%s Failed to send submission error to Slack: %s", log_id, say_err
            )


async def handle_slack_message(
    component: "SlackGatewayComponent", event: Dict, say: Any, client: Any
):
    """Handles 'message' events from Slack (DMs, potentially thread messages)."""
    channel_type = event.get("channel_type")
    if channel_type == "im":
        log.debug("%s Handling Direct Message event.", component.log_identifier)
        await _process_slack_event(component, event, say, client)
    elif event.get("thread_ts") and channel_type in ["channel", "group"]:
        log.debug(
            "%s Ignoring non-mention message in channel/group thread.",
            component.log_identifier,
        )
    else:
        log.debug(
            "%s Ignoring message event type: %s in channel type: %s",
            component.log_identifier,
            event.get("subtype", "message"),
            channel_type,
        )


async def handle_slack_mention(
    component: "SlackGatewayComponent", event: Dict, say: Any, client: Any
):
    """Handles 'app_mention' events from Slack."""
    log.debug("%s Handling App Mention event.", component.log_identifier)
    await _process_slack_event(component, event, say, client)
