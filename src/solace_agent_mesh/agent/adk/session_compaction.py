"""
Session compaction state management for coordinating parallel summarization tasks.
"""

import asyncio
from cachetools import TTLCache


class SessionCompactionState:
    """
    Manages per-session coordination state for parallel compaction tasks.

    Ensures:
    - Only one task per session compacts simultaneously (via locks)
    - Deferred notifications are stored until after successful response
    - Each agent has isolated state (agent-scoped, not global)
    """

    def __init__(self):
        # Per-session locks to prevent parallel tasks from duplicating summarization
        # When multiple tasks hit context limit simultaneously, only one compacts per session
        self.locks: TTLCache = TTLCache(maxsize=10000, ttl=3600)
        self.locks_mutex = asyncio.Lock()

        # Per-session summaries for deferred notification (after successful response)
        # When compaction occurs during retries, we store the summary here instead of sending immediately
        # This ensures users see the actual response first, then a clean notification about summarization
        # TTLCache prevents memory leak if pop() doesn't run for some reason (maxsize=10000, ttl=3600)
        self._deferred_summaries: TTLCache = TTLCache(maxsize=10000, ttl=3600)

    async def get_lock(self, session_id: str) -> asyncio.Lock:
        """
        Get or create an asyncio.Lock for the given session_id.

        Ensures only one task per session can perform compaction at a time.
        When multiple parallel tasks hit context limits, they coordinate via this lock.

        Args:
            session_id: The ADK session ID

        Returns:
            asyncio.Lock instance for this session
        """
        async with self.locks_mutex:
            if session_id not in self.locks:
                self.locks[session_id] = asyncio.Lock()
            else:
                # Re-insert to reset TTL on access (idle timeout behavior)
                lock = self.locks.pop(session_id)
                self.locks[session_id] = lock
            return self.locks[session_id]

    def store_summary(self, session_id: str, summary: str) -> None:
        """
        Store a deferred notification summary for a session.

        The summary will be sent to the user after the task completes successfully.
        If a summary already exists, it will be overwritten (keeping only the latest).

        Args:
            session_id: The session ID
            summary: The summary text to store
        """
        self._deferred_summaries[session_id] = summary

    def get_summary(self, session_id: str) -> str | None:
        """
        Peek at a deferred summary without removing it.

        Used by subtasks that want to check if compaction happened without consuming
        the summary (leaving it for the root task to notify).

        Args:
            session_id: The session ID

        Returns:
            The summary text if it exists, None otherwise
        """
        return self._deferred_summaries.get(session_id)

    def pop_summary(self, session_id: str) -> str | None:
        """
        Retrieve and remove a deferred summary.

        Used by root tasks after successful response to consume and send the notification.

        Args:
            session_id: The session ID

        Returns:
            The summary text if it exists, None otherwise
        """
        return self._deferred_summaries.pop(session_id, None)