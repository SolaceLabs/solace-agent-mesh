"""
API integration tests for the feedback router.

These tests verify that the /feedback endpoint correctly processes
feedback payloads and interacts with the configured FeedbackService,
including writing to CSV files and logging.
"""

import uuid
from unittest.mock import MagicMock

import sqlalchemy as sa
from fastapi.testclient import TestClient

from solace_agent_mesh.shared.utils.timestamp_utils import now_epoch_ms

from .infrastructure.database_inspector import DatabaseInspector
from .infrastructure.gateway_adapter import GatewayAdapter


def test_submit_feedback_persists_to_database(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that a valid feedback submission creates a record in the database.
    """
    # Arrange: Create a session and a task using the gateway adapter
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for feedback")

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
        "feedbackText": "This was very helpful!",
    }

    # Act: Submit the feedback via the API
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert: Check HTTP response
    assert response.status_code == 202
    assert response.json() == {"status": "feedback received"}

    # Verify database record using the database inspector
    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        feedback_table = metadata.tables["feedback"]
        query = sa.select(feedback_table).where(
            feedback_table.c.task_id == task.task_id
        )
        feedback_record = conn.execute(query).first()

        assert feedback_record is not None
        assert feedback_record.session_id == session.id
        assert feedback_record.rating == "up"
        assert feedback_record.comment == "This was very helpful!"
        # The user_id is injected by the mock authentication in the test client
        assert feedback_record.user_id == "sam_dev_user"


def test_submit_multiple_feedback_records(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that multiple feedback submissions for the same task create distinct records.
    """
    # Arrange: Create a session and a task
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for multiple feedback")

    payload1 = {"taskId": task.task_id, "sessionId": session.id, "feedbackType": "up"}
    payload2 = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "down",
        "feedbackText": "Confusing",
    }

    # Act: Submit two feedback payloads
    api_client.post("/api/v1/feedback", json=payload1)
    api_client.post("/api/v1/feedback", json=payload2)

    # Assert: Check database for two records
    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        feedback_table = metadata.tables["feedback"]
        query = sa.select(feedback_table).where(
            feedback_table.c.task_id == task.task_id
        )
        feedback_records = conn.execute(query).fetchall()

        assert len(feedback_records) == 2
        ratings = {record.rating for record in feedback_records}
        assert ratings == {"up", "down"}


def test_feedback_missing_required_fields_fails(api_client: TestClient):
    """
    Tests that a payload missing required fields (like taskId) returns a 422 error.
    """
    # Arrange: Payload is missing the required 'taskId'
    invalid_payload = {
        "sessionId": "session-invalid",
        "feedbackType": "up",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=invalid_payload)

    # Assert
    assert response.status_code == 422


