import time

import pytest
from solace_agent_mesh.shared.api.pagination import PaginationParams
from solace_agent_mesh.shared.outbox import (
    CreateOutboxEventModel,
    UpdateOutboxEventModel,
)


class TestCreateEvent:

    def test_create_event_persists_to_database(self, db_session, outbox_repo, create_event):
        event = create_event(entity_type="agent", entity_id="agt-001", payload='{"trigger":"test"}')
        db_session.commit()

        fetched = outbox_repo.get_event_by_id(db_session, event.id)
        assert fetched is not None
        assert fetched.entity_type == "agent"
        assert fetched.entity_id == "agt-001"
        assert fetched.event_type == "auto_upgrade"
        assert fetched.status == "pending"
        assert fetched.payload == '{"trigger":"test"}'
        assert fetched.retry_count == 0
        assert fetched.created_time > 0

    def test_create_batch_persists_all_events(self, db_session, outbox_repo):
        batch = [
            CreateOutboxEventModel(entity_type="agent", entity_id=f"agt-{i}", event_type="auto_upgrade")
            for i in range(3)
        ]
        results = outbox_repo.create_events_batch(db_session, batch)
        db_session.commit()

        assert len(results) == 3
        for i, entity in enumerate(results):
            fetched = outbox_repo.get_event_by_id(db_session, entity.id)
            assert fetched is not None
            assert fetched.entity_id == f"agt-{i}"


class TestGetPendingEvents:

    def test_filters_by_status_and_retry_time(self, db_session, outbox_repo, create_event):
        now_ms = int(time.time() * 1000)
        ready = create_event(entity_id="agt-ready", next_retry_at=now_ms - 1000)
        create_event(entity_id="agt-future", next_retry_at=now_ms + 60_000)
        completed = create_event(entity_id="agt-done", status="pending")
        outbox_repo.update_event(db_session, completed.id, UpdateOutboxEventModel(status="completed"))
        db_session.commit()

        events = outbox_repo.get_pending_events(db_session, now_ms)
        event_ids = {e.id for e in events}
        assert ready.id in event_ids
        assert completed.id not in event_ids

    def test_respects_limit(self, db_session, outbox_repo, create_event):
        now_ms = int(time.time() * 1000) + 1000
        for i in range(5):
            create_event(entity_id=f"agt-{i}")
        db_session.commit()

        events = outbox_repo.get_pending_events(db_session, now_ms, limit=2)
        assert len(events) == 2

    def test_orders_by_created_time_ascending(self, db_session, outbox_repo, create_event):
        now_ms = int(time.time() * 1000) + 1000
        first = create_event(entity_id="agt-first")
        second = create_event(entity_id="agt-second")
        db_session.commit()

        events = outbox_repo.get_pending_events(db_session, now_ms)
        assert events[0].id == first.id
        assert events[1].id == second.id


class TestHasPendingEvent:

    def test_returns_true_for_existing_pending(self, db_session, outbox_repo, create_event):
        create_event(entity_type="agent", entity_id="agt-001", event_type="auto_upgrade")
        db_session.commit()

        assert outbox_repo.has_pending_event(db_session, "agent", "agt-001", "auto_upgrade") is True

    def test_returns_false_after_completion(self, db_session, outbox_repo, create_event):
        event = create_event(entity_type="agent", entity_id="agt-001", event_type="auto_upgrade")
        outbox_repo.update_event(db_session, event.id, UpdateOutboxEventModel(status="completed"))
        db_session.commit()

        assert outbox_repo.has_pending_event(db_session, "agent", "agt-001", "auto_upgrade") is False


