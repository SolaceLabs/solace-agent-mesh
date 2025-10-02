"""
Authorization and security tests for the task history API endpoints.

Tests that users can only access their own tasks, and that users with
special permissions can access tasks belonging to other users.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from solace_agent_mesh.gateway.http_sse.repository.models import TaskModel
from solace_agent_mesh.gateway.http_sse.shared import now_epoch_ms


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


@pytest.fixture
def multi_user_task_auth_setup(test_app, test_db_engine):
    """
    Creates multiple test clients with different user authentications and configs
    for testing task authorization.
    - user_a_client: A regular user.
    - user_b_client: Another regular user.
    - admin_client: A user with `tasks:read:all` scope.
    """
    from solace_agent_mesh.gateway.http_sse import dependencies

    # Store original dependencies to restore them later
    original_get_user_id = dependencies.get_user_id
    original_get_user_config = dependencies.get_user_config

    # This will be mutated by the clients to set the current user context
    current_test_user_context = {
        "user_id": "user_a",
        "config": {"scopes": {}},
    }

    def mock_get_user_id() -> str:
        return current_test_user_context["user_id"]

    async def mock_get_user_config() -> dict:
        return current_test_user_context["config"]

    # Apply the mocks
    test_app.dependency_overrides[dependencies.get_user_id] = mock_get_user_id
    test_app.dependency_overrides[dependencies.get_user_config] = mock_get_user_config

    class UserTestClient(TestClient):
        def __init__(self, app, user_id, config):
            super().__init__(app)
            self.user_id = user_id
            self.config = config

        def request(self, method, url, **kwargs):
            # Switch to this user's context for the request
            old_context = current_test_user_context.copy()
            current_test_user_context["user_id"] = self.user_id
            current_test_user_context["config"] = self.config
            try:
                return super().request(method, url, **kwargs)
            finally:
                # Restore previous user context
                current_test_user_context.update(old_context)

    user_a_client = UserTestClient(test_app, "user_a", {"scopes": {}})
    user_b_client = UserTestClient(test_app, "user_b", {"scopes": {}})
    admin_client = UserTestClient(
        test_app, "admin_user", {"scopes": {"tasks:read:all": True}}
    )

    yield user_a_client, user_b_client, admin_client

    # Cleanup: restore original dependencies
    test_app.dependency_overrides[dependencies.get_user_id] = original_get_user_id
    test_app.dependency_overrides[dependencies.get_user_config] = (
        original_get_user_config
    )


def test_task_list_is_isolated_by_user(multi_user_task_auth_setup, test_db_engine):
    """
    Tests that users can only see their own tasks in the list view.
    Corresponds to Test Plan 4.1.
    """
    user_a_client, user_b_client, _ = multi_user_task_auth_setup

    # Create tasks directly in the database with specific user IDs
    task_a_id = f"task-user-a-{uuid.uuid4().hex[:8]}"
    task_b_id = f"task-user-b-{uuid.uuid4().hex[:8]}"

    _create_task_directly_in_db(test_db_engine, task_a_id, "user_a", "Task for user A")
    _create_task_directly_in_db(test_db_engine, task_b_id, "user_b", "Task for user B")

    # User A lists tasks, should only see their own
    response_a = user_a_client.get("/api/v1/tasks")
    assert response_a.status_code == 200
    tasks_a = response_a.json()
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == task_a_id
    assert tasks_a[0]["user_id"] == "user_a"

    # User B lists tasks, should only see their own
    response_b = user_b_client.get("/api/v1/tasks")
    assert response_b.status_code == 200
    tasks_b = response_b.json()
    assert len(tasks_b) == 1
    assert tasks_b[0]["id"] == task_b_id
    assert tasks_b[0]["user_id"] == "user_b"


def test_task_detail_is_isolated_by_user(multi_user_task_auth_setup, test_db_engine):
    """
    Tests that a user cannot retrieve the details of another user's task.
    Corresponds to Test Plan 4.2.
    """
    user_a_client, user_b_client, _ = multi_user_task_auth_setup

    # Create a task directly in the database for user A
    task_a_id = f"task-private-a-{uuid.uuid4().hex[:8]}"
    _create_task_directly_in_db(
        test_db_engine, task_a_id, "user_a", "Private task for user A"
    )

    # User A can get their own task details
    response_a = user_a_client.get(f"/api/v1/tasks/{task_a_id}")
    assert response_a.status_code == 200
    assert f"task_id: {task_a_id}" in response_a.text

    # User B tries to get User A's task details, should be forbidden
    response_b = user_b_client.get(f"/api/v1/tasks/{task_a_id}")
    assert response_b.status_code == 403
    data = response_b.json()

    assert "You do not have permission to view this task" in data["error"]["message"]


def test_admin_can_query_all_tasks(multi_user_task_auth_setup, test_db_engine):
    """
    Tests that a user with 'tasks:read:all' scope can view all tasks.
    Corresponds to Test Plan 4.3.
    """
    user_a_client, user_b_client, admin_client = multi_user_task_auth_setup

    # Create tasks directly in the database for user A and B
    task_a_id = f"task-admin-a-{uuid.uuid4().hex[:8]}"
    task_b_id = f"task-admin-b-{uuid.uuid4().hex[:8]}"

    _create_task_directly_in_db(
        test_db_engine, task_a_id, "user_a", "User A task for admin view"
    )
    _create_task_directly_in_db(
        test_db_engine, task_b_id, "user_b", "User B task for admin view"
    )

    # Admin queries for all tasks (by not specifying a user_id)
    response_all = admin_client.get("/api/v1/tasks")
    assert response_all.status_code == 200
    all_tasks = response_all.json()
    assert len(all_tasks) == 2
    task_ids = {t["id"] for t in all_tasks}
    assert {task_a_id, task_b_id} == task_ids

    # Admin queries for user A's tasks specifically
    response_a_query = admin_client.get("/api/v1/tasks?query_user_id=user_a")
    assert response_a_query.status_code == 200
    tasks_a = response_a_query.json()
    assert len(tasks_a) == 1
    assert tasks_a[0]["id"] == task_a_id

    # Admin queries for user B's tasks specifically
    response_b_query = admin_client.get("/api/v1/tasks?query_user_id=user_b")
    assert response_b_query.status_code == 200
    tasks_b = response_b_query.json()
    assert len(tasks_b) == 1
    assert tasks_b[0]["id"] == task_b_id

    # Admin can get details for user A's task
    response_detail_a = admin_client.get(f"/api/v1/tasks/{task_a_id}")
    assert response_detail_a.status_code == 200
    assert f"task_id: {task_a_id}" in response_detail_a.text

    # Admin can get details for user B's task
    response_detail_b = admin_client.get(f"/api/v1/tasks/{task_b_id}")
    assert response_detail_b.status_code == 200
    assert f"task_id: {task_b_id}" in response_detail_b.text
