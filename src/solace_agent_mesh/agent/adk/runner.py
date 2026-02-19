"""
Manages the asynchronous execution of the ADK Runner.
"""

import logging
import asyncio

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
from cachetools import TTLCache

from ...common import a2a

log = logging.getLogger(__name__)

# Per-session locks for compaction to prevent parallel tasks from duplicate summarization
# When multiple tasks hit context limit simultaneously, only one compacts per session
_compaction_locks: TTLCache = TTLCache(maxsize=10000, ttl=3600)
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


def _calculate_total_char_count(events: list[ADKEvent]) -> int:
    """
    Calculate total character count across all event content.
    Sums the length of all text in event.content.parts[].text across all events.
    Only counts events with actual content (skips empty events).
    Args:
        events: List of ADK events
    Returns:
        Total character count from all event content
    """
    if not events:
        return 0

    total_chars = 0
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    total_chars += len(part.text)

    return total_chars


def _find_compaction_cutoff(
    events: list[ADKEvent],
    target_chars: int,
    log_identifier: str = ""
) -> tuple[int, int]:
    """
    Find the cutoff index that gets closest to target character count.

    Always cuts at user turn boundaries (complete interactions).
    Ensures at least 1 user turn remains uncompacted.

    Args:
        events: All conversation events (non-compaction, non-system)
        target_chars: Target number of characters to compact
        log_identifier: Logging prefix

    Returns:
        Tuple of (cutoff_index, actual_chars_to_compact)
        - cutoff_index: Index where to cut (events[:cutoff_index] get compacted)
        - actual_chars_to_compact: Actual character count up to cutoff
    """
    if not events:
        return 0, 0

    # Find all user turn indices (same logic as genuine user messages)
    user_indices = [
        i for i, e in enumerate(events)
        if e.content
        and e.author == 'user'
        and e.content.role == 'user'
        and not (e.actions and e.actions.compaction)
    ]

    if len(user_indices) < 2:
        # Need at least 2 turns (compact 1, leave 1)
        log.warning(
            "%s Not enough user turns to compact (%d available, need at least 2)",
            log_identifier,
            len(user_indices)
        )
        return 0, 0

    # Iterate through potential cutoff points (each user turn except the last)
    # For each cutoff, we'll calculate the char count up to that point
    best_cutoff_idx = 0
    best_char_count = 0
    best_distance = float('inf')

    # Try each user turn (except the last) as a potential cutoff point
    for turn_idx in range(len(user_indices) - 1):
        # The cutoff will be at the NEXT user turn (to include complete interactions)
        cutoff_idx = user_indices[turn_idx + 1]

        # Calculate total chars from events[0:cutoff_idx]
        char_count = 0
        for event in events[:cutoff_idx]:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        char_count += len(part.text)

        # Check if this is closest to target
        distance = abs(char_count - target_chars)
        if distance < best_distance:
            best_distance = distance
            best_cutoff_idx = cutoff_idx
            best_char_count = char_count

    log.info(
        "%s Found cutoff at turn boundary (index=%d): %d chars (target: %d, diff: %d)",
        log_identifier,
        best_cutoff_idx,
        best_char_count,
        target_chars,
        abs(best_char_count - target_chars)
    )

    return best_cutoff_idx, best_char_count

