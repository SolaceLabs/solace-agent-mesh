"""
Tests for the append_event_with_retry helper function.

This function handles stale session race conditions that occur when the Google ADK's
DatabaseSessionService validates that the session object's `last_update_time` is not
older than the database's `update_timestamp_tz`.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from solace_agent_mesh.agent.adk.services import (
    append_event_with_retry,
    STALE_SESSION_MAX_RETRIES,
    STALE_SESSION_ERROR_SUBSTRING,
)


@pytest.fixture
def mock_session_service():
    """Create a mock session service."""
    service = MagicMock()
    service.append_event = AsyncMock()
    service.get_session = AsyncMock()
    return service


@pytest.fixture
def mock_session():
    """Create a mock ADK session."""
    session = MagicMock()
    session.id = "test-session-id"
    session.user_id = "test-user-id"
    return session


@pytest.fixture
def mock_event():
    """Create a mock ADK event."""
    event = MagicMock()
    event.id = "test-event-id"
    return event


class TestAppendEventWithRetrySuccess:
    """Tests for successful append_event operations."""

    @pytest.mark.asyncio
    async def test_append_event_success_first_try(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that append_event succeeds on the first try."""
        mock_session_service.append_event.return_value = mock_event

        result = await append_event_with_retry(
            session_service=mock_session_service,
            session=mock_session,
            event=mock_event,
            app_name="test-app",
            user_id="test-user",
            session_id="test-session",
            log_identifier="[Test]",
        )

        assert result == mock_event
        mock_session_service.append_event.assert_called_once_with(
            session=mock_session, event=mock_event
        )
        mock_session_service.get_session.assert_not_called()


