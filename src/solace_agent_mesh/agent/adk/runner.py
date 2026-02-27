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
from .models.lite_llm import _calculate_content_tokens

log = logging.getLogger(__name__)


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


def _get_test_token_threshold() -> int:
    """
    Get the TEST_TOKEN_TRIGGER_THRESHOLD from environment variable.

    This must be called at runtime (not module import time) to ensure pytest_configure
    has already set the env var in test mode.

    Returns:
        Token threshold value, or -1 if not set (test mode disabled)
    """
    return int(os.getenv("TEST_TOKEN_TRIGGER_THRESHOLD", "-1"))


def _is_test_mode_trigger_enabled() -> bool:
    """
    Check if test mode compaction is enabled via TEST_TOKEN_TRIGGER_THRESHOLD env var.

    Returns:
        True if TEST_TOKEN_TRIGGER_THRESHOLD > 0 (test mode enabled), False otherwise
    """
    return _get_test_token_threshold() > 0


def _calculate_session_context_tokens(events: list[ADKEvent], model: str = "gpt-4-vision") -> int:
    """
    Calculate total tokens the LLM will receive for this session.

    Counts ALL events that will be sent to the LLM:
    - User messages
    - Model responses
    - System events
    - Compaction events with summaries
    - Everything with content that contributes to context window

    This includes text, images, videos, and all binary content types.

    Args:
        events: Session events
        model: LLM model for token counting (default: gpt-4-vision)

    Returns:
        Total tokens that will be used in LLM context window
    """
    if not events:
        return 0

    total_tokens = 0

    # Count tokens for each event individually
    for idx, event in enumerate(events):
        if event.content:
            try:
                tokens = _calculate_content_tokens(event.content, model=model)
                log.debug(
                    "Event[%d] role=%s tokens=%d",
                    idx,
                    event.content.role if hasattr(event.content, 'role') else 'unknown',
                    tokens
                )
                total_tokens += tokens
            except Exception as e:
                log.warning(
                    "Failed to count event tokens for event[%d]: %s",
                    idx,
                    e
                )
                continue

    log.info(
        "Session total tokens: %d (from %d events with content)",
        total_tokens,
        sum(1 for e in events if e.content)
    )
    return total_tokens


def _test_and_trigger_compaction(
    test_token_threshold: int,
    adk_session: ADKSession,
    component: Any
) -> None:
    """
    Test token count against TEST_TOKEN_TRIGGER_THRESHOLD and trigger compaction error if exceeded.
    This is used only for unit/integration and manual testing to force proactive compaction trigger.
    Raises BadRequestError if token count exceeds threshold, which triggers the retry loop
    with automatic summarization.

    Args:
        TEST_TOKEN_TRIGGER_THRESHOLD: Token threshold from TEST_TOKEN_TRIGGER_THRESHOLD env var
        adk_session: The ADK session with events
        component: The SamAgentComponent for logging and model info

    Raises:
        BadRequestError: If token count exceeds threshold (triggers compaction retry loop)
    """
    total_tokens = _calculate_session_context_tokens(adk_session.events, model=str(component.adk_agent.model))
    log.info(
        "%s Proactive compaction check: total_tokens=%d, threshold=%d, exceeds=%s",
        component.log_identifier,
        total_tokens,
        test_token_threshold,
        total_tokens > test_token_threshold
    )

    if total_tokens > test_token_threshold:
        log.warning(
            "%s Proactive compaction triggered: total_tokens=%d exceeds threshold=%d",
            component.log_identifier,
            total_tokens,
            test_token_threshold
        )
        # Extract provider from model string (format: "provider/model-name")
        model_str = str(component.adk_agent.model)
        provider = model_str.split('/')[0] if '/' in model_str else model_str
        raise BadRequestError(
            message=f"Too many tokens: {total_tokens} tokens exceed token limit {test_token_threshold} (proactive compaction triggered)",
            model=model_str,
            llm_provider=provider
        )