def test_feedback_publishes_event_when_enabled(
    api_client: TestClient,
    monkeypatch,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that feedback is published as an event when feedback_publishing is enabled.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "summary",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for event publishing")

    # Manually create the task record so the feedback service can find it
    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        tasks_table = metadata.tables["tasks"]
        conn.execute(
            tasks_table.insert().values(
                id=task.task_id,
                user_id="sam_dev_user",
                initial_request_text="Task for event publishing",
                start_time=now_epoch_ms(),
                end_time=now_epoch_ms(),
            )
        )
        if conn.in_transaction():
            conn.commit()

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_topic = mock_publish_func.call_args[0][0]
    published_payload = mock_publish_func.call_args[0][1]

    assert published_topic == "sam/feedback/test/v1"
    assert published_payload["feedback"]["task_id"] == task.task_id
    assert published_payload["feedback"]["feedback_type"] == "up"
    assert "task_summary" in published_payload
    assert published_payload["task_summary"]["id"] == task.task_id


def test_feedback_publishing_with_include_task_info_none(
    api_client: TestClient, monkeypatch, gateway_adapter: GatewayAdapter
):
    """
    Tests that when include_task_info is 'none', no task info is included in the published event.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "none",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for none test")

    # No need to create a task record here, as we are testing the 'none' case

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "down",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_payload = mock_publish_func.call_args[0][1]

    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == task.task_id
    assert "task_summary" not in published_payload
    assert "task_stim_data" not in published_payload


def test_feedback_publishing_with_include_task_info_stim(
    api_client: TestClient,
    monkeypatch,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that when include_task_info is 'stim', full task history is included in the published event.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "stim",
            "max_payload_size_bytes": 9000000,
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for stim test")

    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        tasks_table = metadata.tables["tasks"]
        task_events_table = metadata.tables["task_events"]

        # Create the main task record
        conn.execute(
            tasks_table.insert().values(
                id=task.task_id,
                user_id="sam_dev_user",
                initial_request_text="Task for stim test",
                status="completed",
                start_time=now_epoch_ms(),
                end_time=now_epoch_ms(),
            )
        )

        # Create associated task events
        conn.execute(
            task_events_table.insert().values(
                id=str(uuid.uuid4()),
                task_id=task.task_id,
                user_id="sam_dev_user",
                created_time=now_epoch_ms(),
                topic="test/topic/request",
                direction="request",
                payload={"test": "request_payload"},
            )
        )
        conn.execute(
            task_events_table.insert().values(
                id=str(uuid.uuid4()),
                task_id=task.task_id,
                user_id="sam_dev_user",
                created_time=now_epoch_ms() + 100,
                topic="test/topic/response",
                direction="response",
                payload={"test": "response_payload"},
            )
        )

        if conn.in_transaction():
            conn.commit()

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_payload = mock_publish_func.call_args[0][1]

    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == task.task_id
    assert "task_stim_data" in published_payload
    stim_data = published_payload["task_stim_data"]
    assert "invocation_details" in stim_data
    assert "invocation_flow" in stim_data
    assert stim_data["invocation_details"]["task_id"] == task.task_id
    # The gateway_adapter creates 2 messages (user + agent), so we expect 2 events
    assert len(stim_data["invocation_flow"]) >= 2


def test_feedback_publishing_stim_fallback_to_summary_on_size_limit(
    api_client: TestClient,
    monkeypatch,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that when include_task_info is 'stim' but payload exceeds max_payload_size_bytes,
    it falls back to 'summary' mode.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "stim",
            "max_payload_size_bytes": 100,  # Very small
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(
        session.id, "Task for fallback test" * 100
    )  # Large message

    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        tasks_table = metadata.tables["tasks"]
        conn.execute(
            tasks_table.insert().values(
                id=task.task_id,
                user_id="sam_dev_user",
                initial_request_text="Task for fallback test",
                start_time=now_epoch_ms(),
                end_time=now_epoch_ms(),
            )
        )
        if conn.in_transaction():
            conn.commit()

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_payload = mock_publish_func.call_args[0][1]

    assert "feedback" in published_payload
    assert "task_summary" in published_payload
    assert "task_stim_data" not in published_payload
    assert "truncation_details" in published_payload
    assert published_payload["truncation_details"]["reason"] == "payload_too_large"


def test_feedback_publishing_disabled_skips_event_but_saves_to_db(
    api_client: TestClient,
    monkeypatch,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that when feedback_publishing.enabled = False, no event is published
    but feedback is still saved to the database.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {"enabled": False}
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for disabled test")

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "down",
        "feedbackText": "This needs improvement",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_not_called()

    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        feedback_table = metadata.tables["feedback"]
        query = sa.select(feedback_table).where(
            feedback_table.c.task_id == task.task_id
        )
        feedback_record = conn.execute(query).first()
        assert feedback_record is not None
        assert feedback_record.rating == "down"


def test_feedback_publishing_uses_custom_topic(
    api_client: TestClient, monkeypatch, gateway_adapter: GatewayAdapter
):
    """
    Tests that the configured custom topic is used for publishing feedback events.
    """
    # Arrange
    mock_publish_func = MagicMock()
    custom_topic = "custom/feedback/topic/v2"
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": custom_topic,
            "include_task_info": "none",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for custom topic test")

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_topic = mock_publish_func.call_args[0][0]
    assert published_topic == custom_topic


def test_feedback_publishing_failure_does_not_break_saving(
    api_client: TestClient,
    monkeypatch,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that if publish_a2a raises an exception, the feedback is still saved to the database.
    """
    # Arrange
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component, "publish_a2a", MagicMock(side_effect=Exception("Simulated failure"))
    )
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {"enabled": True}
        if key == "feedback_publishing"
        else default,
    )

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for resilience test")

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "down",
        "feedbackText": "Testing resilience",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202  # Should succeed even if publishing fails

    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        feedback_table = metadata.tables["feedback"]
        query = sa.select(feedback_table).where(
            feedback_table.c.task_id == task.task_id
        )
        feedback_record = conn.execute(query).first()
        assert feedback_record is not None
        assert feedback_record.rating == "down"


