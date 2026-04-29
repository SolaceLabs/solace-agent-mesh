"""Helpers to map scheduled-task chat session IDs to their artifact storage location.

Per-execution sessions  ("scheduled_{execution_id}")   are what users see as
chat sessions and what gets shared. Stable storage sessions
("scheduled_task_{task_id}") are the ADK ``context_id`` agents actually use
when writing artifacts. This module translates between them so any code that
needs to load artifacts for a scheduled-task session can find them.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def is_execution_session(session_id: str | None) -> bool:
    """Return True if session_id is a per-execution scheduled session (not task-level)."""
    return bool(
        session_id
        and session_id.startswith("scheduled_")
        and not session_id.startswith("scheduled_task_")
    )


def get_execution_from_db(session_id: str, caller: str) -> Any | None:
    """Look up the scheduled execution record for an execution session.

    Returns the execution ORM object, or ``None`` if the session is not an
    execution session or the lookup fails.
    """
    if not is_execution_session(session_id):
        return None

    try:
        from ...repository.scheduled_task_repository import ScheduledTaskRepository
        from ...dependencies import SessionLocal

        if SessionLocal is None:
            return None

        repo = ScheduledTaskRepository()
        with SessionLocal() as db:
            return repo.find_execution_by_session_id(db, session_id)
    except Exception as e:
        log.warning("[%s] Failed to look up execution for %s: %s", caller, session_id, e)
        return None


def resolve_execution_context(
    session_id: str,
) -> tuple[str | None, dict[str, int | None] | None]:
    """Resolve a per-execution session_id to its stable storage session and pinned versions.

    For per-execution scheduled sessions, fetches the execution record once and
    derives the stable storage session_id and an artifact name -> pinned
    version mapping from the execution's manifest.

    Returns ``(stable_session_id, artifact_info)`` — either or both may be
    ``None`` if the session is not an execution session or the lookup fails.
    """
    execution = get_execution_from_db(session_id, "resolve_execution_context")
    if not execution:
        return None, None

    stable_id = f"scheduled_task_{execution.scheduled_task_id}"
    log.debug("[resolve_execution_context] Mapped %s -> %s", session_id, stable_id)

    artifact_info: dict[str, int | None] | None = None
    if execution.artifacts:
        info: dict[str, int | None] = {}
        for art in execution.artifacts:
            if isinstance(art, dict):
                name = art.get("name") or art.get("filename")
                if name:
                    info[name] = art.get("version")
        artifact_info = info if info else None

    return stable_id, artifact_info
