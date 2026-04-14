"""
Tests for ADK session cloning logic (clone_adk_session).

Covers:
- Successful clone with events
- Empty source session (no events)
- Missing source session
- compaction_time stripped from cloned state
- Event ordering preserved
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_session(events=None, state=None):
    """Create a mock ADK session."""
    session = MagicMock()
    session.events = events
    session.state = state
    return session


def make_event(content="hello", role="user"):
    """Create a mock event."""
    event = MagicMock()
    event.content = content
    event.role = role
    return event


# ---------------------------------------------------------------------------
# Tests for clone_adk_session
# ---------------------------------------------------------------------------

class TestCloneAdkSession:
    """Tests for the standalone clone_adk_session function."""

    @pytest.fixture
    def session_service(self):
        svc = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_successful_clone_copies_all_events(self, session_service):
        """Clone should copy all events from source to target."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        events = [make_event("msg1"), make_event("msg2"), make_event("msg3")]
        source = make_session(events=events, state={"key": "value"})
        target = make_session(events=[])

        session_service.get_session.side_effect = [source, target]
        session_service.create_session.return_value = target

        with patch("solace_agent_mesh.agent.adk.services.append_event_with_retry", new_callable=AsyncMock) as mock_append:
            result = await clone_adk_session(
                session_service=session_service,
                app_name="test-app",
                source_user_id="owner",
                source_session_id="source-session",
                target_user_id="forker",
                target_session_id="target-session",
            )

            assert result is target
            assert mock_append.call_count == 3
            # Verify events were passed in order
            for i, call in enumerate(mock_append.call_args_list):
                assert call.kwargs["event"] is events[i]

    @pytest.mark.asyncio
    async def test_clone_strips_compaction_time_from_state(self, session_service):
        """Cloned session should not inherit compaction_time."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        events = [make_event("msg1")]
        source = make_session(
            events=events,
            state={"compaction_time": 999999, "custom_key": "keep_me"}
        )
        target = make_session(events=[])

        session_service.get_session.side_effect = [source, target]
        session_service.create_session.return_value = target

        with patch("solace_agent_mesh.agent.adk.services.append_event_with_retry", new_callable=AsyncMock):
            await clone_adk_session(
                session_service=session_service,
                app_name="test-app",
                source_user_id="owner",
                source_session_id="source-session",
                target_user_id="forker",
                target_session_id="target-session",
            )

            create_call = session_service.create_session.call_args
            state = create_call.kwargs["state"]
            assert "compaction_time" not in state
            assert state["custom_key"] == "keep_me"

    @pytest.mark.asyncio
    async def test_clone_returns_none_when_source_missing(self, session_service):
        """Clone should return None when source session doesn't exist."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        session_service.get_session.return_value = None

        result = await clone_adk_session(
            session_service=session_service,
            app_name="test-app",
            source_user_id="owner",
            source_session_id="nonexistent",
            target_user_id="forker",
            target_session_id="target-session",
        )

        assert result is None
        session_service.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_clone_returns_none_when_source_has_no_events(self, session_service):
        """Clone should return None when source session has no events."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        source = make_session(events=[], state=None)
        session_service.get_session.return_value = source

        result = await clone_adk_session(
            session_service=session_service,
            app_name="test-app",
            source_user_id="owner",
            source_session_id="empty-session",
            target_user_id="forker",
            target_session_id="target-session",
        )

        assert result is None
        session_service.create_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_clone_falls_back_to_history_attribute(self, session_service):
        """Clone should use 'history' attribute when 'events' is None."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        events = [make_event("from-history")]
        source = MagicMock(spec=[])  # No attributes by default
        source.state = None
        # Only set history, not events
        type(source).history = property(lambda self: events)
        target = make_session(events=[])

        session_service.get_session.side_effect = [source, target]
        session_service.create_session.return_value = target

        with patch("solace_agent_mesh.agent.adk.services.append_event_with_retry", new_callable=AsyncMock) as mock_append:
            result = await clone_adk_session(
                session_service=session_service,
                app_name="test-app",
                source_user_id="owner",
                source_session_id="source",
                target_user_id="forker",
                target_session_id="target",
            )

            assert result is target
            assert mock_append.call_count == 1

    @pytest.mark.asyncio
    async def test_clone_with_none_state(self, session_service):
        """Clone should handle source session with None state."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        events = [make_event("msg")]
        source = make_session(events=events, state=None)
        target = make_session(events=[])

        session_service.get_session.side_effect = [source, target]
        session_service.create_session.return_value = target

        with patch("solace_agent_mesh.agent.adk.services.append_event_with_retry", new_callable=AsyncMock):
            await clone_adk_session(
                session_service=session_service,
                app_name="test-app",
                source_user_id="owner",
                source_session_id="source",
                target_user_id="forker",
                target_session_id="target",
            )

            create_call = session_service.create_session.call_args
            assert create_call.kwargs["state"] is None

    @pytest.mark.asyncio
    async def test_clone_fetches_final_session_once(self, session_service):
        """Clone should fetch session only twice: once for source, once after all appends."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        events = [make_event("a"), make_event("b"), make_event("c")]
        source = make_session(events=events, state=None)
        target = make_session(events=[])

        session_service.get_session.side_effect = [source, target]
        session_service.create_session.return_value = target

        with patch("solace_agent_mesh.agent.adk.services.append_event_with_retry", new_callable=AsyncMock):
            await clone_adk_session(
                session_service=session_service,
                app_name="test-app",
                source_user_id="owner",
                source_session_id="source",
                target_user_id="forker",
                target_session_id="target",
            )

            # get_session called exactly twice: once for source, once for final target
            assert session_service.get_session.call_count == 2

    @pytest.mark.asyncio
    async def test_clone_method_delegates_to_standalone(self):
        """FilteringSessionService.clone_session should delegate to clone_adk_session."""
        from solace_agent_mesh.agent.adk.services import clone_adk_session

        with patch("solace_agent_mesh.agent.adk.services.clone_adk_session", new_callable=AsyncMock) as mock_clone:
            mock_clone.return_value = make_session()

            # Import and create a mock FilteringSessionService
            from solace_agent_mesh.agent.adk.services import FilteringSessionService
            svc = MagicMock(spec=FilteringSessionService)
            svc.clone_session = FilteringSessionService.clone_session.__get__(svc)

            await svc.clone_session(
                app_name="test",
                source_user_id="a",
                source_session_id="b",
                target_user_id="c",
                target_session_id="d",
            )

            mock_clone.assert_called_once()
