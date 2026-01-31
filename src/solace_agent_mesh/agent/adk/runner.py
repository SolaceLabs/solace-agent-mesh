"""
Manages the asynchronous execution of the ADK Runner.
"""

import logging
import asyncio
import os

from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from litellm.exceptions import BadRequestError


class TaskCancelledError(Exception):
    """Raised when an ADK task is cancelled via external signal."""

    pass


from typing import TYPE_CHECKING, Any

from google.adk.agents import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.events import Event as ADKEvent
from google.adk.events.event_actions import EventActions
from google.adk.sessions import Session as ADKSession
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.genai import types as adk_types
from a2a.types import TaskState

from ...common import a2a

log = logging.getLogger(__name__)

# System-wide auto-summarization (configurable via env var)
# Set SAM_ENABLE_AUTO_SUMMARIZATION=false to disable
ENABLE_AUTO_SUMMARIZATION = os.getenv("SAM_ENABLE_AUTO_SUMMARIZATION", "true").lower() == "true"

if TYPE_CHECKING:
    from ..sac.component import SamAgentComponent
    from ..sac.task_execution_context import TaskExecutionContext


def _is_context_limit_error(error: BadRequestError) -> bool:
    """
    Check if a BadRequestError is due to context/token limit being exceeded.

    Args:
        error: The BadRequestError exception

    Returns:
        True if this is a context limit error, False otherwise
    """
    error_message = str(error.message).lower() if hasattr(error, 'message') else str(error).lower()
    context_limit_indicators = [
        "too many tokens",
        "maximum context length",
        "context length exceeded",
        "input is too long",
        "prompt is too long",
        "context_length_exceeded",
        "token limit",
    ]
    return any(indicator in error_message for indicator in context_limit_indicators)


def _is_background_task(a2a_context: dict) -> bool:
    """
    Determine if this is a background task or interactive session.

    Background tasks are:
    - Scheduled/cron jobs
    - Agent-to-agent calls without human in loop
    - Tasks with backgroundExecutionEnabled=True in metadata

    Interactive tasks are:
    - Direct user requests from HTTP/SSE gateway
    - Tasks initiated via web UI
    - Have a user-specific client_id

    Args:
        a2a_context: The A2A context dictionary

    Returns:
        True if this is a background task, False if interactive
    """
    # Check metadata for explicit background flag
    metadata = a2a_context.get("metadata", {})
    if metadata.get("backgroundExecutionEnabled", False):
        return True

    # Check if there's a reply topic indicating peer-to-peer (no user)
    reply_topic = a2a_context.get("replyToTopic")
    client_id = a2a_context.get("client_id")

    # If there's a peer reply topic but no client, it's likely background
    if reply_topic and not client_id:
        return True

    return False