class TestAppendEventWithRetryStaleSession:
    """Tests for stale session retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_stale_session_error(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that stale session error triggers retry with fresh session."""
        stale_error = ValueError(
            f"The last_update_time provided in the session object '2026-01-30 19:34:32' is "
            f"{STALE_SESSION_ERROR_SUBSTRING} '2026-01-30 19:34:41'. Please check if it is a stale session."
        )
        fresh_session = MagicMock()
        fresh_session.id = "test-session-id"

        # First call fails with stale session, second succeeds
        mock_session_service.append_event.side_effect = [stale_error, mock_event]
        mock_session_service.get_session.return_value = fresh_session

        result = await append_event_with_retry(
            session_service=mock_session_service,
            session=mock_session,
            event=mock_event,
            app_name="test-app",
            user_id="test-user",
            session_id="test-session",
            log_identifier="[Test]",
        )

        assert result == mock_event
        assert mock_session_service.append_event.call_count == 2
        mock_session_service.get_session.assert_called_once_with(
            app_name="test-app",
            user_id="test-user",
            session_id="test-session",
        )

    @pytest.mark.asyncio
    async def test_retry_multiple_times_before_success(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that multiple retries work before eventual success."""
        stale_error = ValueError(
            f"Session {STALE_SESSION_ERROR_SUBSTRING} error"
        )
        fresh_session = MagicMock()
        fresh_session.id = "test-session-id"

        # Fail twice, then succeed on third attempt
        mock_session_service.append_event.side_effect = [
            stale_error,
            stale_error,
            mock_event,
        ]
        mock_session_service.get_session.return_value = fresh_session

        result = await append_event_with_retry(
            session_service=mock_session_service,
            session=mock_session,
            event=mock_event,
            app_name="test-app",
            user_id="test-user",
            session_id="test-session",
            log_identifier="[Test]",
        )

        assert result == mock_event
        assert mock_session_service.append_event.call_count == 3
        assert mock_session_service.get_session.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that ValueError is raised after max retries exceeded."""
        stale_error = ValueError(
            f"Session {STALE_SESSION_ERROR_SUBSTRING} error"
        )
        fresh_session = MagicMock()
        fresh_session.id = "test-session-id"

        # Always fail with stale session error
        mock_session_service.append_event.side_effect = stale_error
        mock_session_service.get_session.return_value = fresh_session

        with pytest.raises(ValueError) as exc_info:
            await append_event_with_retry(
                session_service=mock_session_service,
                session=mock_session,
                event=mock_event,
                app_name="test-app",
                user_id="test-user",
                session_id="test-session",
                log_identifier="[Test]",
            )

        assert STALE_SESSION_ERROR_SUBSTRING in str(exc_info.value)
        # Initial attempt + max_retries
        assert mock_session_service.append_event.call_count == STALE_SESSION_MAX_RETRIES + 1
        assert mock_session_service.get_session.call_count == STALE_SESSION_MAX_RETRIES

    @pytest.mark.asyncio
    async def test_custom_max_retries(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that custom max_retries parameter is respected."""
        stale_error = ValueError(
            f"Session {STALE_SESSION_ERROR_SUBSTRING} error"
        )
        fresh_session = MagicMock()
        fresh_session.id = "test-session-id"

        # Always fail with stale session error
        mock_session_service.append_event.side_effect = stale_error
        mock_session_service.get_session.return_value = fresh_session

        custom_max_retries = 5

        with pytest.raises(ValueError):
            await append_event_with_retry(
                session_service=mock_session_service,
                session=mock_session,
                event=mock_event,
                app_name="test-app",
                user_id="test-user",
                session_id="test-session",
                max_retries=custom_max_retries,
                log_identifier="[Test]",
            )

        # Initial attempt + custom_max_retries
        assert mock_session_service.append_event.call_count == custom_max_retries + 1
        assert mock_session_service.get_session.call_count == custom_max_retries


class TestAppendEventWithRetryNonStaleErrors:
    """Tests for non-stale session errors."""

    @pytest.mark.asyncio
    async def test_non_stale_value_error_not_retried(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that non-stale ValueError is raised immediately without retry."""
        non_stale_error = ValueError("Some other validation error")

        mock_session_service.append_event.side_effect = non_stale_error

        with pytest.raises(ValueError) as exc_info:
            await append_event_with_retry(
                session_service=mock_session_service,
                session=mock_session,
                event=mock_event,
                app_name="test-app",
                user_id="test-user",
                session_id="test-session",
                log_identifier="[Test]",
            )

        assert "Some other validation error" in str(exc_info.value)
        mock_session_service.append_event.assert_called_once()
        mock_session_service.get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_other_exception_not_retried(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that non-ValueError exceptions are raised immediately."""
        runtime_error = RuntimeError("Database connection failed")

        mock_session_service.append_event.side_effect = runtime_error

        with pytest.raises(RuntimeError) as exc_info:
            await append_event_with_retry(
                session_service=mock_session_service,
                session=mock_session,
                event=mock_event,
                app_name="test-app",
                user_id="test-user",
                session_id="test-session",
                log_identifier="[Test]",
            )

        assert "Database connection failed" in str(exc_info.value)
        mock_session_service.append_event.assert_called_once()
        mock_session_service.get_session.assert_not_called()


class TestAppendEventWithRetrySessionRefetch:
    """Tests for session re-fetch behavior."""

    @pytest.mark.asyncio
    async def test_session_not_found_on_refetch(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that ValueError is raised if session not found during retry."""
        stale_error = ValueError(
            f"Session {STALE_SESSION_ERROR_SUBSTRING} error"
        )

        mock_session_service.append_event.side_effect = stale_error
        mock_session_service.get_session.return_value = None  # Session not found

        with pytest.raises(ValueError) as exc_info:
            await append_event_with_retry(
                session_service=mock_session_service,
                session=mock_session,
                event=mock_event,
                app_name="test-app",
                user_id="test-user",
                session_id="test-session",
                log_identifier="[Test]",
            )

        assert "not found during stale session retry" in str(exc_info.value)
        mock_session_service.append_event.assert_called_once()
        mock_session_service.get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_fresh_session_used_for_retry(
        self, mock_session_service, mock_session, mock_event
    ):
        """Test that the fresh session is used for retry attempts."""
        stale_error = ValueError(
            f"Session {STALE_SESSION_ERROR_SUBSTRING} error"
        )
        fresh_session = MagicMock()
        fresh_session.id = "fresh-session-id"

        mock_session_service.append_event.side_effect = [stale_error, mock_event]
        mock_session_service.get_session.return_value = fresh_session

        await append_event_with_retry(
            session_service=mock_session_service,
            session=mock_session,
            event=mock_event,
            app_name="test-app",
            user_id="test-user",
            session_id="test-session",
            log_identifier="[Test]",
        )

        # Verify the second call used the fresh session
        calls = mock_session_service.append_event.call_args_list
        assert calls[0].kwargs["session"] == mock_session
        assert calls[1].kwargs["session"] == fresh_session


class TestAppendEventWithRetryConstants:
    """Tests for module constants."""

    def test_stale_session_max_retries_default(self):
        """Test that the default max retries is reasonable."""
        assert STALE_SESSION_MAX_RETRIES == 3

    def test_stale_session_error_substring(self):
        """Test that the error substring matches the ADK error message."""
        assert "earlier than the update_time in the storage_session" in STALE_SESSION_ERROR_SUBSTRING