def test_feedback_publishing_payload_structure_with_summary(
    api_client: TestClient,
    monkeypatch,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that the published payload has the correct structure with task_summary.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "summary",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for payload structure test")

    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        tasks_table = metadata.tables["tasks"]
        conn.execute(
            tasks_table.insert().values(
                id=task.task_id,
                user_id="sam_dev_user",
                initial_request_text="Task for payload structure test",
                start_time=now_epoch_ms(),
                end_time=now_epoch_ms(),
            )
        )
        if conn.in_transaction():
            conn.commit()

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
        "feedbackText": "Great response!",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_payload = mock_publish_func.call_args[0][1]

    assert "feedback" in published_payload
    feedback_obj = published_payload["feedback"]
    assert feedback_obj["task_id"] == task.task_id
    assert feedback_obj["feedback_type"] == "up"
    assert feedback_obj["feedback_text"] == "Great response!"

    assert "task_summary" in published_payload
    task_summary = published_payload["task_summary"]
    assert task_summary["id"] == task.task_id
    assert task_summary["initial_request_text"] == "Task for payload structure test"


def test_feedback_publishing_with_missing_task(
    api_client: TestClient, monkeypatch, gateway_adapter: GatewayAdapter
):
    """
    Tests behavior when include_task_info is set but the task doesn't exist in the database.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.get_sac_component()
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "summary",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    # We don't create a task, just a session
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    fake_task_id = f"task-{uuid.uuid4().hex[:8]}"

    feedback_payload = {
        "taskId": fake_task_id,
        "sessionId": session.id,
        "feedbackType": "down",
        "feedbackText": "Task not found test",
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    published_payload = mock_publish_func.call_args[0][1]

    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == fake_task_id
    assert "task_summary" not in published_payload
    assert "task_stim_data" not in published_payload


# ========================================
# GET /feedback endpoint tests
# ========================================


def test_get_feedback_returns_users_own_feedback(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that a user can retrieve their own feedback.
    """
    # Arrange: Create session, task, and submit feedback
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for retrieval test")

    feedback_payload = {
        "taskId": task.task_id,
        "sessionId": session.id,
        "feedbackType": "up",
        "feedbackText": "Great response!",
    }
    api_client.post("/api/v1/feedback", json=feedback_payload)

    # Act: Retrieve feedback
    response = api_client.get("/api/v1/feedback")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()
    assert len(feedback_list) >= 1

    # Find our feedback in the list
    our_feedback = next(
        (f for f in feedback_list if f["task_id"] == task.task_id), None
    )
    assert our_feedback is not None
    assert our_feedback["rating"] == "up"
    assert our_feedback["comment"] == "Great response!"
    assert our_feedback["user_id"] == "sam_dev_user"


def test_get_feedback_filters_by_task_id(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that feedback can be filtered by task_id.
    """
    # Arrange: Create two tasks with different feedback
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task1 = gateway_adapter.send_message(session.id, "Task 1")
    task2 = gateway_adapter.send_message(session.id, "Task 2")

    # Manually create the task records so the feedback endpoint can find them
    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        tasks_table = metadata.tables["tasks"]
        conn.execute(
            tasks_table.insert().values(
                id=task1.task_id,
                user_id="sam_dev_user",
                initial_request_text="Task 1",
                start_time=now_epoch_ms(),
                end_time=now_epoch_ms(),
            )
        )
        conn.execute(
            tasks_table.insert().values(
                id=task2.task_id,
                user_id="sam_dev_user",
                initial_request_text="Task 2",
                start_time=now_epoch_ms(),
                end_time=now_epoch_ms(),
            )
        )
        if conn.in_transaction():
            conn.commit()

    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task1.task_id,
            "sessionId": session.id,
            "feedbackType": "up",
            "feedbackText": "Task 1 feedback",
        },
    )
    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task2.task_id,
            "sessionId": session.id,
            "feedbackType": "down",
            "feedbackText": "Task 2 feedback",
        },
    )

    # Act: Filter by task1
    response = api_client.get(f"/api/v1/feedback?task_id={task1.task_id}")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()
    assert len(feedback_list) == 1
    assert feedback_list[0]["task_id"] == task1.task_id
    assert feedback_list[0]["comment"] == "Task 1 feedback"


def test_get_feedback_filters_by_rating(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that feedback can be filtered by rating type.
    """
    # Arrange: Create multiple feedback entries with different ratings
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task1 = gateway_adapter.send_message(session.id, "Task with positive feedback")
    task2 = gateway_adapter.send_message(session.id, "Task with negative feedback")

    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task1.task_id,
            "sessionId": session.id,
            "feedbackType": "up",
        },
    )
    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task2.task_id,
            "sessionId": session.id,
            "feedbackType": "down",
        },
    )

    # Act: Filter by rating "down"
    response = api_client.get("/api/v1/feedback?rating=down")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()

    # Find our negative feedback
    our_feedback = next(
        (f for f in feedback_list if f["task_id"] == task2.task_id), None
    )
    assert our_feedback is not None
    assert our_feedback["rating"] == "down"


