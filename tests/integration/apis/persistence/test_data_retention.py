"""
Integration tests for data retention service.
"""

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


def test_data_retention_deletes_old_tasks(database_manager):
    """
    Tests that tasks older than the retention period are deleted.
    Corresponds to Test Plan 5.1.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create tasks at different times
    now_ms = now_epoch_ms()

    # Old task (100 days ago)
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)
    old_task_id = "old-task-retention-test"
    _create_task_directly_in_db(
        engine,
        old_task_id,
        "sam_dev_user",
        "Old task message",
        old_time_ms,
    )

    # New task (10 days ago)
    new_time_ms = now_ms - (10 * 24 * 60 * 60 * 1000)
    new_task_id = "new-task-retention-test"
    _create_task_directly_in_db(
        engine,
        new_task_id,
        "sam_dev_user",
        "New task message",
        new_time_ms,
    )

    # Verify both tasks exist
    assert _count_tasks_in_db(engine) == 2

    # Act: Get the data retention service and run cleanup with 90-day retention
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    # Temporarily override config for this test
    original_retention = retention_service.config.get("task_retention_days")
    retention_service.config["task_retention_days"] = 90

    try:
        retention_service.cleanup_old_data()

        # Assert: Old task deleted, new task remains
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            old_task = db.query(TaskModel).filter_by(id=old_task_id).first()
            new_task = db.query(TaskModel).filter_by(id=new_task_id).first()

            assert old_task is None, "Old task should be deleted"
            assert new_task is not None, "New task should remain"
            assert _count_tasks_in_db(engine) == 1
        finally:
            db.close()
    finally:
        # Restore original config
        if original_retention is not None:
            retention_service.config["task_retention_days"] = original_retention


@pytest.mark.xfail(
    reason="Task deletion does not cascade to task events due to bulk delete implementation "
    "using synchronize_session=False in TaskRepository.delete_tasks_older_than(). "
    "This bypasses SQLAlchemy ORM cascading. Needs fix in repository implementation."
)
def test_data_retention_cascades_to_task_events(api_client_factory):
    """
    Tests that deleting tasks also deletes their events (cascade).
    Corresponds to Test Plan 5.2.
    """
    # Arrange: Create an old task with events
    now_ms = now_epoch_ms()
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)
    old_task_id = "old-task-with-events"

    _create_task_directly_in_db(
        api_client_factory.engine,
        old_task_id,
        "sam_dev_user",
        "Old task with events",
        old_time_ms,
    )

    # Create task events for the old task
    Session = sessionmaker(bind=api_client_factory.engine)
    db = Session()
    try:
        for i in range(3):
            event = TaskEventModel(
                id=f"event-{old_task_id}-{i}",
                task_id=old_task_id,
                user_id="sam_dev_user",
                created_time=old_time_ms + (i * 1000),
                topic=f"test/topic/{i}",
                direction="request",
                payload={"test": f"event {i}"},
            )
            db.add(event)
        db.commit()

        # Verify events exist
        event_count = db.query(TaskEventModel).filter_by(task_id=old_task_id).count()
        assert event_count == 3
    finally:
        db.close()

    # Create a new task with events
    new_time_ms = now_ms - (10 * 24 * 60 * 60 * 1000)
    new_task_id = "new-task-with-events"

    _create_task_directly_in_db(
        api_client_factory.engine,
        new_task_id,
        "sam_dev_user",
        "New task with events",
        new_time_ms,
    )

    db = Session()
    try:
        for i in range(2):
            event = TaskEventModel(
                id=f"event-{new_task_id}-{i}",
                task_id=new_task_id,
                user_id="sam_dev_user",
                created_time=new_time_ms + (i * 1000),
                topic=f"test/topic/{i}",
                direction="request",
                payload={"test": f"event {i}"},
            )
            db.add(event)
        db.commit()

        # Verify total event count
        total_events = db.query(TaskEventModel).count()
        assert total_events == 5
    finally:
        db.close()

    # Act: Run cleanup with 90-day retention
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_retention = retention_service.config.get("task_retention_days")
    retention_service.config["task_retention_days"] = 90

    try:
        retention_service.cleanup_old_data()

        # Assert: Old task and its events deleted, new task and events remain
        db = Session()
        try:
            old_events = db.query(TaskEventModel).filter_by(task_id=old_task_id).count()
            new_events = db.query(TaskEventModel).filter_by(task_id=new_task_id).count()

            assert old_events == 0, "Old task events should be deleted (cascaded)"
            assert new_events == 2, "New task events should remain"

            total_events = db.query(TaskEventModel).count()
            assert total_events == 2
        finally:
            db.close()
    finally:
        if original_retention is not None:
            retention_service.config["task_retention_days"] = original_retention


def test_data_retention_deletes_multiple_old_tasks(database_manager):
    """
    Tests that multiple old tasks are deleted.
    Corresponds to Test Plan 5.3.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create 5 old tasks and 3 new tasks
    now_ms = now_epoch_ms()
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)
    new_time_ms = now_ms - (10 * 24 * 60 * 60 * 1000)

    old_task_ids = []
    for i in range(5):
        task_id = f"old-task-{i}"
        _create_task_directly_in_db(
            engine, task_id, "sam_dev_user", f"Old task {i}", old_time_ms
        )
        old_task_ids.append(task_id)

    new_task_ids = []
    for i in range(3):
        task_id = f"new-task-{i}"
        _create_task_directly_in_db(
            engine, task_id, "sam_dev_user", f"New task {i}", new_time_ms
        )
        new_task_ids.append(task_id)

    # Verify all tasks exist
    assert _count_tasks_in_db(engine) == 8

    # Act: Run cleanup with 90-day retention
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_retention = retention_service.config.get("task_retention_days")
    retention_service.config["task_retention_days"] = 90

    try:
        retention_service.cleanup_old_data()

        # Assert: Only new tasks remain
        assert _count_tasks_in_db(engine) == 3

        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            # Verify all old tasks are gone
            for task_id in old_task_ids:
                task = db.query(TaskModel).filter_by(id=task_id).first()
                assert task is None, f"Old task {task_id} should be deleted"

            # Verify all new tasks remain
            for task_id in new_task_ids:
                task = db.query(TaskModel).filter_by(id=task_id).first()
                assert task is not None, f"New task {task_id} should remain"
        finally:
            db.close()
    finally:
        if original_retention is not None:
            retention_service.config["task_retention_days"] = original_retention


