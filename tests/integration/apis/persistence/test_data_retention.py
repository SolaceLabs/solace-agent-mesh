"""
Integration tests for data retention service.
"""

import time
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models import (
    FeedbackModel,
    TaskEventModel,
    TaskModel,
)
from solace_agent_mesh.gateway.http_sse.shared import now_epoch_ms


def _create_task_directly_in_db(
    db_engine, task_id: str, user_id: str, message: str, start_time_ms: int
):
    """
    Creates a task record directly in the database with a specific timestamp.

    Args:
        db_engine: SQLAlchemy engine for the test database
        task_id: The task ID to create
        user_id: The user ID who owns this task
        message: The initial request text for the task
        start_time_ms: The start time in epoch milliseconds
    """
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id=user_id,
            start_time=start_time_ms,
            initial_request_text=message,
            status="completed",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()


def _create_feedback_directly_in_db(
    db_engine,
    feedback_id: str,
    task_id: str,
    user_id: str,
    created_time_ms: int,
):
    """
    Creates a feedback record directly in the database with a specific timestamp.

    Args:
        db_engine: SQLAlchemy engine for the test database
        feedback_id: The feedback ID to create
        task_id: The task ID this feedback is for
        user_id: The user ID who submitted the feedback
        created_time_ms: The creation time in epoch milliseconds
    """
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        new_feedback = FeedbackModel(
            id=feedback_id,
            task_id=task_id,
            session_id=f"session-{task_id}",
            user_id=user_id,
            rating="up",
            comment="Test feedback",
            created_time=created_time_ms,
        )
        db_session.add(new_feedback)
        db_session.commit()
    finally:
        db_session.close()


def _count_tasks_in_db(db_engine) -> int:
    """
    Counts the number of task records in the database.

    Args:
        db_engine: SQLAlchemy engine for the test database

    Returns:
        The number of task records
    """
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        count = db_session.query(TaskModel).count()
        return count
    finally:
        db_session.close()


def _count_feedback_in_db(db_engine) -> int:
    """
    Counts the number of feedback records in the database.

    Args:
        db_engine: SQLAlchemy engine for the test database

    Returns:
        The number of feedback records
    """
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        count = db_session.query(FeedbackModel).count()
        return count
    finally:
        db_session.close()
