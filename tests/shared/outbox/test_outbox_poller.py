from unittest.mock import MagicMock, call

from solace_agent_mesh.shared.outbox import OutboxEventEntity, OutboxEventPoller


def _make_event(event_id="evt-1", entity_id="agt-001"):
    return OutboxEventEntity(
        id=event_id,
        entity_type="agent",
        entity_id=entity_id,
        event_type="auto_upgrade",
        status="pending",
        created_time=1000,
        updated_time=1000,
    )


def _make_poller(**overrides):
    defaults = dict(
        processor=MagicMock(),
        db_session_factory=MagicMock(),
        outbox_repository=MagicMock(),
        heartbeat_tracker=MagicMock(),
        batch_size=50,
        interval_seconds=10,
        cleanup_interval_seconds=3600,
        cleanup_retention_ms=86_400_000,
    )
    defaults.update(overrides)
    return OutboxEventPoller(**defaults), defaults


class TestPollCycle:

    def test_skips_poll_when_heartbeat_inactive(self):
        poller, deps = _make_poller()
        deps["heartbeat_tracker"].is_heartbeat_active.return_value = False

        poller._poll_cycle()

        deps["db_session_factory"].assert_not_called()
        deps["processor"].process_single_event.assert_not_called()

    def test_processes_pending_events(self):
        event = _make_event()
        mock_session = MagicMock()

        poller, deps = _make_poller()
        deps["heartbeat_tracker"].is_heartbeat_active.return_value = True
        deps["db_session_factory"].return_value = mock_session
        deps["outbox_repository"].get_pending_events.return_value = [event]
        deps["outbox_repository"].bulk_deduplicate_events.return_value = set()

        poller._poll_cycle()

        deps["processor"].process_single_event.assert_called_once_with(mock_session, event)
        assert mock_session.commit.call_count >= 1

    def test_skips_deduplicated_events(self):
        event = _make_event(event_id="evt-deduped")

        poller, deps = _make_poller()
        deps["heartbeat_tracker"].is_heartbeat_active.return_value = True
        deps["db_session_factory"].return_value = MagicMock()
        deps["outbox_repository"].get_pending_events.return_value = [event]
        deps["outbox_repository"].bulk_deduplicate_events.return_value = {"evt-deduped"}

        poller._poll_cycle()

        deps["processor"].process_single_event.assert_not_called()

    def test_isolates_failures_between_events(self):
        evt_fail = _make_event(event_id="evt-fail", entity_id="agt-fail")
        evt_ok = _make_event(event_id="evt-ok", entity_id="agt-ok")

        sessions = [MagicMock(), MagicMock(), MagicMock()]
        session_iter = iter(sessions)

        poller, deps = _make_poller()
        deps["heartbeat_tracker"].is_heartbeat_active.return_value = True
        deps["db_session_factory"].side_effect = lambda: next(session_iter)
        deps["outbox_repository"].get_pending_events.return_value = [evt_fail, evt_ok]
        deps["outbox_repository"].bulk_deduplicate_events.return_value = set()
        deps["processor"].process_single_event.side_effect = [RuntimeError("boom"), None]

        poller._poll_cycle()

        assert deps["processor"].process_single_event.call_count == 2
        sessions[1].rollback.assert_called_once()
        sessions[2].commit.assert_called_once()

    def test_commits_per_event_session(self):
        events = [_make_event(event_id=f"evt-{i}", entity_id=f"agt-{i}") for i in range(3)]
        sessions = [MagicMock() for _ in range(4)]
        session_iter = iter(sessions)

        poller, deps = _make_poller()
        deps["heartbeat_tracker"].is_heartbeat_active.return_value = True
        deps["db_session_factory"].side_effect = lambda: next(session_iter)
        deps["outbox_repository"].get_pending_events.return_value = events
        deps["outbox_repository"].bulk_deduplicate_events.return_value = set()

        poller._poll_cycle()

        for session in sessions[1:]:
            session.commit.assert_called_once()
            session.close.assert_called_once()


class TestCleanup:

    def test_cleanup_runs_on_interval(self):
        mock_session = MagicMock()
        poller, deps = _make_poller(cleanup_interval_seconds=0)
        deps["db_session_factory"].return_value = mock_session
        poller._last_cleanup = 0

        poller._maybe_cleanup()

        deps["outbox_repository"].cleanup_old_events.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_cleanup_skipped_when_interval_not_elapsed(self):
        import time

        poller, deps = _make_poller(cleanup_interval_seconds=3600)
        poller._last_cleanup = time.time()

        poller._maybe_cleanup()

        deps["outbox_repository"].cleanup_old_events.assert_not_called()