def test_data_retention_respects_batch_size(database_manager):
    """
    Tests that cleanup respects the batch size configuration.
    Corresponds to Test Plan 5.4.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create 25 old tasks
    now_ms = now_epoch_ms()
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)

    for i in range(25):
        task_id = f"batch-task-{i}"
        _create_task_directly_in_db(
            engine,
            task_id,
            "sam_dev_user",
            f"Batch task {i}",
            old_time_ms,
        )

    # Verify all tasks exist
    assert _count_tasks_in_db(engine) == 25

    # Act: Run cleanup with small batch size
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_retention = retention_service.config.get("task_retention_days")
    original_batch_size = retention_service.config.get("batch_size")

    retention_service.config["task_retention_days"] = 90
    retention_service.config["batch_size"] = 10

    try:
        retention_service.cleanup_old_data()

        # Assert: All tasks deleted despite batch size
        assert _count_tasks_in_db(engine) == 0
    finally:
        if original_retention is not None:
            retention_service.config["task_retention_days"] = original_retention
        if original_batch_size is not None:
            retention_service.config["batch_size"] = original_batch_size


def test_data_retention_deletes_old_feedback(database_manager):
    """
    Tests that feedback older than the retention period is deleted.
    Corresponds to Test Plan 6.1.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create a task for feedback reference
    now_ms = now_epoch_ms()
    task_id = "task-for-feedback"
    _create_task_directly_in_db(
        engine, task_id, "sam_dev_user", "Task for feedback test", now_ms
    )

    # Create old feedback (100 days ago)
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)
    old_feedback_id = "old-feedback"
    _create_feedback_directly_in_db(
        engine, old_feedback_id, task_id, "sam_dev_user", old_time_ms
    )

    # Create new feedback (10 days ago)
    new_time_ms = now_ms - (10 * 24 * 60 * 60 * 1000)
    new_feedback_id = "new-feedback"
    _create_feedback_directly_in_db(
        engine, new_feedback_id, task_id, "sam_dev_user", new_time_ms
    )

    # Verify both feedback records exist
    assert _count_feedback_in_db(engine) == 2

    # Act: Run cleanup with 90-day feedback retention
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_retention = retention_service.config.get("feedback_retention_days")
    retention_service.config["feedback_retention_days"] = 90

    try:
        retention_service.cleanup_old_data()

        # Assert: Old feedback deleted, new feedback remains
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            old_feedback = db.query(FeedbackModel).filter_by(id=old_feedback_id).first()
            new_feedback = db.query(FeedbackModel).filter_by(id=new_feedback_id).first()

            assert old_feedback is None, "Old feedback should be deleted"
            assert new_feedback is not None, "New feedback should remain"
            assert _count_feedback_in_db(engine) == 1
        finally:
            db.close()
    finally:
        if original_retention is not None:
            retention_service.config["feedback_retention_days"] = original_retention


