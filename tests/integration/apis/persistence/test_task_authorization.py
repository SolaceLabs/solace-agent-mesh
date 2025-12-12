"""
Authorization and security tests for the task history API endpoints.

Tests that users can only access their own tasks, and that users with
special permissions can access tasks belonging to other users.
"""

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel
from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms


def _create_task_directly_in_db(db_engine, task_id: str, user_id: str, message: str):
    """
    Creates a task record directly in the database, bypassing the API.
    This avoids race conditions with the automatic TaskLoggerService.

    Args:
        db_engine: SQLAlchemy engine for the test database
        task_id: The task ID to create
        user_id: The user ID who owns this task
        message: The initial request text for the task
    """
    Session = sessionmaker(bind=db_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id=user_id,
            start_time=now_epoch_ms(),
            initial_request_text=message,
            status="completed",  # Set as completed for query tests
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()


def test_task_list_is_isolated_by_user(
    api_client, secondary_api_client, database_manager
):
    """
    Tests that users can only see their own tasks in the list view.
    Corresponds to Test Plan 4.1.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Create tasks directly in the database with specific user IDs
    task_a_id = f"task-user-a-{uuid.uuid4().hex[:8]}"
    task_b_id = f"task-user-b-{uuid.uuid4().hex[:8]}"

    _create_task_directly_in_db(engine, task_a_id, "sam_dev_user", "Task for user A")
    _create_task_directly_in_db(engine, task_b_id, "secondary_user", "Task for user B")

    # Primary user lists tasks, should only see their own
    response_a = api_client.get("/api/v1/tasks")
    assert response_a.status_code == 200
    tasks_a = response_a.json()
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == task_a_id
    assert tasks_a[0]["user_id"] == "sam_dev_user"

    # Secondary user lists tasks, should only see their own
    response_b = secondary_api_client.get("/api/v1/tasks")
    assert response_b.status_code == 200
    tasks_b = response_b.json()
    assert len(tasks_b) == 1
    assert tasks_b[0]["id"] == task_b_id
    assert tasks_b[0]["user_id"] == "secondary_user"


def test_task_detail_is_isolated_by_user(
    api_client, secondary_api_client, database_manager
):
    """
    Tests that a user cannot retrieve the details of another user's task.
    Corresponds to Test Plan 4.2.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Create a task directly in the database for primary user
    task_a_id = f"task-private-a-{uuid.uuid4().hex[:8]}"
    _create_task_directly_in_db(
        engine, task_a_id, "sam_dev_user", "Private task for user A"
    )

    # Primary user can get their own task details
    response_a = api_client.get(f"/api/v1/tasks/{task_a_id}")
    assert response_a.status_code == 200
    assert f"task_id: {task_a_id}" in response_a.text

    # Secondary user tries to get primary user's task details, should be forbidden
    response_b = secondary_api_client.get(f"/api/v1/tasks/{task_a_id}")
    assert response_b.status_code == 403
    data = response_b.json()

    assert "You do not have permission to view this task" in data["error"]["message"]


@pytest.mark.skip(
    reason="Admin functionality with 'tasks:read:all' scope not available in standard test fixtures. "
    "Requires custom user authentication setup with admin permissions."
)
def test_admin_can_query_all_tasks(api_client, secondary_api_client, database_manager):
    """
    Tests that a user with 'tasks:read:all' scope can view all tasks.
    Corresponds to Test Plan 4.3.
    """
    # Get the correct engine based on the database provider
    engine = database_manager.provider.get_sync_gateway_engine()

    # Note: This test would need admin_client with special scope permissions
    # user_a_client, user_b_client, admin_client = multi_user_task_auth_setup

    # Create tasks directly in the database for user A and B
    task_a_id = f"task-admin-a-{uuid.uuid4().hex[:8]}"
    task_b_id = f"task-admin-b-{uuid.uuid4().hex[:8]}"

    _create_task_directly_in_db(
        engine, task_a_id, "sam_dev_user", "User A task for admin view"
    )
    _create_task_directly_in_db(
        engine, task_b_id, "secondary_user", "User B task for admin view"
    )

    # Note: Admin client would be needed for these operations
    # admin_client = create_admin_client_with_tasks_read_all_scope()

    # Admin queries for all tasks (by not specifying a user_id)
    # response_all = admin_client.get("/api/v1/tasks")
    # assert response_all.status_code == 200
    # all_tasks = response_all.json()
    # assert len(all_tasks) == 2
    # task_ids = {t["id"] for t in all_tasks}
    # assert {task_a_id, task_b_id} == task_ids

    # Admin queries for user A's tasks specifically
    # response_a_query = admin_client.get("/api/v1/tasks?query_user_id=sam_dev_user")
    # assert response_a_query.status_code == 200
    # tasks_a = response_a_query.json()
    # assert len(tasks_a) == 1
    # assert tasks_a[0]["id"] == task_a_id

    # Admin queries for user B's tasks specifically
    # response_b_query = admin_client.get("/api/v1/tasks?query_user_id=secondary_user")
    # assert response_b_query.status_code == 200
    # tasks_b = response_b_query.json()
    # assert len(tasks_b) == 1
    # assert tasks_b[0]["id"] == task_b_id

    # Admin can get details for user A's task
    # response_detail_a = admin_client.get(f"/api/v1/tasks/{task_a_id}")
    # assert response_detail_a.status_code == 200
    # assert f"task_id: {task_a_id}" in response_detail_a.text

    # Admin can get details for user B's task
    # response_detail_b = admin_client.get(f"/api/v1/tasks/{task_b_id}")
    # assert response_detail_b.status_code == 200
    # assert f"task_id: {task_b_id}" in response_detail_b.text
