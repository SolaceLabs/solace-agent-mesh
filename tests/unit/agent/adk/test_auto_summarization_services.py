"""
Unit tests for auto-summarization functionality in services.py
"""
import pytest
from unittest.mock import AsyncMock, Mock
from google.adk.events import Event as ADKEvent
from google.adk.events.event_actions import EventActions, EventCompaction
from google.adk.sessions import Session as ADKSession
from google.genai import types as adk_types
from solace_agent_mesh.agent.adk.services import (
    _filter_session_by_latest_compaction,
    FilteringSessionService,
)


class TestFilterSessionByLatestCompaction:
    """Tests for _filter_session_by_latest_compaction function."""

    def test_returns_session_unchanged_when_no_compaction_time(self):
        """Session without compaction_time should be returned unchanged."""
        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={},
            events=[
                ADKEvent(
                    invocation_id="e1",
                    author="user",
                    content=adk_types.Content(
                        role="user",
                        parts=[adk_types.Part(text="Hello")]
                    ),
                    timestamp=1.0
                ),
            ]
        )

        result = _filter_session_by_latest_compaction(session)
        assert result == session
        assert len(result.events) == 1

    def test_returns_none_when_session_is_none(self):
        """Should handle None session gracefully."""
        result = _filter_session_by_latest_compaction(None)
        assert result is None

    def test_returns_session_unchanged_when_events_empty(self):
        """Session with empty events should be returned unchanged."""
        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={"compaction_time": 2.0},
            events=[]
        )

        result = _filter_session_by_latest_compaction(session)
        assert result == session
        assert len(result.events) == 0

    def test_filters_events_before_compaction_timestamp(self):
        """Events before compaction timestamp should be filtered out."""
        compaction_ts = 5.0
        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={"compaction_time": compaction_ts},
            events=[
                # Old events (should be filtered)
                ADKEvent(
                    invocation_id="e1",
                    author="user",
                    content=adk_types.Content(
                        role="user",
                        parts=[adk_types.Part(text="Old message 1")]
                    ),
                    timestamp=1.0
                ),
                ADKEvent(
                    invocation_id="e2",
                    author="model",
                    content=adk_types.Content(
                        role="model",
                        parts=[adk_types.Part(text="Old response 1")]
                    ),
                    timestamp=2.0
                ),
                # Compaction event
                ADKEvent(
                    invocation_id="comp",
                    author="model",
                    content=adk_types.Content(
                        role="model",
                        parts=[adk_types.Part(text="Summary")]
                    ),
                    timestamp=5.0,
                    actions=EventActions(
                        compaction=EventCompaction(
                            start_timestamp=1.0,
                            end_timestamp=compaction_ts,
                            compacted_content=adk_types.Content(
                                role="model",
                                parts=[adk_types.Part(text="Summary of old messages")]
                            )
                        )
                    )
                ),
                # New events (should be kept)
                ADKEvent(
                    invocation_id="e3",
                    author="user",
                    content=adk_types.Content(
                        role="user",
                        parts=[adk_types.Part(text="New message")]
                    ),
                    timestamp=6.0
                ),
            ]
        )

        result = _filter_session_by_latest_compaction(session)
        assert len(result.events) == 2  # Compaction + 1 new event
        assert result.events[0].invocation_id == "comp"
        assert result.events[1].invocation_id == "e3"

    def test_keeps_only_latest_compaction_when_multiple_exist(self):
        """When multiple compaction events match timestamp, keep only the last one."""
        compaction_ts = 5.0
        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={"compaction_time": compaction_ts},
            events=[
                # First compaction (should be filtered)
                ADKEvent(
                    invocation_id="comp1",
                    author="model",
                    timestamp=5.0,
                    actions=EventActions(
                        compaction=EventCompaction(
                            start_timestamp=1.0,
                            end_timestamp=compaction_ts,
                            compacted_content=adk_types.Content(
                                role="model",
                                parts=[adk_types.Part(text="First summary")]
                            )
                        )
                    )
                ),
                # Second compaction (should be kept)
                ADKEvent(
                    invocation_id="comp2",
                    author="model",
                    timestamp=5.0,
                    actions=EventActions(
                        compaction=EventCompaction(
                            start_timestamp=1.0,
                            end_timestamp=compaction_ts,
                            compacted_content=adk_types.Content(
                                role="model",
                                parts=[adk_types.Part(text="Second summary")]
                            )
                        )
                    )
                ),
                # New event
                ADKEvent(
                    invocation_id="e1",
                    author="user",
                    timestamp=6.0,
                    content=adk_types.Content(
                        role="user",
                        parts=[adk_types.Part(text="New")]
                    )
                ),
            ]
        )

        result = _filter_session_by_latest_compaction(session)
        assert len(result.events) == 2
        assert result.events[0].invocation_id == "comp2"  # Latest compaction
        assert result.events[1].invocation_id == "e1"

    def test_sets_content_on_compaction_event_from_compacted_content(self):
        """Compaction event should have .content set from .actions.compaction.compacted_content."""
        compaction_ts = 5.0
        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={"compaction_time": compaction_ts},
            events=[
                ADKEvent(
                    invocation_id="comp",
                    author="model",
                    timestamp=5.0,
                    actions=EventActions(
                        compaction=EventCompaction(
                            start_timestamp=1.0,
                            end_timestamp=compaction_ts,
                            compacted_content=adk_types.Content(
                                role="model",
                                parts=[adk_types.Part(text="Summary text")]
                            )
                        )
                    )
                ),
            ]
        )

        result = _filter_session_by_latest_compaction(session)
        assert len(result.events) == 1
        comp_event = result.events[0]
        assert comp_event.content is not None
        assert comp_event.content.role == "model"
        assert len(comp_event.content.parts) == 1
        assert comp_event.content.parts[0].text == "Summary text"

    def test_handles_dict_form_compacted_content(self):
        """Should handle compacted_content in dict form (from DB)."""
        compaction_ts = 5.0

        # Create compaction with dict-form compacted_content
        compaction_dict = {
            "start_timestamp": 1.0,
            "end_timestamp": compaction_ts,
            "compacted_content": {
                "role": "model",
                "parts": [{"text": "Dict summary"}]
            }
        }

        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={"compaction_time": compaction_ts},
            events=[
                ADKEvent(
                    invocation_id="comp",
                    author="model",
                    timestamp=5.0,
                    actions=EventActions(compaction=compaction_dict)
                ),
            ]
        )

        result = _filter_session_by_latest_compaction(session)
        comp_event = result.events[0]
        assert comp_event.content is not None
        assert comp_event.content.parts[0].text == "Dict summary"


