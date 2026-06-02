"""Database tests for SessionRepository.update_agent (agent_id backfill).

Exercises the real backfill data path used when the first message arrives for a
session that was created without an agent (the file-upload-before-first-message
and fork paths persist ``agent_id=None``).
"""

import uuid

from solace_agent_mesh.gateway.http_sse.repository.models import SessionModel
from solace_agent_mesh.gateway.http_sse.repository.session_repository import (
    SessionRepository,
)


def _insert_session(db_session, *, agent_id, user_id, deleted_at=None, updated_time=1000):
    """Insert a session row directly and return its id."""
    session_id = str(uuid.uuid4())
    db_session.add(
        SessionModel(
            id=session_id,
            name=None,
            user_id=user_id,
            agent_id=agent_id,
            created_time=1000,
            updated_time=updated_time,
            deleted_at=deleted_at,
        )
    )
    db_session.commit()
    return session_id


def test_update_agent_backfills_when_null(db_session_factory):
    """A NULL agent_id is set, the call reports success, and updated_time is left alone."""
    db_session = db_session_factory()
    try:
        user_id = f"user-{uuid.uuid4()}"
        session_id = _insert_session(
            db_session, agent_id=None, user_id=user_id, updated_time=1000
        )

        repo = SessionRepository()
        updated = repo.update_agent(db_session, session_id, user_id, "TestAgent")
        db_session.commit()

        assert updated is True

        row = db_session.query(SessionModel).filter_by(id=session_id).first()
        assert row.agent_id == "TestAgent"
        # Pure metadata backfill: updated_time must NOT be bumped.
        assert row.updated_time == 1000
    finally:
        db_session.close()


def test_update_agent_does_not_overwrite_existing_agent(db_session_factory):
    """A session that already has an agent is left untouched and reports no update."""
    db_session = db_session_factory()
    try:
        user_id = f"user-{uuid.uuid4()}"
        session_id = _insert_session(
            db_session, agent_id="OriginalAgent", user_id=user_id
        )

        repo = SessionRepository()
        updated = repo.update_agent(db_session, session_id, user_id, "OtherAgent")
        db_session.commit()

        assert updated is False
        row = db_session.query(SessionModel).filter_by(id=session_id).first()
        assert row.agent_id == "OriginalAgent"
    finally:
        db_session.close()


def test_update_agent_returns_false_for_unknown_session(db_session_factory):
    """No matching session -> no update."""
    db_session = db_session_factory()
    try:
        repo = SessionRepository()
        updated = repo.update_agent(
            db_session, str(uuid.uuid4()), f"user-{uuid.uuid4()}", "TestAgent"
        )
        assert updated is False
    finally:
        db_session.close()


def test_update_agent_ignores_wrong_user(db_session_factory):
    """A session owned by another user is not backfilled."""
    db_session = db_session_factory()
    try:
        owner_id = f"user-{uuid.uuid4()}"
        session_id = _insert_session(db_session, agent_id=None, user_id=owner_id)

        repo = SessionRepository()
        updated = repo.update_agent(
            db_session, session_id, f"other-{uuid.uuid4()}", "TestAgent"
        )
        db_session.commit()

        assert updated is False
        row = db_session.query(SessionModel).filter_by(id=session_id).first()
        assert row.agent_id is None
    finally:
        db_session.close()


def test_update_agent_ignores_soft_deleted_session(db_session_factory):
    """A soft-deleted session is not backfilled."""
    db_session = db_session_factory()
    try:
        user_id = f"user-{uuid.uuid4()}"
        session_id = _insert_session(
            db_session, agent_id=None, user_id=user_id, deleted_at=2000
        )

        repo = SessionRepository()
        updated = repo.update_agent(db_session, session_id, user_id, "TestAgent")
        db_session.commit()

        assert updated is False
        row = db_session.query(SessionModel).filter_by(id=session_id).first()
        assert row.agent_id is None
    finally:
        db_session.close()