async def _summarize_and_replace_oldest_turns(
    component: "SamAgentComponent",
    session: ADKSession,
    num_turns_to_summarize: int = 2,
    log_identifier: str = ""
) -> tuple[int, str, ADKSession]:
    """
    Summarize the oldest N user turns using ADK's compaction mechanism.

    Uses LlmEventSummarizer to create properly formatted compaction events that:
    1. Get persisted to DB via session_service.append_event()
    2. Contain timestamp ranges to identify which events they replace
    3. Are understood by ADK's prompt builder to skip compacted events
    4. Reload session from DB to get fresh state with compaction included

    This dramatically reduces token count while preserving conversation context.
    Typically achieves 50:1 to 100:1 compression ratio.

    Args:
        component: The SamAgentComponent instance
        session: The ADK session to truncate
        num_turns_to_summarize: Number of oldest user turns to summarize (default: 2)
        log_identifier: Logging prefix

    Returns:
        Tuple of (events_removed_count, summary_text, fresh_session)
    """
    if not session or not session.events:
        return 0, "", session

    # 1. Filter out existing compaction events and separate by author
    non_compaction_events = [
        e for e in session.events
        if not (e.actions and e.actions.compaction)
    ]

    system_events = [e for e in non_compaction_events if e.author == "system"]
    conversation_events = [e for e in non_compaction_events if e.author != "system"]

    # 2. Find user turn boundaries
    user_indices = [i for i, e in enumerate(conversation_events) if e.author == "user"]

    if len(user_indices) <= num_turns_to_summarize:
        log.warning(
            "%s Not enough user turns to summarize (%d available, %d requested)",
            log_identifier,
            len(user_indices),
            num_turns_to_summarize
        )
        return 0, "", session

    # 3. Extract turns to summarize (from start to Nth user turn)
    cutoff_idx = user_indices[num_turns_to_summarize]
    events_to_compact = conversation_events[:cutoff_idx]
    remaining_events = conversation_events[cutoff_idx:]

    if not events_to_compact:
        return 0, "", session

    log.info(
        "%s Compacting %d events (first %d user turns) using LlmEventSummarizer...",
        log_identifier,
        len(events_to_compact),
        num_turns_to_summarize
    )

    # 4. Use ADK's LlmEventSummarizer to create compaction event
    try:
        summarizer = LlmEventSummarizer(llm=component.adk_agent.model)
        compaction_event = await summarizer.maybe_summarize_events(events=events_to_compact)

        if not compaction_event:
            log.error("%s LlmEventSummarizer returned no compaction event", log_identifier)
            return 0, "", session

        # Extract summary text from compaction event for notification
        summary_text = ""
        if compaction_event.actions and compaction_event.actions.compaction:
            compacted_content = compaction_event.actions.compaction.compacted_content
            if compacted_content and compacted_content.parts:
                for part in compacted_content.parts:
                    if part.text:
                        summary_text = part.text
                        break

        if not summary_text:
            log.warning("%s No text found in compaction event", log_identifier)
            summary_text = "[Summary generated but no text available]"

    except Exception as e:
        log.error("%s Failed to create compaction event: %s", log_identifier, e, exc_info=True)
        return 0, "", session

    # 5. Persist compaction event to database
    try:
        await component.session_service.append_event(session=session, event=compaction_event)
        log.info(
            "%s Persisted compaction event for timestamp range [%s → %s]",
            log_identifier,
            compaction_event.actions.compaction.start_timestamp,
            compaction_event.actions.compaction.end_timestamp
        )
    except Exception as e:
        log.error(
            "%s Failed to persist compaction event: %s",
            log_identifier,
            e,
            exc_info=True
        )
        raise  # Fail retry if we can't persist

    # 6. Reload session from DB to get fresh state with compaction included
    #    This ensures ADK's prompt builder can properly handle the compaction event
    try:
        fresh_session = await component.session_service.get_session(
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id
        )
        if not fresh_session:
            raise RuntimeError(f"Failed to reload session {session.id} after compaction")

        log.debug(
            "%s Reloaded session from DB: %d events (including compaction)",
            log_identifier,
            len(fresh_session.events) if fresh_session.events else 0
        )

    except Exception as e:
        log.error("%s Failed to reload session: %s", log_identifier, e, exc_info=True)
        raise

    # Log compression stats
    log.info(
        "%s Compacted %d events into summary (%d tokens → ~%d tokens, ~%dx compression)",
        log_identifier,
        len(events_to_compact),
        sum(len(str(e.content)) for e in events_to_compact if e.content) // 4,  # Rough estimate
        len(summary_text) // 4,
        max(1, sum(len(str(e.content)) for e in events_to_compact if e.content) // max(1, len(summary_text)))
    )

    return len(events_to_compact), summary_text, fresh_session


async def _send_truncation_notification(
    component: "SamAgentComponent",
    a2a_context: dict,
    summary: str,
    is_background: bool = False,
    log_identifier: str = ""
):
    """
    Send a status update to the user notifying them that conversation was summarized.

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        summary: The summary text that replaced the old turns
        is_background: True if this is a background task, False if interactive
        log_identifier: Logging prefix
    """
    try:
        logical_task_id = a2a_context.get("logical_task_id", "unknown")

        # Different messages for background vs interactive tasks
        if is_background:
            notification_text = (
                f"ℹ️ Note: Conversation history was automatically summarized to stay within token limits.\n\n"
                f"Summary of earlier messages:\n{summary}"
            )
        else:
            notification_text = (
                f"⚠️ Your conversation history reached the token limit!\n\n"
                f"We've automatically summarized older messages to continue. "
                f"Alternatively, you can start a new chat for a fresh conversation.\n\n"
                f"Summary of earlier messages:\n{summary}"
            )

        status_update = a2a.create_task_status_update(
            task_id=logical_task_id,
            state=TaskState.running,
            message=a2a.create_agent_text_message(text=notification_text)
        )

        response = a2a.create_success_response(
            result=status_update,
            request_id=a2a_context.get("jsonrpc_request_id")
        )

        # Publish to appropriate topic
        namespace = component.get_config("namespace")
        client_id = a2a_context.get("client_id")
        peer_reply_topic = a2a_context.get("replyToTopic")

        target_topic = peer_reply_topic or a2a.get_client_response_topic(namespace, client_id)

        component._publish_a2a_event(
            response.model_dump(exclude_none=True),
            target_topic,
            a2a_context
        )

        log.info(
            "%s Sent truncation notification to user for task %s",
            log_identifier,
            logical_task_id
        )

    except Exception as e:
        log.warning(
            "%s Failed to send truncation notification: %s",
            log_identifier,
            e
        )


async def run_adk_async_task_thread_wrapper(
    component: "SamAgentComponent",
    adk_session: ADKSession,
    adk_content: adk_types.Content,
    run_config: RunConfig,
    a2a_context: dict[str, Any],
    append_context_event: bool = True,
    skip_finalization: bool = False,
):
    """
    Wrapper to run the async ADK task.
    Calls component finalization methods upon completion or error.

    Args:
        component: The SamAgentComponent instance.
        adk_session: The ADK session to use (from component.session_service).
        adk_content: The input content for the ADK agent.
        run_config: The ADK run configuration.
        a2a_context: The context dictionary for this specific A2A request.
        append_context_event: Whether to append the context-setting event to the session.
        skip_finalization: If True, skips automatic finalization (for custom finalization like workflow nodes).
    """
    logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
    is_paused = False
    exception_to_finalize_with = None
    task_context = None
    try:
        with component.active_tasks_lock:
            task_context = component.active_tasks.get(logical_task_id)

        if not task_context:
            log.error(
                "%s TaskExecutionContext not found for task %s. Cannot start ADK runner.",
                component.log_identifier,
                logical_task_id,
            )
            return

        task_context.flush_streaming_buffer()
        log.debug(
            "%s Cleared streaming text buffer before starting ADK task %s.",
            component.log_identifier,
            logical_task_id,
        )

        if adk_session and component.session_service and append_context_event:
            context_setting_invocation_id = logical_task_id
            try:
                from .services import append_event_with_retry

                context_setting_event = ADKEvent(
                    invocation_id=context_setting_invocation_id,
                    author="A2A_Host_System",
                    content=adk_types.Content(
                        role="user",  # Must set role to avoid breaking ADK's is_final_response() logic
                        parts=[
                            adk_types.Part(
                                text="Initializing A2A context for task run."
                            )
                        ],
                    ),
                    actions=EventActions(state_delta={"a2a_context": a2a_context}),
                    branch=None,
                )
                # Use retry helper to handle stale session race conditions
                await append_event_with_retry(
                    session_service=component.session_service,
                    session=adk_session,
                    event=context_setting_event,
                    app_name=component.agent_name,
                    user_id=adk_session.user_id,
                    session_id=adk_session.id,
                    log_identifier=f"{component.log_identifier}[ContextEvent:{logical_task_id}]",
                )
                log.debug(
                    "%s Appended context-setting event to ADK session %s (via component.session_service) for task %s.",
                    component.log_identifier,
                    adk_session.id,
                    logical_task_id,
                )
            except Exception as e_append:
                log.error(
                    "%s Failed to append context-setting event for task %s: %s.",
                    component.log_identifier,
                    logical_task_id,
                    e_append,
                    exc_info=True,
                )
        else:
            if append_context_event:
                log.warning(
                    "%s Could not inject a2a_context into ADK session state via event for task %s (session or session_service invalid). Tool scope filtering might not work.",
                    component.log_identifier,
                    logical_task_id,
                )

        # =================================================================
        # Retry loop with automatic summarization on context limit errors
        # System-wide configuration via SAM_ENABLE_AUTO_SUMMARIZATION env var
        # =================================================================
        max_retries = 3
        retry_count = 0
        is_paused = False

        while retry_count <= max_retries:
            try:
                is_paused = await run_adk_async_task(
                    component,
                    task_context,
                    adk_session,
                    adk_content,
                    run_config,
                    a2a_context,
                )
                # Success! Break out of retry loop
                break

            except BadRequestError as e:
                # Check if this is a context limit error AND auto-summarization is enabled
                if _is_context_limit_error(e) and ENABLE_AUTO_SUMMARIZATION:
                    retry_count += 1

                    if retry_count > max_retries:
                        # Exceeded max retries, give up
                        log.error(
                            "%s Context limit exceeded after %d summarization attempts for task %s. Giving up.",
                            component.log_identifier,
                            max_retries,
                            logical_task_id,
                        )
                        raise

                    # Summarize oldest 2 turns and retry
                    log.warning(
                        "%s Context limit exceeded for task %s. Attempting automatic summarization (attempt %d/%d)...",
                        component.log_identifier,
                        logical_task_id,
                        retry_count,
                        max_retries,
                    )

                    # Store original events for audit logging
                    original_event_count = len(adk_session.events) if adk_session.events else 0

                    events_removed, summary, adk_session = await _summarize_and_replace_oldest_turns(
                        component=component,
                        session=adk_session,
                        num_turns_to_summarize=2,
                        log_identifier=component.log_identifier
                    )

                    if events_removed == 0:
                        # Can't summarize any more (not enough turns)
                        log.error(
                            "%s Cannot summarize further - insufficient conversation history for task %s.",
                            component.log_identifier,
                            logical_task_id,
                        )
                        raise

                    # Audit log: Now using fresh session reloaded from DB
                    new_event_count = len(adk_session.events) if adk_session.events else 0
                    log.warning(
                        "%s AUDIT: Summarized session %s for task %s. "
                        "Removed %d events (%d → %d total). "
                        "Summary: '%s'",
                        component.log_identifier,
                        adk_session.id,
                        logical_task_id,
                        events_removed,
                        original_event_count,
                        new_event_count,
                        summary[:200] + "..." if len(summary) > 200 else summary
                    )

                    # Detect if this is a background task for different notification messaging
                    is_background = _is_background_task(a2a_context)

                    # Send notification to user about summarization
                    await _send_truncation_notification(
                        component=component,
                        a2a_context=a2a_context,
                        summary=summary,
                        is_background=is_background,
                        log_identifier=component.log_identifier
                    )

                    log.info(
                        "%s Summarization complete. Retrying task %s with reduced context...",
                        component.log_identifier,
                        logical_task_id
                    )

                    # Continue to next retry iteration
                    continue
                else:
                    # Either not a context limit error, or auto-summarization is disabled
                    if _is_context_limit_error(e) and not ENABLE_AUTO_SUMMARIZATION:
                        log.error(
                            "%s Context limit exceeded for task %s, but auto-summarization is disabled. "
                            "Set SAM_ENABLE_AUTO_SUMMARIZATION=true to enable.",
                            component.log_identifier,
                            logical_task_id
                        )
                    # Re-raise the original error
                    raise

        # Mark task as paused if it's waiting for peer response or user input
        if task_context and is_paused:
            task_context.set_paused(True)
            log.debug(
                "%s Task %s marked as paused, waiting for peer response or user input.",
                component.log_identifier,
                logical_task_id,
            )

        log.debug(
            "%s ADK task %s awaited and completed (Paused: %s).",
            component.log_identifier,
            logical_task_id,
            is_paused,
        )

    except TaskCancelledError as tce:
        exception_to_finalize_with = tce
        log.info(
            "%s Task %s was cancelled. Propagating to peers before scheduling finalization. Message: %s",
            component.log_identifier,
            logical_task_id,
            tce,
        )
        sub_tasks_to_cancel = task_context.active_peer_sub_tasks if task_context else {}

        if sub_tasks_to_cancel:
            log.info(
                "%s Propagating cancellation to %d peer sub-task(s) for main task %s.",
                component.log_identifier,
                len(sub_tasks_to_cancel),
                logical_task_id,
            )
            for sub_task_id, sub_task_info in sub_tasks_to_cancel.items():
                try:
                    target_peer_agent_name = sub_task_info.get("peer_agent_name")
                    if not sub_task_id or not target_peer_agent_name:
                        log.warning(
                            "%s Incomplete sub-task info found for sub-task %s, cannot cancel: %s",
                            component.log_identifier,
                            sub_task_id,
                            sub_task_info,
                        )
                        continue

                    task_id_for_peer = sub_task_id.replace(
                        component.CORRELATION_DATA_PREFIX, "", 1
                    )
                    peer_cancel_request = a2a.create_cancel_task_request(
                        task_id=task_id_for_peer
                    )
                    peer_cancel_user_props = {"clientId": component.agent_name}
                    peer_request_topic = component._get_agent_request_topic(
                        target_peer_agent_name
                    )
                    component.publish_a2a_message(
                        payload=peer_cancel_request.model_dump(exclude_none=True),
                        topic=peer_request_topic,
                        user_properties=peer_cancel_user_props,
                    )
                except Exception as e_peer_cancel:
                    log.error(
                        "%s Failed to send CancelTaskRequest for sub-task %s: %s",
                        component.log_identifier,
                        sub_task_id,
                        e_peer_cancel,
                        exc_info=True,
                    )
    except LlmCallsLimitExceededError as llm_limit_e:
        exception_to_finalize_with = llm_limit_e
        log.warning(
            "%s LLM call limit exceeded for task %s: %s. Scheduling finalization.",
            component.log_identifier,
            logical_task_id,
            llm_limit_e,
        )
    except BadRequestError as e:
        exception_to_finalize_with = e
        log.error(
            "%s Bad Request for task %s: %s. Scheduling finalization.",
            component.log_identifier,
            logical_task_id,
            e.message,
        )
    except Exception as e:
        exception_to_finalize_with = e
        log.exception(
            "%s Exception in ADK runner for task %s: %s. Scheduling finalization.",
            component.log_identifier,
            logical_task_id,
            e,
        )

    if not skip_finalization:
        loop = component.get_async_loop()
        if loop and loop.is_running():
            log.debug(
                "%s Scheduling finalize_task_with_cleanup for task %s.",
                component.log_identifier,
                logical_task_id,
            )
            asyncio.run_coroutine_threadsafe(
                component.finalize_task_with_cleanup(
                    a2a_context, is_paused, exception_to_finalize_with
                ),
                loop,
            )
        else:
            log.error(
                "%s Async loop not available. Cannot schedule finalization for task %s.",
                component.log_identifier,
                logical_task_id,
            )
    else:
        log.debug(
            "%s Skipping automatic finalization for task %s (skip_finalization=True).",
            component.log_identifier,
            logical_task_id,
        )

        log.debug(
            "%s ADK runner for task %s finished.",
            component.log_identifier,
            logical_task_id,
        )


async def run_adk_async_task(
    component: "SamAgentComponent",
    task_context: "TaskExecutionContext",
    adk_session: ADKSession,
    adk_content: adk_types.Content,
    run_config: RunConfig,
    a2a_context: dict[str, Any],
) -> bool:
    """
    Runs the ADK Runner asynchronously and calls component methods to process
    intermediate events and finalize the task.
    Returns:
        bool: True if the task is paused for a long-running tool, False otherwise.
    """
    logical_task_id = a2a_context.get("logical_task_id", "unknown_task")
    event_loop_stored = False
    current_loop = asyncio.get_running_loop()
    # Track pending long-running tools by their function_call IDs
    # This replaces the simple boolean is_paused to properly handle sync returns
    pending_long_running_tools: set[str] = set()
    # Collect synchronous responses from long-running tools for potential re-run
    sync_tool_responses: list[adk_types.Part] = []

    adk_event_generator = component.runner.run_async(
        user_id=adk_session.user_id,
        session_id=adk_session.id,
        new_message=adk_content,
        run_config=run_config,
    )

    try:
        while True:
            next_event_task = asyncio.create_task(adk_event_generator.__anext__())
            cancel_wait_task = asyncio.create_task(
                task_context.cancellation_event.wait()
            )

            done, pending = await asyncio.wait(
                {next_event_task, cancel_wait_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if cancel_wait_task in done:
                next_event_task.cancel()
                try:
                    await next_event_task
                except asyncio.CancelledError:
                    log.debug(
                        "%s Suppressed CancelledError for next_event_task after signal.",
                        component.log_identifier,
                    )
                log.info(
                    "%s Task %s cancellation detected while awaiting ADK event.",
                    component.log_identifier,
                    logical_task_id,
                )
                raise TaskCancelledError(
                    f"Task {logical_task_id} was cancelled by signal."
                )

            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    log.debug(
                        "%s Suppressed CancelledError for lingering task after event.",
                        component.log_identifier,
                    )

            try:
                event = await next_event_task
            except StopAsyncIteration:
                break

            if event.long_running_tool_ids:
                # Track which long-running tool calls are pending (waiting for async response)
                pending_long_running_tools = pending_long_running_tools.union(
                    event.long_running_tool_ids
                )

            if not event_loop_stored and event.invocation_id:
                task_context.set_event_loop(current_loop)
                a2a_context["invocation_id"] = event.invocation_id
                event_loop_stored = True

            try:
                await component.process_and_publish_adk_event(event, a2a_context)
            except Exception as process_err:
                log.exception(
                    "%s Error processing intermediate ADK event %s for task %s: %s",
                    component.log_identifier,
                    event.id,
                    logical_task_id,
                    process_err,
                )

            if task_context.is_cancelled():
                raise TaskCancelledError(
                    f"Task {logical_task_id} was cancelled after processing ADK event {event.id}."
                )

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_response:
                        # Check if this is a sync response from a long-running tool
                        # (i.e., the tool returned immediately instead of async)
                        response_id = part.function_response.id
                        if response_id and response_id in pending_long_running_tools:
                            pending_long_running_tools.discard(response_id)
                            sync_tool_responses.append(part)
                            log.info(
                                "%s Long-running tool %s (id=%s) returned synchronously.",
                                component.log_identifier,
                                part.function_response.name,
                                response_id,
                            )

    except TaskCancelledError:
        raise
    except BadRequestError as e:
        log.error(
            "%s Bad Request for task %s: %s.",
            component.log_identifier,
            logical_task_id,
            e.message,
        )
        raise
    except Exception as e:
        log.exception(
            "%s Unexpected error in ADK runner loop for task %s: %s",
            component.log_identifier,
            logical_task_id,
            e,
        )
        raise

    if task_context.is_cancelled():
        log.info(
            "%s Task %s cancellation detected before finalization.",
            component.log_identifier,
            logical_task_id,
        )
        raise TaskCancelledError(
            f"Task {logical_task_id} was cancelled before finalization."
        )

    invocation_id = a2a_context.get("invocation_id")

    # Check if we still have pending long-running tools (waiting for async responses)
    if pending_long_running_tools:
        # Store any sync responses using the SAME format as event_handlers.py
        # This ensures they're combined with async responses when _retrigger is called
        if sync_tool_responses:
            for part in sync_tool_responses:
                result = {
                    "adk_function_call_id": part.function_response.id,
                    "peer_tool_name": part.function_response.name,
                    "payload": part.function_response.response,  # Already a dict from ADK
                }
                task_context.record_parallel_result(result, invocation_id)
            log.info(
                "%s Stored %d sync tool response(s) for later combination. Waiting for: %s",
                component.log_identifier,
                len(sync_tool_responses),
                pending_long_running_tools,
            )

        log.info(
            "%s Task %s paused, waiting for %d async tool response(s).",
            component.log_identifier,
            logical_task_id,
            len(pending_long_running_tools),
        )
        return True

    # All tools returned synchronously - re-run ADK with their responses
    # The ADK already created the Part objects, so we use them directly (no duplication)
    if sync_tool_responses:
        log.info(
            "%s All %d long-running tool(s) returned synchronously for task %s. Re-running ADK.",
            component.log_identifier,
            len(sync_tool_responses),
            logical_task_id,
        )
        # Use the Part objects directly from the ADK (already properly formatted)
        tool_response_content = adk_types.Content(role="tool", parts=sync_tool_responses)
        return await run_adk_async_task(
            component=component,
            task_context=task_context,
            adk_session=adk_session,
            adk_content=tool_response_content,
            run_config=run_config,
            a2a_context=a2a_context,
        )

    log.debug(
        "%s ADK run_async completed for task %s. Returning to wrapper for finalization.",
        component.log_identifier,
        logical_task_id,
    )
    return False
