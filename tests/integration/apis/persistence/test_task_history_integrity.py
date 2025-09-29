"""
Database integrity tests for the task history feature.
"""

import time

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models import (
    TaskEventModel,
    TaskModel,
)
from tests.integration.apis.persistence.test_task_history_api import (
    _create_task_and_get_ids,
)


def test_task_deletion_cascades_to_events(api_client: TestClient, test_db_engine):
    """
    Tests that deleting a Task record correctly cascades the deletion to all
    associated TaskEvent records, verifying the `ondelete='CASCADE'` constraint.
    Corresponds to Test Plan 2.3.
    """
    # Arrange: Create a task via the API. The TaskLoggerService, running in the
    # background of the test harness, will automatically log events for it.
    task_id, _ = _create_task_and_get_ids(
        api_client, "Test message for cascade delete"
    )

    # The task logger runs asynchronously. We need to wait for events to be persisted.
    # Polling is more robust than a fixed sleep.
    Session = sessionmaker(bind=test_db_engine)
    db_session = Session()
    events = []
    try:
        for _ in range(10):  # Poll for up to 5 seconds
            events = (
                db_session.query(TaskEventModel)
                .filter(TaskEventModel.task_id == task_id)
                .all()
            )
            if len(events) > 1:  # Wait for at least request and response
                break
            time.sleep(0.5)

        assert (
            len(events) > 0
        ), f"Task events were not logged for task {task_id} within the timeout period."
        print(f"Found {len(events)} events for task {task_id} before deletion.")

        task = db_session.query(TaskModel).filter(TaskModel.id == task_id).one()

        # Act: Delete the parent task directly from the database
        db_session.delete(task)
        db_session.commit()
        print(f"Deleted task {task_id} from the database.")

        # Assert: Verify the task and its events are gone
        task_after_delete = (
            db_session.query(TaskModel).filter(TaskModel.id == task_id).one_or_none()
        )
        assert (
            task_after_delete is None
        ), "The task should have been deleted from the tasks table."

        events_after_delete = (
            db_session.query(TaskEventModel)
            .filter(TaskEventModel.task_id == task_id)
            .all()
        )
        assert (
            len(events_after_delete) == 0
        ), "Task events should have been deleted by the CASCADE constraint."

        print(
            f"✓ Task deletion for {task_id} correctly cascaded to delete {len(events)} events."
        )

    finally:
        db_session.close()
