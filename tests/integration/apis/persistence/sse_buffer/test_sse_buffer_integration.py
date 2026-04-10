"""
Integration tests for PersistentSSEEventBuffer with real database.

Tests SSE event buffering, flushing, and cleanup against real databases (SQLite and PostgreSQL).
These replace the DB-mocking tests in tests/unit/gateway/http_sse/test_persistent_sse_buffer_comprehensive.py
which patched SSEEventBufferRepository.

Uses the existing integration test infrastructure with real test containers.
"""

import sqlalchemy as sa
from fastapi.testclient import TestClient

from solace_agent_mesh.gateway.http_sse.persistent_sse_event_buffer import (
    PersistentSSEEventBuffer,
)
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms
from tests.integration.apis.infrastructure.database_inspector import DatabaseInspector
from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter


class TestPersistentSSEBufferWithRealDB:
    """Integration tests for PersistentSSEEventBuffer with real database."""

    def test_get_task_metadata_from_database(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test retrieving task metadata from database when not in cache."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True
        )

        # Create session and task in DB
        session = gateway_adapter.create_session(
            user_id="user-456", agent_name="TestAgent"
        )

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            tasks_table = metadata.tables["tasks"]

            task_id = "task-db-meta-1"
            now = now_epoch_ms()

            conn.execute(
                sa.insert(tasks_table).values(
                    id=task_id,
                    user_id="user-456",
                    session_id=session.id,
                    start_time=now,
                    status="running",
                )
            )
            conn.commit()

        # Act: Get metadata (should fetch from DB and cache it)
        metadata_result = buffer.get_task_metadata(task_id)

        # Assert: Metadata retrieved from DB
        assert metadata_result is not None
        assert metadata_result["session_id"] == session.id
        assert metadata_result["user_id"] == "user-456"

        # Assert: Now cached
        assert task_id in buffer._task_metadata_cache

    def test_buffer_event_normal_mode_writes_to_db(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that normal mode writes events directly to database."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory,
            enabled=True,
            hybrid_mode_enabled=False,  # Normal mode
        )

        # Act: Buffer an event
        result = buffer.buffer_event(
            "task-normal-1",
            "message",
            {"text": "test event"},
            session_id="session-abc",
            user_id="user-xyz",
        )

        # Assert: Operation succeeded
        assert result is True

        # Assert: Event was written to DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            events = conn.execute(
                sa.select(sse_buffer_table).where(
                    sse_buffer_table.c.task_id == "task-normal-1"
                )
            ).fetchall()

            assert len(events) == 1
            assert events[0].event_type == "message"
            assert events[0].consumed in [False, 0]

    def test_buffer_event_hybrid_mode_uses_ram_then_flushes(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that hybrid mode buffers to RAM then flushes at threshold."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=3,  # Flush after 3 events
        )

        task_id = "task-hybrid-1"

        # Add 2 events - should stay in RAM
        buffer.buffer_event(
            task_id, "event1", {"data": "1"}, session_id="s1", user_id="u1"
        )
        buffer.buffer_event(
            task_id, "event2", {"data": "2"}, session_id="s1", user_id="u1"
        )

        # Assert: Events in RAM buffer
        assert buffer.get_ram_buffer_size(task_id) == 2

        # Assert: NOT yet in database
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            db_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert db_count == 0

        # Add 3rd event - should trigger auto-flush
        buffer.buffer_event(
            task_id, "event3", {"data": "3"}, session_id="s1", user_id="u1"
        )

        # Assert: RAM buffer flushed
        ram_size_after = buffer.get_ram_buffer_size(task_id)
        assert ram_size_after == 0

        # Assert: Events now in database
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            db_count_after = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert db_count_after == 3

    def test_flush_task_buffer_writes_to_db_and_clears_ram(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that manual flush writes RAM events to DB and clears buffer."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,  # High threshold - no auto-flush
        )

        task_id = "task-manual-flush"

        # Buffer 2 events to RAM
        buffer.buffer_event(task_id, "evt1", {"a": 1}, session_id="s1", user_id="u1")
        buffer.buffer_event(task_id, "evt2", {"b": 2}, session_id="s1", user_id="u1")

        # Verify in RAM
        assert buffer.get_ram_buffer_size(task_id) == 2

        # Act: Manual flush
        flushed_count = buffer.flush_task_buffer(task_id)

        # Assert: 2 events flushed
        assert flushed_count == 2

        # Assert: RAM buffer cleared
        assert buffer.get_ram_buffer_size(task_id) == 0

        # Assert: Events in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            db_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert db_count == 2

    def test_get_buffered_events_returns_from_db(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that get_buffered_events retrieves events from database."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        task_id = "task-get-events"

        # Buffer 3 events directly to DB (normal mode)
        buffer.buffer_event(
            task_id, "event1", {"num": 1}, session_id="s1", user_id="u1"
        )
        buffer.buffer_event(
            task_id, "event2", {"num": 2}, session_id="s1", user_id="u1"
        )
        buffer.buffer_event(
            task_id, "event3", {"num": 3}, session_id="s1", user_id="u1"
        )

        # Act: Retrieve buffered events
        events = buffer.get_buffered_events(task_id, mark_consumed=False)

        # Assert: 3 events retrieved
        assert len(events) == 3
        event_types = [e["type"] for e in events]
        assert "event1" in event_types
        assert "event2" in event_types
        assert "event3" in event_types

    def test_get_buffered_events_marks_consumed_in_db(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that mark_consumed flag updates database."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        task_id = "task-consume"

        # Buffer event
        buffer.buffer_event(
            task_id, "event1", {"data": "test"}, session_id="s1", user_id="u1"
        )

        # Verify not consumed in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            consumed_before = conn.execute(
                sa.select(sse_buffer_table.c.consumed).where(
                    sse_buffer_table.c.task_id == task_id
                )
            ).scalar()
            assert consumed_before in [False, 0]

        # Act: Get events with mark_consumed=True
        buffer.get_buffered_events(task_id, mark_consumed=True)

        # Assert: Event marked as consumed in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            consumed_after = conn.execute(
                sa.select(sse_buffer_table.c.consumed).where(
                    sse_buffer_table.c.task_id == task_id
                )
            ).scalar()
            assert consumed_after in [True, 1]

    def test_delete_events_for_task_removes_from_db(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that delete_events_for_task removes events from database."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        task_id = "task-delete"

        # Buffer 2 events
        buffer.buffer_event(task_id, "evt1", {}, session_id="s1", user_id="u1")
        buffer.buffer_event(task_id, "evt2", {}, session_id="s1", user_id="u1")

        # Verify in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            count_before = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert count_before == 2

        # Act: Delete events
        deleted = buffer.delete_events_for_task(task_id)

        # Assert: 2 events deleted
        assert deleted == 2

        # Assert: Removed from DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            count_after = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert count_after == 0

    def test_delete_events_clears_ram_and_db_in_hybrid(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test delete removes events from both RAM and DB in hybrid mode."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,  # No auto-flush
        )

        task_id = "task-delete-hybrid"

        # Add 2 events to RAM
        buffer.buffer_event(task_id, "ram1", {}, session_id="s1", user_id="u1")
        buffer.buffer_event(task_id, "ram2", {}, session_id="s1", user_id="u1")

        # Manually flush to DB
        buffer.flush_task_buffer(task_id)

        # Add 1 more to RAM
        buffer.buffer_event(task_id, "ram3", {}, session_id="s1", user_id="u1")

        # Verify: 1 in RAM, 2 in DB
        assert buffer.get_ram_buffer_size(task_id) == 1

        # Act: Delete all
        deleted = buffer.delete_events_for_task(task_id)

        # Assert: Both RAM and DB events deleted
        assert deleted == 3  # 1 from RAM + 2 from DB
        assert buffer.get_ram_buffer_size(task_id) == 0

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            count_in_db = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert count_in_db == 0

    def test_cleanup_old_events_removes_from_db(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test cleanup removes old consumed events from database."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        task_id = "task-old-cleanup"

        # Buffer event (creates it with current timestamp)
        buffer.buffer_event(
            task_id, "old-event", {"data": "test"}, session_id="s1", user_id="u1"
        )

        # Mark as consumed (sets consumed_at)
        buffer.get_buffered_events(task_id, mark_consumed=True)

        # Update the consumed_at timestamp to 8 days ago (cleanup checks consumed_at, not created_at)
        old_time = now_epoch_ms() - (8 * 24 * 60 * 60 * 1000)

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            conn.execute(
                sa.update(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
                .values(consumed_at=old_time)
            )
            conn.commit()

            # Verify exists
            count_before = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert count_before == 1

        # Act: Cleanup events older than 7 days
        deleted = buffer.cleanup_old_events(days=7)

        # Assert: Old event removed
        assert deleted == 1

        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            count_after = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == task_id)
            ).scalar()
            assert count_after == 0

    def test_has_unconsumed_events_checks_db(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test has_unconsumed_events queries database correctly."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        task_id = "task-has-unconsumed"

        # Initially no events
        assert buffer.has_unconsumed_events(task_id) is False

        # Buffer an unconsumed event
        buffer.buffer_event(task_id, "evt1", {}, session_id="s1", user_id="u1")

        # Assert: Has unconsumed events
        assert buffer.has_unconsumed_events(task_id) is True

        # Mark consumed
        buffer.get_buffered_events(task_id, mark_consumed=True)

        # Assert: No more unconsumed events
        assert buffer.has_unconsumed_events(task_id) is False

    def test_get_unconsumed_events_for_session_groups_by_task(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test get_unconsumed_events_for_session retrieves and groups events from DB."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        session_id = "session-multi-task"

        # Buffer events for multiple tasks in same session
        buffer.buffer_event(
            "task-1", "evt1", {"num": 1}, session_id=session_id, user_id="u1"
        )
        buffer.buffer_event(
            "task-1", "evt2", {"num": 2}, session_id=session_id, user_id="u1"
        )
        buffer.buffer_event(
            "task-2", "evt3", {"num": 3}, session_id=session_id, user_id="u1"
        )

        # Act: Get all unconsumed events for session
        events_by_task = buffer.get_unconsumed_events_for_session(session_id)

        # Assert: Events grouped by task
        assert "task-1" in events_by_task
        assert "task-2" in events_by_task
        assert len(events_by_task["task-1"]) == 2
        assert len(events_by_task["task-2"]) == 1

    def test_flush_all_buffers_writes_all_tasks(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test flush_all_buffers writes all RAM buffers to DB."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,  # No auto-flush
        )

        # Buffer events for multiple tasks
        buffer.buffer_event("task-A", "evt1", {}, session_id="s1", user_id="u1")
        buffer.buffer_event("task-A", "evt2", {}, session_id="s1", user_id="u1")
        buffer.buffer_event("task-B", "evt3", {}, session_id="s2", user_id="u2")

        # Verify in RAM
        assert buffer.get_ram_buffer_size("task-A") == 2
        assert buffer.get_ram_buffer_size("task-B") == 1

        # Act: Flush all
        total_flushed = buffer.flush_all_buffers()

        # Assert: 3 events flushed total
        assert total_flushed == 3

        # Assert: All RAM buffers cleared
        assert buffer.get_ram_buffer_size("task-A") == 0
        assert buffer.get_ram_buffer_size("task-B") == 0

        # Assert: All in DB
        with database_inspector.db_manager.get_gateway_connection() as conn:
            metadata = sa.MetaData()
            metadata.reflect(bind=conn)
            sse_buffer_table = metadata.tables["sse_event_buffer"]

            task_a_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == "task-A")
            ).scalar()
            task_b_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(sse_buffer_table)
                .where(sse_buffer_table.c.task_id == "task-B")
            ).scalar()

            assert task_a_count == 2
            assert task_b_count == 1

    def test_hybrid_mode_get_buffered_events_flushes_first(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that get_buffered_events flushes RAM before retrieving in hybrid mode."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory,
            enabled=True,
            hybrid_mode_enabled=True,
            hybrid_flush_threshold=100,
        )

        task_id = "task-flush-before-get"

        # Add events to RAM
        buffer.buffer_event(
            task_id, "ram1", {"in": "ram"}, session_id="s1", user_id="u1"
        )
        buffer.buffer_event(
            task_id, "ram2", {"in": "ram"}, session_id="s1", user_id="u1"
        )

        # Verify in RAM
        assert buffer.get_ram_buffer_size(task_id) == 2

        # Act: Get buffered events (should flush RAM first)
        events = buffer.get_buffered_events(task_id, mark_consumed=False)

        # Assert: RAM flushed and events retrieved
        assert len(events) == 2
        assert buffer.get_ram_buffer_size(task_id) == 0

    def test_delete_events_clears_metadata_cache(
        self,
        api_client: TestClient,
        gateway_adapter: GatewayAdapter,
        database_inspector: DatabaseInspector,
        db_session_factory,
    ):
        """Test that delete_events_for_task clears metadata cache."""
        buffer = PersistentSSEEventBuffer(
            session_factory=db_session_factory, enabled=True, hybrid_mode_enabled=False
        )

        task_id = "task-clear-meta"

        # Set metadata
        buffer.set_task_metadata(task_id, "session-123", "user-456")
        assert task_id in buffer._task_metadata_cache

        # Buffer and delete events
        buffer.buffer_event(task_id, "evt", {}, session_id="s1", user_id="u1")
        buffer.delete_events_for_task(task_id)

        # Assert: Metadata cache cleared
        assert task_id not in buffer._task_metadata_cache