class TestUpdateEvent:

    def test_applies_partial_fields_without_overwriting_others(self, db_session, outbox_repo, create_event):
        event = create_event(payload='{"original": true}')
        outbox_repo.update_event(db_session, event.id, UpdateOutboxEventModel(status="error", error_message="boom"))
        db_session.commit()

        fetched = outbox_repo.get_event_by_id(db_session, event.id)
        assert fetched.status == "error"
        assert fetched.error_message == "boom"
        assert fetched.payload == '{"original": true}'
        assert fetched.retry_count == 0

    def test_update_nonexistent_event_raises(self, db_session, outbox_repo):
        with pytest.raises(ValueError, match="not found"):
            outbox_repo.update_event(db_session, "nonexistent-id", UpdateOutboxEventModel(status="error"))


class TestBulkDeduplication:

    def test_keeps_newest_marks_older_skipped(self, db_session, outbox_repo, create_event):
        older = create_event(entity_id="agt-001")
        newer = create_event(entity_id="agt-001")
        # Ensure distinct created_time so ORDER BY created_time DESC is deterministic
        from solace_agent_mesh.shared.outbox import OutboxEventModel
        db_session.query(OutboxEventModel).filter(OutboxEventModel.id == older.id).update({"created_time": 1000})
        db_session.query(OutboxEventModel).filter(OutboxEventModel.id == newer.id).update({"created_time": 2000})
        db_session.commit()

        deduped = outbox_repo.bulk_deduplicate_events(db_session, [older.id, newer.id])
        db_session.commit()

        assert older.id in deduped
        assert newer.id not in deduped

        older_fetched = outbox_repo.get_event_by_id(db_session, older.id)
        newer_fetched = outbox_repo.get_event_by_id(db_session, newer.id)
        assert older_fetched.status == "skipped"
        assert newer_fetched.status == "pending"

    def test_noop_for_single_event_per_entity(self, db_session, outbox_repo, create_event):
        event = create_event(entity_id="agt-001")
        db_session.commit()

        deduped = outbox_repo.bulk_deduplicate_events(db_session, [event.id])
        assert len(deduped) == 0

        fetched = outbox_repo.get_event_by_id(db_session, event.id)
        assert fetched.status == "pending"


class TestStaleDeduplication:

    def test_returns_false_when_not_latest(self, db_session, outbox_repo, create_event):
        older = create_event(entity_id="agt-001")
        newer = create_event(entity_id="agt-001")
        from solace_agent_mesh.shared.outbox import OutboxEventModel
        db_session.query(OutboxEventModel).filter(OutboxEventModel.id == older.id).update({"created_time": 1000})
        db_session.query(OutboxEventModel).filter(OutboxEventModel.id == newer.id).update({"created_time": 2000})
        db_session.commit()

        is_latest = outbox_repo.deduplicate_stale_events(db_session, older.id, "agent", "agt-001")
        assert is_latest is False


class TestPagination:

    def test_returns_correct_page_and_total(self, db_session, outbox_repo, create_event):
        for i in range(5):
            create_event(entity_id=f"agt-{i}")
        db_session.commit()

        events, total = outbox_repo.get_events_paginated(
            db_session, PaginationParams(page_number=1, page_size=2)
        )
        assert len(events) == 2
        assert total == 5

        events_p2, total_p2 = outbox_repo.get_events_paginated(
            db_session, PaginationParams(page_number=2, page_size=2)
        )
        assert len(events_p2) == 2
        assert total_p2 == 5

        all_ids = {e.id for e in events} | {e.id for e in events_p2}
        assert len(all_ids) == 4


class TestCleanup:

    def test_deletes_old_completed_preserves_pending(self, db_session, outbox_repo, create_event):
        pending = create_event(entity_id="agt-pending")
        old_completed = create_event(entity_id="agt-old")
        outbox_repo.update_event(db_session, old_completed.id, UpdateOutboxEventModel(status="completed"))
        db_session.commit()

        far_future = int(time.time() * 1000) + 86_400_000
        deleted = outbox_repo.cleanup_old_events(db_session, far_future)
        db_session.commit()

        assert deleted == 1
        assert outbox_repo.get_event_by_id(db_session, pending.id) is not None
        assert outbox_repo.get_event_by_id(db_session, old_completed.id) is None