def test_data_retention_deletes_multiple_old_feedback(database_manager):
    """
    Tests that multiple old feedback records are deleted.
    Corresponds to Test Plan 6.2.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create a task for feedback reference
    now_ms = now_epoch_ms()
    task_id = "task-for-multiple-feedback"
    _create_task_directly_in_db(
        engine,
        task_id,
        "sam_dev_user",
        "Task for multiple feedback test",
        now_ms,
    )

    # Create 10 old feedback records (all 100+ days old)
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)
    old_feedback_ids = []
    for i in range(10):
        feedback_id = f"old-feedback-{i}"
        _create_feedback_directly_in_db(
            engine, feedback_id, task_id, "sam_dev_user", old_time_ms
        )
        old_feedback_ids.append(feedback_id)

    # Create 5 new feedback records (all < 30 days old)
    new_time_ms = now_ms - (10 * 24 * 60 * 60 * 1000)
    new_feedback_ids = []
    for i in range(5):
        feedback_id = f"new-feedback-{i}"
        _create_feedback_directly_in_db(
            engine, feedback_id, task_id, "sam_dev_user", new_time_ms
        )
        new_feedback_ids.append(feedback_id)

    # Verify all feedback exists
    assert _count_feedback_in_db(engine) == 15

    # Act: Run cleanup with 90-day retention
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_retention = retention_service.config.get("feedback_retention_days")
    retention_service.config["feedback_retention_days"] = 90

    try:
        retention_service.cleanup_old_data()

        # Assert: Only new feedback remains
        assert _count_feedback_in_db(engine) == 5

        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            # Verify all old feedback is gone
            for feedback_id in old_feedback_ids:
                feedback = db.query(FeedbackModel).filter_by(id=feedback_id).first()
                assert feedback is None, f"Old feedback {feedback_id} should be deleted"

            # Verify all new feedback remains
            for feedback_id in new_feedback_ids:
                feedback = db.query(FeedbackModel).filter_by(id=feedback_id).first()
                assert feedback is not None, f"New feedback {feedback_id} should remain"
        finally:
            db.close()
    finally:
        if original_retention is not None:
            retention_service.config["feedback_retention_days"] = original_retention


def test_task_and_feedback_retention_periods_independent(database_manager):
    """
    Tests that task and feedback retention periods work independently.
    Corresponds to Test Plan 6.3.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create tasks and feedback at different ages
    now_ms = now_epoch_ms()

    # Old task (100 days ago)
    old_task_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)
    old_task_id = "old-task-independent"
    _create_task_directly_in_db(
        engine, old_task_id, "sam_dev_user", "Old task", old_task_time_ms
    )

    # Old feedback (100 days ago)
    old_feedback_id = "old-feedback-independent"
    _create_feedback_directly_in_db(
        engine,
        old_feedback_id,
        old_task_id,
        "sam_dev_user",
        old_task_time_ms,
    )

    # Medium-age task (50 days ago)
    medium_task_time_ms = now_ms - (50 * 24 * 60 * 60 * 1000)
    medium_task_id = "medium-task-independent"
    _create_task_directly_in_db(
        engine,
        medium_task_id,
        "sam_dev_user",
        "Medium task",
        medium_task_time_ms,
    )

    # Medium-age feedback (50 days ago)
    medium_feedback_id = "medium-feedback-independent"
    _create_feedback_directly_in_db(
        engine,
        medium_feedback_id,
        medium_task_id,
        "sam_dev_user",
        medium_task_time_ms,
    )

    # Verify initial state
    assert _count_tasks_in_db(engine) == 2
    assert _count_feedback_in_db(engine) == 2

    # Act: Run cleanup with different retention periods
    # Tasks: 90 days, Feedback: 30 days
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_task_retention = retention_service.config.get("task_retention_days")
    original_feedback_retention = retention_service.config.get(
        "feedback_retention_days"
    )

    retention_service.config["task_retention_days"] = 90
    retention_service.config["feedback_retention_days"] = 30

    try:
        retention_service.cleanup_old_data()

        # Assert: Check what was deleted
        Session = sessionmaker(bind=engine)
        db = Session()
        try:
            # Old task should be deleted (> 90 days)
            old_task = db.query(TaskModel).filter_by(id=old_task_id).first()
            assert old_task is None, "Old task should be deleted (> 90 days)"

            # Medium task should remain (< 90 days)
            medium_task = db.query(TaskModel).filter_by(id=medium_task_id).first()
            assert medium_task is not None, "Medium task should remain (< 90 days)"

            # Old feedback should be deleted (> 30 days)
            old_feedback = db.query(FeedbackModel).filter_by(id=old_feedback_id).first()
            assert old_feedback is None, "Old feedback should be deleted (> 30 days)"

            # Medium feedback should be deleted (> 30 days)
            medium_feedback = (
                db.query(FeedbackModel).filter_by(id=medium_feedback_id).first()
            )
            assert medium_feedback is None, (
                "Medium feedback should be deleted (> 30 days)"
            )

            # Final counts
            assert _count_tasks_in_db(engine) == 1
            assert _count_feedback_in_db(engine) == 0
        finally:
            db.close()
    finally:
        if original_task_retention is not None:
            retention_service.config["task_retention_days"] = original_task_retention
        if original_feedback_retention is not None:
            retention_service.config["feedback_retention_days"] = (
                original_feedback_retention
            )