async def _create_compaction_event(
    component: "SamAgentComponent",
    session: ADKSession,
    compaction_threshold: float = 0.25,
    log_identifier: str = ""
) -> tuple[int, str]:
    """
    Create a compaction event using percentage-based progressive summarization.
    Strategy:
    1. Calculate total character count across all conversation events
    2. Determine target compaction size (total_chars * compaction_threshold)
    3. Find user turn boundary closest to target percentage
    4. Extract previous summary (if exists) and create fake event to trick LlmEventSummarizer
    5. Pass [FakeSummaryEvent, NewEvents] to LLM for progressive re-compression
    6. Persist compaction event to DB (append-only, old events remain for audit)

    Progressive Summarization: Each new summary re-compresses (old_summary + new_content),
    keeping total size bounded instead of growing infinitely with each compaction.

    Filtering Architecture:
    - This function does NOT filter events - it only creates/persists compaction event
    - DB remains append-only (events never deleted, compaction events just added)
    - FilteringSessionService automatically filters ghost events when loading sessions
    - Filtering modifies session.events IN-MEMORY (services.py:327), DB stays unchanged
    - After calling this function, MUST reload session via get_session() to get filtered state

    Args:
        component: The SamAgentComponent instance
        session: The ADK session to compact
        compaction_threshold: Percentage of conversation to compact (0.0 - 1.0)
        log_identifier: Logging prefix

    Returns:
        Tuple of (events_compacted_count, summary_text)
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

    # 2. Calculate total character count and target compaction size
    # Use non_compaction_events (includes system + conversation) for consistency
    # with proactive trigger logic
    total_chars = _calculate_total_char_count(non_compaction_events)
    target_chars = int(total_chars * compaction_threshold)

    log.info(
        "%s Compaction target: %d total chars * %.1f%% = %d target chars",
        log_identifier,
        total_chars,
        compaction_threshold * 100,
        target_chars
    )

    # 3. Find cutoff point using target character count
    # This finds the user turn boundary closest to our target percentage
    # Pass ALL non_compaction_events to match our total_chars calculation
    cutoff_idx, actual_chars = _find_compaction_cutoff(
        events=non_compaction_events,
        target_chars=target_chars,
        log_identifier=log_identifier
    )

    if cutoff_idx == 0:
        # Not enough user turns to compact
        log.warning(
            "%s Cannot compact - insufficient user turns or history",
            log_identifier
        )
        return 0, ""

    # 4. Extract events to compact (up to cutoff boundary)
    events_to_compact = non_compaction_events[:cutoff_idx]

    if not events_to_compact:
        return 0, ""

    # 5. Progressive Summarization via "Fake Event"
    # LlmEventSummarizer intelligently SKIPS events with .actions.compaction
    # So we create a FAKE event (no .actions.compaction) containing the old summary
    # Prepend it to events_to_compact so LLM re-summarizes (old summary + new events)
    # Result: summary stays bounded, not growing infinitely
    if latest_compaction:
        previous_summary_text = ""
        if hasattr(latest_compaction, 'content') and latest_compaction.content and latest_compaction.content.parts:
            for part in latest_compaction.content.parts:
                if part.text:
                    previous_summary_text = part.text
                    break

        if previous_summary_text:
            # Create fake event that looks like normal conversation (no .actions.compaction)
            # this is what tricks LlmEventSummarizer to accept summarized event for next compaction
            comp = latest_compaction.actions.compaction
            end_ts = comp['end_timestamp'] if isinstance(comp, dict) else comp.end_timestamp # Defensive handling: compaction can be dict or EventCompaction object

            fake_summary_event = ADKEvent(
                invocation_id="progressive_summary_fake_event",
                author="model",  # Summary is from AI's perspective
                content=adk_types.Content(
                    role="model",
                    parts=[adk_types.Part(text=previous_summary_text)]
                ),
                timestamp=end_ts  # Use end_timestamp from previous compaction
            )
            events_to_compact = [fake_summary_event] + events_to_compact

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

    if latest_compaction:
        log.info(
            "%s Compacting %d events: [PREVIOUS_SUMMARY + %d new events (%d chars)]",
            log_identifier,
            len(events_to_compact),
            len(events_to_compact) - 1,  # -1 for fake summary event
            actual_chars
        )
    else:
        log.info(
            "%s Compacting %d events (%d chars) - no previous summary",
            log_identifier,
            len(events_to_compact),
            actual_chars
        )

    # 6. Use ADK's LlmEventSummarizer to create compaction event
    try:
        # When previous summary exists (via fake event trick), LLM must dilute old context and prioritize new
        progressive_prompt_template = """You are creating a rolling summary of an ongoing conversation that prioritizes recent information.

IMPORTANT: If the first message below is from 'model' (the AI), it contains a PREVIOUS SUMMARY of earlier parts of this conversation. Your task is to:
1. **Focus primarily on the NEW user-AI interactions** - these are the most important
2. **Compress and condense the previous summary** - keep only the most critical context
3. **Drop outdated information** from the old summary that's no longer relevant to recent discussion

If there is NO previous summary (conversation starts with 'user'), simply summarize the entire conversation.

The summary should:
- **Prioritize recent information** - newer events should get more detail
- **Aggressively compress older context** - earlier summaries should fade into brief mentions
- **Drop irrelevant old details** - don't carry forward information no longer needed
- Be concise and focus on what's currently relevant

Think of this like a rolling window: as new information comes in, older information should naturally fade away unless it remains directly relevant.

Conversation history:
{conversation_history}