class TestFilteringSessionService:
    """Tests for FilteringSessionService wrapper."""

    @pytest.mark.asyncio
    async def test_get_session_applies_filtering(self):
        """get_session should apply compaction filtering."""
        # Create mock wrapped service
        wrapped = AsyncMock()

        # Create session with compaction
        compaction_ts = 5.0
        session = ADKSession(
            app_name="test",
            user_id="user1",
            id="session1",
            state={"compaction_time": compaction_ts},
            events=[
                ADKEvent(
                    invocation_id="e1",
                    author="user",
                    timestamp=1.0,
                    content=adk_types.Content(
                        role="user",
                        parts=[adk_types.Part(text="Old")]
                    )
                ),
                ADKEvent(
                    invocation_id="comp",
                    author="model",
                    timestamp=5.0,
                    actions=EventActions(
                        compaction=EventCompaction(
                            start_timestamp=1.0,
                            end_timestamp=compaction_ts,
                            compacted_content=adk_types.Content(
                                role="model",
                                parts=[adk_types.Part(text="Summary")]
                            )
                        )
                    )
                ),
                ADKEvent(
                    invocation_id="e2",
                    author="user",
                    timestamp=6.0,
                    content=adk_types.Content(
                        role="user",
                        parts=[adk_types.Part(text="New")]
                    )
                ),
            ]
        )
        wrapped.get_session.return_value = session

        # Create filtering wrapper
        filtering_service = FilteringSessionService(wrapped)

        # Call get_session
        result = await filtering_service.get_session(
            app_name="test",
            user_id="user1",
            session_id="session1"
        )

        # Verify wrapped service was called
        wrapped.get_session.assert_called_once_with(
            app_name="test",
            user_id="user1",
            session_id="session1",
            config=None
        )

        # Verify filtering was applied (old event removed)
        assert len(result.events) == 2
        assert result.events[0].invocation_id == "comp"
        assert result.events[1].invocation_id == "e2"

    @pytest.mark.asyncio
    async def test_create_session_delegates_to_wrapped(self):
        """create_session should delegate to wrapped service."""
        wrapped = AsyncMock()
        expected_session = ADKSession(
            app_name="test",
            user_id="user1",
            id="new_session"
        )
        wrapped.create_session.return_value = expected_session

        filtering_service = FilteringSessionService(wrapped)

        result = await filtering_service.create_session(
            app_name="test",
            user_id="user1",
            state={"key": "value"},
            session_id="new_session"
        )

        wrapped.create_session.assert_called_once_with(
            app_name="test",
            user_id="user1",
            state={"key": "value"},
            session_id="new_session"
        )
        assert result == expected_session

    @pytest.mark.asyncio
    async def test_delete_session_delegates_to_wrapped(self):
        """delete_session should delegate to wrapped service."""
        wrapped = AsyncMock()
        filtering_service = FilteringSessionService(wrapped)

        await filtering_service.delete_session(
            app_name="test",
            user_id="user1",
            session_id="session1"
        )

        wrapped.delete_session.assert_called_once_with(
            app_name="test",
            user_id="user1",
            session_id="session1"
        )

    @pytest.mark.asyncio
    async def test_list_sessions_delegates_to_wrapped(self):
        """list_sessions should delegate to wrapped service."""
        wrapped = AsyncMock()
        expected_sessions = ["session1", "session2"]
        wrapped.list_sessions.return_value = expected_sessions

        filtering_service = FilteringSessionService(wrapped)

        result = await filtering_service.list_sessions(
            app_name="test",
            user_id="user1"
        )

        wrapped.list_sessions.assert_called_once_with(
            app_name="test",
            user_id="user1"
        )
        assert result == expected_sessions

    @pytest.mark.asyncio
    async def test_append_event_delegates_to_wrapped(self):
        """append_event should delegate to wrapped service."""
        wrapped = AsyncMock()
        session = ADKSession(app_name="test", user_id="user1", id="session1")
        event = ADKEvent(invocation_id="e1", author="user")
        wrapped.append_event.return_value = event

        filtering_service = FilteringSessionService(wrapped)

        result = await filtering_service.append_event(session, event)

        wrapped.append_event.assert_called_once_with(session, event)
        assert result == event