# Phase 7: Edge Cases


def test_data_retention_respects_disabled_config(database_manager):
    """
    Tests that cleanup doesn't run when disabled.
    Corresponds to Test Plan 7.1.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create old data
    now_ms = now_epoch_ms()
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)

    old_task_id = "task-disabled-test"
    _create_task_directly_in_db(
        engine, old_task_id, "sam_dev_user", "Old task", old_time_ms
    )

    old_feedback_id = "feedback-disabled-test"
    _create_feedback_directly_in_db(
        engine, old_feedback_id, old_task_id, "sam_dev_user", old_time_ms
    )

    # Verify initial state
    assert _count_tasks_in_db(engine) == 1
    assert _count_feedback_in_db(engine) == 1

    # Act: Run cleanup with service disabled
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    original_enabled = retention_service.config.get("enabled")
    retention_service.config["enabled"] = False

    try:
        retention_service.cleanup_old_data()

        # Assert: Nothing should be deleted
        assert _count_tasks_in_db(engine) == 1
        assert _count_feedback_in_db(engine) == 1
    finally:
        if original_enabled is not None:
            retention_service.config["enabled"] = original_enabled


def test_data_retention_handles_empty_database(database_manager):
    """
    Tests that cleanup handles empty database gracefully.
    Corresponds to Test Plan 7.3.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Ensure database is empty
    assert _count_tasks_in_db(engine) == 0
    assert _count_feedback_in_db(engine) == 0

    # Act: Run cleanup on empty database
    from solace_agent_mesh.gateway.http_sse import dependencies

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    # Should not raise any errors
    retention_service.cleanup_old_data()

    # Assert: Database still empty, no errors
    assert _count_tasks_in_db(engine) == 0
    assert _count_feedback_in_db(engine) == 0


def test_data_retention_handles_database_errors(database_manager, monkeypatch):
    """
    Tests that cleanup handles database errors gracefully.
    Corresponds to Test Plan 7.4.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Arrange: Create a task
    now_ms = now_epoch_ms()
    old_time_ms = now_ms - (100 * 24 * 60 * 60 * 1000)

    task_id = "task-error-test"
    _create_task_directly_in_db(
        engine, task_id, "sam_dev_user", "Error test task", old_time_ms
    )

    assert _count_tasks_in_db(engine) == 1

    # Act: Mock the repository to raise an exception
    from solace_agent_mesh.gateway.http_sse import dependencies
    from solace_agent_mesh.gateway.http_sse.repository.task_repository import (
        TaskRepository,
    )

    original_delete = TaskRepository.delete_tasks_older_than

    def mock_delete_with_error(self, cutoff_time_ms, batch_size):
        raise Exception("Simulated database error")

    monkeypatch.setattr(
        TaskRepository, "delete_tasks_older_than", mock_delete_with_error
    )

    retention_service = dependencies.get_data_retention_service(
        dependencies.sac_component_instance
    )

    # Should not crash, should log error and continue
    retention_service.cleanup_old_data()

    # Assert: Task still exists (cleanup failed but didn't crash)
    assert _count_tasks_in_db(engine) == 1

    # Restore original method
    monkeypatch.setattr(TaskRepository, "delete_tasks_older_than", original_delete)
