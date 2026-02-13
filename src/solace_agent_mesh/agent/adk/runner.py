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
from google.adk.events import Event as ADKEvent
from google.adk.events.event_actions import EventActions
from google.adk.sessions import Session as ADKSession
from google.adk.apps.llm_event_summarizer import LlmEventSummarizer
from google.genai import types as adk_types

from ...common import a2a

log = logging.getLogger(__name__)

# System-wide auto-summarization (configurable via env var)
# Set SAM_ENABLE_AUTO_SUMMARIZATION=false to disable
ENABLE_AUTO_SUMMARIZATION = os.getenv("SAM_ENABLE_AUTO_SUMMARIZATION", "false").lower() == "true"


# Trigger compaction after N user turns (for testing without burning tokens)
# Set SAM_FORCE_COMPACTION_TURN_THRESHOLD=4 to trigger compaction after 4 user messages
# Set to 0 (default) to disable test mode and use real context limits
FORCE_COMPACTION_TURN_THRESHOLD = int(os.getenv("SAM_FORCE_COMPACTION_TURN_THRESHOLD", "0"))

# Number of interactions to compact at a time
COMPACTION_INTERACTIONS_COUNT = int(os.getenv("SAM_COMPACTION_INTERACTIONS_COUNT", "2"))

# Per-session locks for compaction to prevent parallel tasks from duplicate summarization
# When multiple tasks hit context limit simultaneously, only one compacts per session
# Others wait for the lock, then retry with the compacted session (no redundant work)
# TTL cache prevents memory leak: locks expire after 1 hour of inactivity
try:
    from cachetools import TTLCache
    _compaction_locks: TTLCache = TTLCache(maxsize=10000, ttl=3600)
except ImportError:
    # TODO add proper LLTCache dep Fallback to regular dict if cachetools not available (will leak memory over time)
    log.warning("cachetools not installed - compaction locks will not expire (memory leak)")
    _compaction_locks: dict[str, asyncio.Lock] = {}
_compaction_locks_mutex = asyncio.Lock()

# Per-session summaries for deferred notification (after successful response)
# When compaction occurs during retries, we store the summary here instead of sending immediately
# This ensures users see the actual response first, then a clean notification about summarization
# Dict operations are atomic in asyncio (single event loop), so no mutex needed
_session_summaries: dict[str, str] = {}  # session_id → latest summary text


async def _get_compaction_lock(session_id: str) -> asyncio.Lock:
    """
    Get or create an asyncio.Lock for the given session_id.

    Ensures only one task per session can perform compaction at a time.
    When multiple parallel tasks hit context limits, they coordinate via this lock.

    Args:
        session_id: The ADK session ID

    Returns:
        asyncio.Lock instance for this session
    """
    async with _compaction_locks_mutex:
        if session_id not in _compaction_locks:
            _compaction_locks[session_id] = asyncio.Lock()
        return _compaction_locks[session_id]


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


def _count_user_turns(events: list[ADKEvent]) -> int:
    """
    Count the number of user turns in the session.

    Used for test mode to trigger compaction after N user messages.

    Args:
        events: List of ADK events

    Returns:
        Number of user turns (messages authored by 'user')
    """
    if not events:
        return 0

    # CRITICAL: Exclude compaction events from count
    # ADK's LlmEventSummarizer creates compaction events with author='user'
    # but they're summaries, not actual user messages
    return sum(
        1 for e in events
        if e.author == 'user'
        and e.content
        and not (e.actions and e.actions.compaction)  # Exclude compaction events
    )