def _find_compaction_cutoff(
    events: list[ADKEvent],
    target_tokens: int,
    log_identifier: str = "",
    model: str = "gpt-4-vision"
) -> tuple[int, int]:
    """
    Find the cutoff index that gets closest to target token count.

    O(N) efficient algorithm:
    1. Pre-calculates tokens for all events once (N token_counter calls)
    2. Builds cumulative sum array (N math operations)
    3. Finds best cutoff using array lookups (M binary searches, M << N)

    Always cuts at user turn boundaries (complete interactions).
    Ensures at least 1 user turn remains uncompacted.

    Args:
        events: All conversation events (non-compaction, non-system)
        target_tokens: Target number of tokens to compact
        log_identifier: Logging prefix
        model: LLM model for token counting (default: gpt-4-vision)

    Returns:
        Tuple of (cutoff_index, actual_tokens_to_compact)
        - cutoff_index: Index where to cut (events[:cutoff_index] get compacted)
        - actual_tokens_to_compact: Actual token count up to cutoff
    """
    if not events:
        return 0, 0

    # Find all user turn indices
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

    # OPTIMIZATION: Pre-calculate tokens and build cumulative sum in single pass (O(N))
    import time

    start_time = time.time()
    cumulative_tokens = [0]
    for event in events:
        if event.content:
            try:
                tokens = _calculate_content_tokens(event.content, model=model)
            except Exception as e:
                log.warning("Failed to count event tokens: %s", e)
                tokens = 0
        else:
            tokens = 0
        cumulative_tokens.append(cumulative_tokens[-1] + tokens)

    elapsed = time.time() - start_time
    log.info(
        "%s Pre-calculated tokens for %d events in %.2f seconds",
        log_identifier,
        len(events),
        elapsed
    )

    # Find best cutoff using cumulative array (O(M) where M = number of user turns << N)
    best_cutoff_idx = 0
    best_token_count = 0
    best_distance = float('inf')

    for turn_idx in range(len(user_indices) - 1):
        # The cutoff will be at the NEXT user turn (to include complete interactions)
        cutoff_idx = user_indices[turn_idx + 1]

        # O(1) lookup: get cumulative tokens up to this cutoff
        token_count = cumulative_tokens[cutoff_idx]

        # Check if this is closest to target
        distance = abs(token_count - target_tokens)
        if distance < best_distance:
            best_distance = distance
            best_cutoff_idx = cutoff_idx
            best_token_count = token_count

    log.info(
        "%s Found cutoff at turn boundary (index=%d): %d tokens (target: %d, diff: %d)",
        log_identifier,
        best_cutoff_idx,
        best_token_count,
        target_tokens,
        abs(best_token_count - target_tokens)
    )

    return best_cutoff_idx, best_token_count

async def _create_compaction_event(
    component: "SamAgentComponent",
    session: ADKSession,
    compaction_threshold: float = 0.25,
    log_identifier: str = ""
) -> tuple[int, str]:
    """
    Create a compaction event using percentage-based progressive summarization.
    Strategy:
    1. Calculate total token count across all conversation events
    2. Determine target compaction size (total_tokens * compaction_threshold)
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

    # 2. Calculate total token count and target compaction size
    # Use non_compaction_events (includes system + conversation) for consistency
    # with proactive trigger logic
    total_tokens = _calculate_session_context_tokens(non_compaction_events, model=str(component.adk_agent.model))
    target_tokens = int(total_tokens * compaction_threshold)

    log.info(
        "%s Compaction target: %d total tokens * %.1f%% = %d target tokens",
        log_identifier,
        total_tokens,
        compaction_threshold * 100,
        target_tokens
    )

    # 3. Find cutoff point using target token count
    # This finds the user turn boundary closest to our target percentage
    # Pass ALL non_compaction_events to match our total_tokens calculation
    cutoff_idx, actual_tokens = _find_compaction_cutoff(
        events=non_compaction_events,
        target_tokens=target_tokens,
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
            "%s Compacting %d events: [PREVIOUS_SUMMARY + %d new events (%d tokens)]",
            log_identifier,
            len(events_to_compact),
            len(events_to_compact) - 1,  # -1 for fake summary event
            actual_tokens
        )
    else:
        log.info(
            "%s Compacting %d events (%d tokens) - no previous summary",
            log_identifier,
            len(events_to_compact),
            actual_tokens
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
            f"**ℹ️ Note:** Conversation history was automatically summarized to stay within limits.\n\n"
            f"**Summary of earlier messages:**\n\n"
            f"*{summary}*\n\n"
            f"---\n"
        )
    else:
        notification_text = (
            f"\n\n---\n\n"
            f"**ℹ️ Your conversation history reached the limit. We automatically summarized your older messages to keep things running smoothly. All important context is preserved, so you can keep chatting seamlessly.**\n\n"
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
    component.session_compaction_state.pop_summary(session_id)

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
    if component.session_compaction_state.get_summary(session.id):
        log.info(
            "%s Overriding previous compaction summary for session %s",
            log_identifier,
            session.id
        )
    component.session_compaction_state.store_summary(session.id, summary)

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
                # Check if test mode compaction is enabled and should trigger, will always be false for prod.
                if _is_test_mode_trigger_enabled() and compaction_enabled and adk_session.events and adk_content.role == 'user':
                    _test_and_trigger_compaction(_get_test_token_threshold(), adk_session, component)

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
                compaction_lock = await component.session_compaction_state.get_lock(adk_session.id)

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
                            component.session_compaction_state.pop_summary(adk_session.id)

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
            summary = component.session_compaction_state.get_summary(adk_session.id)
            if summary:
                log.info(
                    "%s Subtask compacted (parent: %s) - leaving summary for root task to notify",
                    component.log_identifier,
                    parent_task_id
                )
        else:
            # Root task - consume and send notification
            summary = component.session_compaction_state.pop_summary(adk_session.id)
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