Create a progressive summary that emphasizes recent activity while compressing historical context:"""

        summarizer = LlmEventSummarizer(
            llm=component.adk_agent.model,
            prompt_template=progressive_prompt_template
        )
        compaction_event = await summarizer.maybe_summarize_events(events=events_to_compact)

        if not compaction_event:
            log.error("%s LlmEventSummarizer returned no compaction event", log_identifier)
            return 0, ""

        # LlmEventSummarizer returns inverted timestamps (start > end)
        # services.py uses max() for defensive handling, so we must do the same here
        comp = compaction_event.actions.compaction
        start_ts = comp.start_timestamp
        end_ts = comp.end_timestamp
        end_timestamp = max(start_ts, end_ts)

        # Add compaction_time as state_delta for O(1) lookup on read.
        compaction_event.actions = EventActions(
            compaction=compaction_event.actions.compaction,
            state_delta={'compaction_time': end_timestamp}
        )

        log.debug(
            "%s Added state_delta to compaction event: compaction_time=%.6f",
            log_identifier,
            end_timestamp
        )

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

    # 7. Persist compaction event to database
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
        sum(len(str(e.content)) for e in events_to_compact if e.content) // 4,
        len(summary_text) // 4,
        max(1, sum(len(str(e.content)) for e in events_to_compact if e.content) // max(1, len(summary_text)))
    )

    return len(events_to_compact), summary_text


async def _send_status_notification(
    component: "SamAgentComponent",
    a2a_context: dict,
    notification_text: str,
    is_final: bool,
    log_message: str,
    log_identifier: str = ""
):
    """
    Common helper to send status update notifications to users.

    Encapsulates the boilerplate of creating and publishing A2A messages.

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        notification_text: The text message to send to the user
        is_final: Whether this is a final status (True) or intermediate (False)
        log_message: What to log after sending (e.g., "Sent failure notification")
        log_identifier: Logging prefix
    """
    try:
        logical_task_id = a2a_context.get("logical_task_id", "unknown")

        message = a2a.create_agent_text_message(text=notification_text)

        status_update = a2a.create_status_update(
            task_id=logical_task_id,
            context_id=a2a_context.get("contextId"),
            message=message,
            is_final=is_final
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
            "%s %s for task %s",
            log_identifier,
            log_message,
            logical_task_id
        )

    except Exception as e:
        log.error(
            "%s Failed to send notification: %s",
            log_identifier,
            e
        )


async def _send_insufficient_history_message(
    component: "SamAgentComponent",
    a2a_context: dict,
    log_identifier: str = ""
):
    """
    Send a graceful error message when there's insufficient conversation history for compaction.

    Informs user that:
    - The conversation is too short to summarize
    - They should start a new conversation

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        log_identifier: Logging prefix
    """
    notification_text = (
        "❌ **Unable to complete request - conversation too short to summarize**\n\n"
        "Your conversation history has exceeded the context limit, but there are not enough "
        "conversation turns to create a meaningful summary.\n\n"
        "**Recommended action:**\n"
        "- **Start a new chat** - Begin a fresh conversation to continue\n\n"
        "We apologize for the inconvenience!"
    )

    await _send_status_notification(
        component=component,
        a2a_context=a2a_context,
        notification_text=notification_text,
        is_final=True,
        log_message="Sent insufficient history notification",
        log_identifier=log_identifier
    )


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

    await _send_status_notification(
        component=component,
        a2a_context=a2a_context,
        notification_text=notification_text,
        is_final=True,
        log_message="Sent compaction failure message",
        log_identifier=log_identifier
    )


async def _send_truncation_notification(
    component: "SamAgentComponent",
    a2a_context: dict,
    summary: str,
    is_background: bool = False,
    log_identifier: str = ""
):
    """
    Send a status update to the user notifying them that conversation was summarized.

    Only root tasks (no parentTaskId) send notifications. Subtasks peek at the summary
    but leave it for the root task to notify, preventing duplicate notifications when
    parallel subtasks hit context limits simultaneously.

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        summary: The summary text that replaced the old turns
        is_background: True if this is a background task, False if interactive
        log_identifier: Logging prefix
    """
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

    await _send_status_notification(
        component=component,
        a2a_context=a2a_context,
        notification_text=notification_text,
        is_final=False,
        log_message="Sent truncation notification",
        log_identifier=log_identifier
    )


async def _handle_max_retries_exceeded(
    component: "SamAgentComponent",
    a2a_context: dict,
    session_id: str,
    max_retries: int,
    logical_task_id: str,
    log_identifier: str
) -> None:
    """
    Handle the case where max compaction retries have been exceeded.

    Cleans up pending summaries and sends graceful failure message to user.

    Args:
        component: The SamAgentComponent instance
        a2a_context: The A2A context dictionary
        session_id: The session ID for cleanup
        max_retries: Maximum number of retries attempted
        logical_task_id: The task ID for logging
        log_identifier: Logging prefix
    """
    # Clean up any pending summary
    _session_summaries.pop(session_id, None)

    log.error(
        "%s Context limit exceeded after %d summarization attempts for task %s.",
        log_identifier,
        max_retries,
        logical_task_id,
    )

    # Send graceful user-facing message
    await _send_compaction_failure_message(
        component=component,
        a2a_context=a2a_context,
        log_identifier=log_identifier
    )


async def _wait_for_parallel_compaction(
    component: "SamAgentComponent",
    compaction_lock: asyncio.Lock,
    session_id: str,
    user_id: str,
    logical_task_id: str,
    log_identifier: str
) -> ADKSession:
    """
    Wait for another parallel task to complete compaction, then reload session.

    When multiple tasks hit context limits simultaneously, only one should perform
    compaction. Other tasks wait here for that compaction to complete, then reload
    the session to get the compacted state.

    Args:
        component: The SamAgentComponent instance
        compaction_lock: The asyncio.Lock being held by another task
        session_id: The session ID to reload
        user_id: The user ID for session lookup
        logical_task_id: The task ID for logging
        log_identifier: Logging prefix

    Returns:
        Reloaded session with compacted state

    Raises:
        RuntimeError: If session cannot be reloaded
    """
    log.info(
        "%s Another parallel task is compacting session %s. Waiting for completion...",
        log_identifier,
        session_id
    )

    # Wait for the other task to finish compacting
    async with compaction_lock:
        pass  # Lock released - other task completed compaction

    # Reload session to get the compacted state created by the other task
    reloaded_session = await component.session_service.get_session(
        app_name=component.agent_name,
        user_id=user_id,
        session_id=session_id
    )

    if not reloaded_session:
        log.error(
            "%s Failed to reload session after parallel compaction for task %s",
            log_identifier,
            logical_task_id
        )
        raise RuntimeError("Session disappeared after parallel compaction")

    log.info(
        "%s Parallel task completed compaction. Retrying with reduced context...",
        log_identifier
    )

    return reloaded_session


async def _perform_session_compaction(
    component: "SamAgentComponent",
    session: ADKSession,
    retry_count: int,
    max_retries: int,
    logical_task_id: str,
    log_identifier: str,
    compaction_threshold: float = 0.25
) -> tuple[ADKSession, str]:
    """
    Perform compaction on the session and store summary for deferred notification.

    This function:
    1. Creates a compaction event (summarizes old events)
    2. Reloads the session from DB to get filtered state
    3. Validates that compaction actually removed events
    4. Logs audit information
    5. Stores summary for later notification to user

    Args:
        component: The SamAgentComponent instance
        session: The ADK session to compact
        retry_count: Current retry attempt number
        max_retries: Maximum number of retries allowed
        logical_task_id: The task ID for logging
        log_identifier: Logging prefix

    Returns:
        Tuple of (reloaded_session, summary_text)

    Raises:
        RuntimeError: If session cannot be reloaded or compaction fails
    """
    log.warning(
        "%s Context limit exceeded for task %s. Performing automatic summarization (attempt %d/%d)...",
        log_identifier,
        logical_task_id,
        retry_count,
        max_retries,
    )

    # Store original count for audit logging
    original_event_count = len(session.events) if session.events else 0

    # Create compaction event
    events_removed, summary = await _create_compaction_event(
        component=component,
        session=session,
        compaction_threshold=compaction_threshold,
        log_identifier=log_identifier
    )

    # MANDATORY: Reload session from DB to get filtered state
    # FilteringSessionService automatically removes ghost events
    reloaded_session = await component.session_service.get_session(
        app_name=component.agent_name,
        user_id=session.user_id,
        session_id=session.id
    )

    if not reloaded_session:
        log.error(
            "%s Failed to reload session after compaction for task %s",
            log_identifier,
            logical_task_id
        )
        raise RuntimeError("Session disappeared after compaction")

    if events_removed == 0:
        # Can't summarize any more (not enough turns)
        log.error(
            "%s Cannot summarize further - insufficient conversation history for task %s.",
            log_identifier,
            logical_task_id,
        )
        raise RuntimeError("Insufficient conversation history for compaction")

    # Audit log with fresh session data
    new_event_count = len(reloaded_session.events) if reloaded_session.events else 0
    log.warning(
        "%s AUDIT: Summarized session %s for task %s (attempt %d/%d). "
        "Removed %d events (%d → %d total). "
        "Summary: '%s'",
        log_identifier,
        session.id,
        logical_task_id,
        retry_count,
        max_retries,
        events_removed,
        original_event_count,
        new_event_count,
        summary[:200] + "..." if len(summary) > 200 else summary
    )

    # Store summary for deferred notification
    # Overwrite any previous summary (we only want the latest)
    if session.id in _session_summaries:
        log.info(
            "%s Overriding previous compaction summary for session %s",
            log_identifier,
            session.id
        )
    _session_summaries[session.id] = summary

    log.info(
        "%s Summarization complete. Retrying task %s with reduced context...",
        log_identifier,
        logical_task_id
    )

    return reloaded_session, summary


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
    # Read auto-summarization config from component (per-agent configuration)
    auto_sum_config = component.auto_summarization_config
    compaction_enabled = auto_sum_config.get("enabled", False)
    char_threshold = auto_sum_config.get("compaction_trigger_char_limit_threshold", -1)
    compaction_percentage = auto_sum_config.get("compaction_percentage", 0.25)

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
                # Proactively trigger compaction when character count exceeds threshold
                if compaction_enabled and char_threshold > 0 and adk_session.events and adk_content.role == 'user':
                    total_chars = _calculate_total_char_count(adk_session.events)
                    if total_chars > char_threshold:
                        log.warning(
                            "%s Proactive compaction triggered: total_chars=%d exceeds threshold=%d",
                            component.log_identifier,
                            total_chars,
                            char_threshold
                        )
                        raise BadRequestError(
                            message=f"Proactive compaction: {total_chars} maximum context length exceeded {char_threshold}",
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
                if not (_is_context_limit_error(e) and compaction_enabled):
                    # Either not a context limit error, or auto-summarization is disabled
                    if _is_context_limit_error(e):
                        log.error(
                            "%s Context limit exceeded for task %s, but auto-summarization is disabled. "
                            "Enable it in the agent's auto_summarization config.",
                            component.log_identifier,
                            logical_task_id
                        )
                    raise  # Re-raise the original error

                # Context limit error with auto-summarization enabled
                retry_count += 1

                # Check if we've exceeded max retries
                if retry_count > max_retries:
                    await _handle_max_retries_exceeded(
                        component=component,
                        a2a_context=a2a_context,
                        session_id=adk_session.id,
                        max_retries=max_retries,
                        logical_task_id=logical_task_id,
                        log_identifier=component.log_identifier
                    )
                    return  # Exit cleanly - user already got the graceful message

                # Get per-session compaction lock to coordinate parallel tasks
                compaction_lock = await _get_compaction_lock(adk_session.id)

                # Check if another task is already compacting this session
                if compaction_lock.locked():
                    # Wait for parallel compaction to complete and get updated session
                    adk_session = await _wait_for_parallel_compaction(
                        component=component,
                        compaction_lock=compaction_lock,
                        session_id=adk_session.id,
                        user_id=adk_session.user_id,
                        logical_task_id=logical_task_id,
                        log_identifier=component.log_identifier
                    )
                    # Retry without doing our own compaction (other task did it)
                    continue

                # Lock is available - we'll do the compaction work
                async with compaction_lock:
                    try:
                        adk_session, _ = await _perform_session_compaction(
                            component=component,
                            session=adk_session,
                            retry_count=retry_count,
                            max_retries=max_retries,
                            logical_task_id=logical_task_id,
                            log_identifier=component.log_identifier,
                            compaction_threshold=compaction_percentage
                        )
                    except RuntimeError as rt_err:
                        # Check if this is the "Insufficient conversation history" error
                        if "Insufficient conversation history" in str(rt_err):
                            # Clean up any pending summary
                            _session_summaries.pop(adk_session.id, None)

                            # Send graceful user-facing message
                            await _send_insufficient_history_message(
                                component=component,
                                a2a_context=a2a_context,
                                log_identifier=component.log_identifier
                            )
                            return  # Exit cleanly - user already got the graceful message
                        else:
                            # Different RuntimeError - re-raise
                            raise

                # Retry with compacted session
                continue

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
        parent_task_id = a2a_context.get("original_message_metadata", {}).get("parentTaskId")

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
                    log_identifier=component.log_identifier
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