async def _create_compaction_event(
    component: "SamAgentComponent",
    session: ADKSession,
    num_turns_to_summarize: int = 2,
    log_identifier: str = ""
) -> tuple[int, str]:
    """
    Create a compaction event summarizing the oldest N user turns.

    CRITICAL: Progressive Summarization via "Fake Event" Trick
    - Extracts previous summary (if exists)
    - Creates fake event (no .actions.compaction) from old summary
    - Passes [FakeSummaryEvent, NewTurn1, NewTurn2] to LlmEventSummarizer
    - LLM re-compresses: new_summary = compress(old_summary + new_turns)
    - Result: Summary size stays bounded, not growing infinitely

    This function does NOT modify the session - it only creates and persists
    a compaction event to DB. Actual event filtering happens via FilteringSessionService
    when session is reloaded from DB.

    Returns:
        Tuple of (events_compacted_count, summary_text, original_session)
        Note: Returns the ORIGINAL session unchanged, not a reloaded one
    """
    if not session or not session.events:
        return 0, ""

    # 1. Extract compaction event (if exists) and other events separately
    latest_compaction = None
    non_compaction_events = []

    for event in session.events:
        if event.actions and event.actions.compaction:
            latest_compaction = event
        else:
            non_compaction_events.append(event)

    # Separate system vs conversation events
    conversation_events = [e for e in non_compaction_events if e.author != "system"]

    # CRITICAL: Progressive Summarization via "Fake Event"
    # LlmEventSummarizer intelligently SKIPS events with .actions.compaction
    # So we create a FAKE event (no .actions.compaction) containing the old summary
    # This tricks LlmEventSummarizer into re-summarizing the old summary + new turns
    # Result: summary stays bounded, not growing infinitely
    if latest_compaction:
        # Extract previous summary text
        previous_summary_text = ""
        if hasattr(latest_compaction, 'content') and latest_compaction.content and latest_compaction.content.parts:
            for part in latest_compaction.content.parts:
                if part.text:
                    previous_summary_text = part.text
                    break

        if previous_summary_text:
            # Create fake event that looks like normal conversation (no .actions.compaction)
            # CRITICAL: Don't set actions.compaction - this is what tricks LlmEventSummarizer
            fake_summary_event = ADKEvent(
                invocation_id="progressive_summary_fake_event",
                author="model",  # Summary is from AI's perspective
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text=previous_summary_text)]
                )
            )
            # Prepend fake event so LlmEventSummarizer re-summarizes old summary + new turns
            conversation_events = [fake_summary_event] + conversation_events

            log.info(
                "%s Progressive summarization: Created fake event with previous summary (%d chars) to trick LlmEventSummarizer",
                log_identifier,
                len(previous_summary_text)
            )
        else:
            log.warning(
                "%s Previous compaction event exists but has no summary text - cannot do progressive summarization!",
                log_identifier
            )

    # 2. Find user turn boundaries (count ONLY real user messages, not compaction)
    user_indices = [
        i for i, e in enumerate(conversation_events)
        if e.author == "user" and not (e.actions and e.actions.compaction)
    ]

    if len(user_indices) < num_turns_to_summarize:
        log.warning(
            "%s Not enough user turns to summarize (%d available, %d requested)",
            log_identifier,
            len(user_indices),
            num_turns_to_summarize
        )
        return 0, ""

    # 3. Extract turns to summarize:
    # A "turn" = user message + model response (complete interaction)
    # We want to include N complete turns, which means:
    # - All events up to (but NOT including) the (N+1)th user message
    # - OR all events if there's no (N+1)th user message
    if num_turns_to_summarize < len(user_indices):
        # There's a next user turn after the ones we're summarizing
        # Include everything BEFORE that next user turn
        cutoff_idx = user_indices[num_turns_to_summarize]
    else:
        # No next user turn - include all remaining events
        cutoff_idx = len(conversation_events)

    events_to_compact = conversation_events[:cutoff_idx]

    if not events_to_compact:
        return 0, ""

    if latest_compaction:
        log.info(
            "%s Compacting %d events: [PREVIOUS_SUMMARY + %d new events (%d user turns)]",
            log_identifier,
            len(events_to_compact),
            len(events_to_compact) - 1,  # -1 for compaction event
            num_turns_to_summarize
        )
    else:
        log.info(
            "%s Compacting %d events (first %d user turns) - no previous summary",
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
            return 0, ""

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
        return 0, ""

    # 5. Persist compaction event to database
    #    We don't reload the session here - ADK will reload from DB on retry anyway
    try:
        from ..adk.services import append_event_with_retry

        await append_event_with_retry(
            session_service=component.session_service,
            session=session,
            event=compaction_event,
            app_name=session.app_name,
            user_id=session.user_id,
            session_id=session.id,
            log_identifier=log_identifier
        )

        log.info(
            "%s Persisted compaction event for timestamp range [%s → %s]",
            log_identifier,
            compaction_event.actions.compaction.start_timestamp,
            compaction_event.actions.compaction.end_timestamp
        )

        log.debug(
            "%s Compaction event persisted to DB. ADK will reload session.",
            log_identifier
        )

    except Exception as e:
        log.error(
            "%s Failed to persist compaction event: %s",
            log_identifier,
            e,
            exc_info=True
        )
        raise  # Fail retry if we can't persist

    # Log compression stats
    log.info(
        "%s Compacted %d events into summary (%d tokens → ~%d tokens, ~%dx compression)",
        log_identifier,
        len(events_to_compact),
        sum(len(str(e.content)) for e in events_to_compact if e.content) // 4,  # Rough estimate
        len(summary_text) // 4,
        max(1, sum(len(str(e.content)) for e in events_to_compact if e.content) // max(1, len(summary_text)))
    )

    return len(events_to_compact), summary_text


async def _send_compaction_failure_message(
    component: "SamAgentComponent",
    a2a_context: dict,
    log_identifier: str = ""
):
    """
    Send a graceful error message when progressive summarization cannot reduce context enough.

    Informs user that:
    - Progressive summarization was attempted
    - Context is still too large
    - Suggests retrying (triggers more summarization) or starting new chat

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        log_identifier: Logging prefix
    """
    try:
        logical_task_id = a2a_context.get("logical_task_id", "unknown")

        notification_text = (
            "❌ **Unable to complete request - conversation history too long**\n\n"
            "We attempted progressive summarization to reduce the context, but your conversation "
            "history is still too large to process this request.\n\n"
            "**Options:**\n"
            "1. **Retry your last request** - This will trigger additional summarization and may succeed\n"
            "2. **Start a new chat** - Begin fresh with no history for complex requests\n"
            "3. **Simplify your request** - Break it into smaller, more focused tasks\n\n"
            "We apologize for the inconvenience!"
        )

        message = a2a.create_agent_text_message(text=notification_text)

        status_update = a2a.create_status_update(
            task_id=logical_task_id,
            context_id=a2a_context.get("contextId"),
            message=message,
            is_final=True  # Mark as final since we're failing
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
            "%s Sent compaction failure message to user for task %s",
            log_identifier,
            logical_task_id
        )

    except Exception as e:
        log.warning(
            "%s Failed to send compaction failure message: %s",
            log_identifier,
            e
        )


async def _send_truncation_notification(
    component: "SamAgentComponent",
    a2a_context: dict,
    summary: str,
    is_background: bool = False,
    log_identifier: str = "",
    session: ADKSession = None
):
    """
    Send a status update to the user notifying them that conversation was summarized.

    Uses deduplication to prevent spam when multiple parallel tasks hit context limits.
    Only sends notification once per 120 seconds per session.

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        summary: The summary text that replaced the old turns
        is_background: True if this is a background task, False if interactive
        log_identifier: Logging prefix
        session: The ADK session (for deduplication tracking)
    """
    try:
        import time

        # Deduplication: Only notify once per 120 seconds per session
        # This prevents spam when multiple parallel background jobs hit context limit
        if session:
            last_notification_time = session.state.get('last_compaction_notification_time', 0)
            time_since_last = time.time() - last_notification_time

            if time_since_last < 120:
                log.info(
                    "%s Skipping notification (sent %.1f seconds ago, cooldown: 120s)",
                    log_identifier,
                    time_since_last
                )
                return

            # Update timestamp to prevent spam from parallel tasks
            session.state['last_compaction_notification_time'] = time.time()
        logical_task_id = a2a_context.get("logical_task_id", "unknown")

        # Different messages for background vs interactive tasks
        if is_background:
            notification_text = (
                f"\n\n---\n\n"
                f"**ℹ️ Note:** Conversation history was automatically summarized to stay within token limits.\n\n"
                f"**Summary of earlier messages:**\n\n"
                f"*{summary}*\n\n"
                f"---\n"
            )
        else:
            notification_text = (
                f"\n\n---\n\n"
                f"**⚠️ Your conversation history reached the token limit!**\n\n"
                f"We've automatically summarized older messages to continue. "
                f"Alternatively, you can start a new chat for a fresh conversation.\n\n"
                f"**Summary of earlier messages:**\n\n"
                f"*{summary}*\n\n"
                f"---\n"
            )

        message = a2a.create_agent_text_message(text=notification_text)

        status_update = a2a.create_status_update(
            task_id=logical_task_id,
            context_id=a2a_context.get("contextId"),
            message=message,
            is_final=False
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
                # Proactively summarize when hitting threshold
                # This allows testing compaction without burning thousands of tokens plus trigger compaction when certain # of iteration is hit
                if FORCE_COMPACTION_TURN_THRESHOLD > 0 and adk_session.events and ENABLE_AUTO_SUMMARIZATION:
                    user_turn_count = _count_user_turns(adk_session.events)
                    if user_turn_count > FORCE_COMPACTION_TURN_THRESHOLD:
                        log.warning(
                            "%sTriggering context limit error at %d user turns (threshold: %d)",
                            component.log_identifier,
                            user_turn_count,
                            FORCE_COMPACTION_TURN_THRESHOLD
                        )
                        raise BadRequestError(
                            message=f"FORCE_COMPACTION_TURN_THRESHOLD: {FORCE_COMPACTION_TURN_THRESHOLD} maximum context length exceeded {user_turn_count}",
                            model="test-model",
                            llm_provider="test-provider"
                        )

                is_paused = await run_adk_async_task(
                    component,
                    task_context,
                    adk_session,
                    adk_content,
                    run_config,
                    a2a_context,
                )
                break

            except BadRequestError as e:
                # Check if this is a context limit error AND auto-summarization is enabled
                if _is_context_limit_error(e) and ENABLE_AUTO_SUMMARIZATION:
                    retry_count += 1

                    if retry_count > max_retries:
                        # Exceeded max retries - clean up and send graceful message
                        # Remove any pending summary since we're failing
                        _session_summaries.pop(adk_session.id, None)

                        log.error(
                            "%s Context limit exceeded after %d summarization attempts for task %s.",
                            component.log_identifier,
                            max_retries,
                            logical_task_id,
                        )

                        # Send graceful user-facing message instead of raising technical error
                        await _send_compaction_failure_message(
                            component=component,
                            a2a_context=a2a_context,
                            log_identifier=component.log_identifier
                        )

                        # Exit cleanly - user already got the graceful message
                        return

                    # Get per-session compaction lock to prevent parallel tasks from duplicate work
                    # When multiple tasks hit limit simultaneously, only one compacts per session
                    compaction_lock = await _get_compaction_lock(adk_session.id)

                    # Check if another task is already compacting this session
                    if compaction_lock.locked():
                        log.info(
                            "%s Another parallel task is compacting session %s. Waiting for completion...",
                            component.log_identifier,
                            adk_session.id
                        )

                        # Wait for the other task to finish compacting
                        async with compaction_lock:
                            pass  # Lock released - other task completed compaction

                        # Reload session to get the compacted state created by the other task
                        adk_session = await component.session_service.get_session(
                            app_name=component.agent_name,
                            user_id=adk_session.user_id,
                            session_id=adk_session.id
                        )

                        if not adk_session:
                            log.error(
                                "%s Failed to reload session after parallel compaction for task %s",
                                component.log_identifier,
                                logical_task_id
                            )
                            raise RuntimeError("Session disappeared after parallel compaction")

                        log.info(
                            "%s Parallel task completed compaction. Retrying task %s with reduced context (no summarization needed)...",
                            component.log_identifier,
                            logical_task_id
                        )

                        # Continue to retry WITHOUT doing our own compaction
                        continue

                    # Lock is available - we'll do the compaction work
                    async with compaction_lock:
                        log.warning(
                            "%s Context limit exceeded for task %s. Performing automatic summarization (attempt %d/%d)...",
                            component.log_identifier,
                            logical_task_id,
                            retry_count,
                            max_retries,
                        )

                        # Store original events for audit logging
                        original_event_count = len(adk_session.events) if adk_session.events else 0

                        events_removed, summary = await _create_compaction_event(
                            component=component,
                            session=adk_session,
                            num_turns_to_summarize=COMPACTION_INTERACTIONS_COUNT,
                            log_identifier=component.log_identifier
                        )

                        # MANDATORY: Reload session from DB after compaction to get filtered state
                        # FilteringSessionService automatically removes ghost events when loading from DB
                        # Without this reload, retry would still contain all old events and fail again
                        adk_session = await component.session_service.get_session(
                            app_name=component.agent_name,
                            user_id=adk_session.user_id,
                            session_id=adk_session.id
                        )
                        log.warning(
                            "%s DEBUG: After reload, session has %d events. Authors: %s",
                            component.log_identifier,
                            len(adk_session.events),
                            [f"{e.author}:{e.invocation_id[:20]}" for e in adk_session.events[:10]]
                        )

                        if not adk_session:
                            log.error(
                                "%s Failed to reload session after compaction for task %s",
                                component.log_identifier,
                                logical_task_id
                            )
                            raise RuntimeError("Session disappeared after compaction")

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
                            "%s AUDIT: Summarized session %s for task %s (attempt %d/%d). "
                            "Removed %d events (%d → %d total). "
                            "Summary: '%s'",
                            component.log_identifier,
                            adk_session.id,
                            logical_task_id,
                            retry_count,
                            max_retries,
                            events_removed,
                            original_event_count,
                            new_event_count,
                            summary[:200] + "..." if len(summary) > 200 else summary
                        )

                        # Store summary for deferred notification (after successful response)
                        # This prevents showing multiple ugly summary messages during retries
                        # User sees answer first, then clean notification about summarization
                        if adk_session.id in _session_summaries:
                            log.info(
                                "%s Overriding previous compaction summary for session %s",
                                component.log_identifier,
                                adk_session.id
                            )
                        _session_summaries[adk_session.id] = summary

                        log.info(
                            "%s Summarization complete. Retrying task %s with reduced context...",
                            component.log_identifier,
                            logical_task_id
                        )

                    # Lock automatically released - continue to next retry iteration
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

        # Send deferred summarization notification AFTER successful response
        # User sees the actual answer first, then a clean notification about what happened

        # Only ROOT tasks should consume the summary - subtasks should leave it
        parent_task_id = a2a_context.get("metadata", {}).get("parentTaskId")

        if parent_task_id:
            # Subtask - peek but don't consume
            summary = _session_summaries.get(adk_session.id)
            if summary:
                log.info(
                    "%s Subtask compacted (parent: %s) - leaving summary for root task to notify",
                    component.log_identifier,
                    parent_task_id
                )
        else:
            # Root task - consume and send notification
            summary = _session_summaries.pop(adk_session.id, None)
            if summary:
                log.info(
                    "%s Sending deferred compaction notification for session %s after successful response",
                    component.log_identifier,
                    adk_session.id
                )
                is_background = _is_background_task(a2a_context)
                await _send_truncation_notification(
                    component=component,
                    a2a_context=a2a_context,
                    summary=summary,
                    is_background=is_background,
                    log_identifier=component.log_identifier,
                    session=adk_session
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