def test_get_feedback_filters_by_session_id(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that feedback can be filtered by session_id.
    """
    # Arrange: Create two sessions with different feedback
    session1 = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    session2 = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    task1 = gateway_adapter.send_message(session1.id, "Task in session 1")
    task2 = gateway_adapter.send_message(session2.id, "Task in session 2")

    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task1.task_id,
            "sessionId": session1.id,
            "feedbackType": "up",
            "feedbackText": "Session 1 feedback",
        },
    )
    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task2.task_id,
            "sessionId": session2.id,
            "feedbackType": "down",
            "feedbackText": "Session 2 feedback",
        },
    )

    # Act: Filter by session1
    response = api_client.get(f"/api/v1/feedback?session_id={session1.id}")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()
    assert len(feedback_list) == 1
    assert feedback_list[0]["session_id"] == session1.id
    assert feedback_list[0]["comment"] == "Session 1 feedback"


def test_get_feedback_filters_by_date_range(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that feedback can be filtered by date range.
    """
    from datetime import datetime, timedelta

    # Arrange: Create feedback
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task = gateway_adapter.send_message(session.id, "Task for date filter test")

    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task.task_id,
            "sessionId": session.id,
            "feedbackType": "up",
            "feedbackText": "Recent feedback",
        },
    )

    # Act: Filter by date range (last 24 hours to now)
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=24)

    response = api_client.get(
        f"/api/v1/feedback?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
    )

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()

    # Should find our feedback
    our_feedback = next(
        (f for f in feedback_list if f["task_id"] == task.task_id), None
    )
    assert our_feedback is not None


