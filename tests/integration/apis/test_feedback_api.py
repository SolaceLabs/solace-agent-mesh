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

from solace_agent_mesh.gateway.http_sse.shared import now_epoch_ms

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
        user_id="feedback_user", agent_name="TestAgent"
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
        user_id="multi_feedback_user", agent_name="TestAgent"
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
        user_id="none_user", agent_name="TestAgent"
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
        user_id="disabled_user", agent_name="TestAgent"
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
        user_id="custom_topic_user", agent_name="TestAgent"
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
        user_id="resilience_user", agent_name="TestAgent"
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
        user_id="missing_task_user", agent_name="TestAgent"
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