def test_get_feedback_combined_filters(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that multiple filters can be combined.
    """
    # Arrange: Create multiple feedback entries
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )
    task1 = gateway_adapter.send_message(session.id, "Task 1")
    task2 = gateway_adapter.send_message(session.id, "Task 2")

    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task1.task_id,
            "sessionId": session.id,
            "feedbackType": "up",
        },
    )
    api_client.post(
        "/api/v1/feedback",
        json={
            "taskId": task2.task_id,
            "sessionId": session.id,
            "feedbackType": "down",
        },
    )

    # Act: Filter by session AND rating
    response = api_client.get(
        f"/api/v1/feedback?session_id={session.id}&rating=up"
    )

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()
    assert len(feedback_list) == 1
    assert feedback_list[0]["task_id"] == task1.task_id
    assert feedback_list[0]["rating"] == "up"


def test_get_feedback_pagination(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that pagination parameters work correctly.
    """
    # Arrange: Create multiple feedback entries
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    for i in range(5):
        task = gateway_adapter.send_message(session.id, f"Task {i}")
        api_client.post(
            "/api/v1/feedback",
            json={
                "taskId": task.task_id,
                "sessionId": session.id,
                "feedbackType": "up",
            },
        )

    # Act: Get first page with page_size=2
    response = api_client.get("/api/v1/feedback?page=1&page_size=2")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()
    assert len(feedback_list) == 2


def test_get_feedback_user_cannot_access_others_feedback(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that regular users cannot see feedback from other users.
    """
    # Arrange: Create task owned by a different user in database directly
    with database_inspector.db_manager.get_gateway_connection() as conn:
        metadata = sa.MetaData()
        metadata.reflect(bind=conn)
        tasks_table = metadata.tables["tasks"]
        feedback_table = metadata.tables["feedback"]

        other_task_id = f"task-{uuid.uuid4().hex[:8]}"
        other_feedback_id = str(uuid.uuid4())

        # Create task for another user
        conn.execute(
            tasks_table.insert().values(
                id=other_task_id,
                user_id="other_user",
                initial_request_text="Other user's task",
                start_time=now_epoch_ms(),
            )
        )

        # Create feedback for another user
        conn.execute(
            feedback_table.insert().values(
                id=other_feedback_id,
                task_id=other_task_id,
                session_id="other-session",
                user_id="other_user",
                rating="up",
                comment="Other user's feedback",
                created_time=now_epoch_ms(),
            )
        )

        if conn.in_transaction():
            conn.commit()

    # Act: Try to retrieve feedback (should only see own feedback, not other user's)
    response = api_client.get("/api/v1/feedback")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()

    # Should not see other user's feedback
    other_feedback = next(
        (f for f in feedback_list if f["user_id"] == "other_user"), None
    )
    assert other_feedback is None


def test_get_feedback_invalid_date_format_returns_400(api_client: TestClient):
    """
    Tests that invalid date format returns 400 Bad Request.
    """
    # Act: Use invalid date format
    response = api_client.get("/api/v1/feedback?start_date=not-a-date")

    # Assert
    assert response.status_code == 400
    error_data = response.json()
    assert "Invalid start_date format" in error_data["detail"]


def test_get_feedback_for_nonexistent_task_returns_404(
    api_client: TestClient,
):
    """
    Tests that querying feedback for a non-existent task returns 404.
    """
    # Act: Query for non-existent task
    fake_task_id = f"task-{uuid.uuid4().hex[:8]}"
    response = api_client.get(f"/api/v1/feedback?task_id={fake_task_id}")

    # Assert
    assert response.status_code == 404
    error_data = response.json()
    assert f"Task with ID '{fake_task_id}' not found" in error_data["detail"]


def test_get_feedback_returns_most_recent_first(
    api_client: TestClient,
    gateway_adapter: GatewayAdapter,
    database_inspector: DatabaseInspector,
):
    """
    Tests that feedback is returned in descending order by creation time (most recent first).
    """
    import time

    # Arrange: Create multiple feedback entries with small delays
    session = gateway_adapter.create_session(
        user_id="sam_dev_user", agent_name="TestAgent"
    )

    task_ids = []
    for i in range(3):
        task = gateway_adapter.send_message(session.id, f"Task {i}")
        task_ids.append(task.task_id)
        api_client.post(
            "/api/v1/feedback",
            json={
                "taskId": task.task_id,
                "sessionId": session.id,
                "feedbackType": "up",
                "feedbackText": f"Feedback {i}",
            },
        )
        time.sleep(0.01)  # Small delay to ensure different timestamps

    # Act: Get feedback
    response = api_client.get("/api/v1/feedback")

    # Assert
    assert response.status_code == 200
    feedback_list = response.json()

    # Filter to only our feedback
    our_feedback = [f for f in feedback_list if f["task_id"] in task_ids]
    assert len(our_feedback) == 3

    # Verify they're in descending order by created_time
    for i in range(len(our_feedback) - 1):
        assert our_feedback[i]["created_time"] >= our_feedback[i + 1]["created_time"]
