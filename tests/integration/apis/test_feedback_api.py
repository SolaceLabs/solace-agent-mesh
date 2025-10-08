"""
API integration tests for the feedback router.

These tests verify that the /feedback endpoint correctly processes
feedback payloads and interacts with the configured FeedbackService,
including writing to CSV files and logging.
"""

import csv
import logging
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from solace_ai_connector.common.log import log
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.repository.models import FeedbackModel, TaskModel
from solace_agent_mesh.gateway.http_sse.shared import now_epoch_ms


def test_submit_feedback_persists_to_database(api_client: TestClient, test_database_engine):
    """
    Tests that a valid feedback submission creates a record in the database.
    """
    # Arrange: First, create a task to get a valid taskId and sessionId
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for feedback"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_result = task_response.json()["result"]
    task_id = task_result["id"]
    session_id = task_result["contextId"]

    feedback_payload = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "up",
        "feedbackText": "This was very helpful!",
    }

    # Act: Submit the feedback
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert: Check HTTP response and database state
    assert response.status_code == 202
    assert response.json() == {"status": "feedback received"}

    # Verify database record
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        feedback_record = (
            db_session.query(FeedbackModel).filter_by(task_id=task_id).one_or_none()
        )
        assert feedback_record is not None
        assert feedback_record.session_id == session_id
        assert feedback_record.rating == "up"
        assert feedback_record.comment == "This was very helpful!"
        assert feedback_record.user_id == "sam_dev_user"  # From default mock auth
    finally:
        db_session.close()


def test_submit_multiple_feedback_records(api_client: TestClient, test_database_engine):
    """
    Tests that multiple feedback submissions for the same task create distinct records.
    """
    # Arrange: Create one task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for multiple feedback"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_result = task_response.json()["result"]
    task_id = task_result["id"]
    session_id = task_result["contextId"]

    payload1 = {"taskId": task_id, "sessionId": session_id, "feedbackType": "up"}
    payload2 = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "down",
        "feedbackText": "Confusing",
    }

    # Act: Submit two feedback payloads
    api_client.post("/api/v1/feedback", json=payload1)
    api_client.post("/api/v1/feedback", json=payload2)

    # Assert: Check database for two records
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        feedback_records = (
            db_session.query(FeedbackModel).filter_by(task_id=task_id).all()
        )
        assert len(feedback_records) == 2
        ratings = {record.rating for record in feedback_records}
        assert ratings == {"up", "down"}
    finally:
        db_session.close()



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
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Tests that feedback is published as an event when feedback_publishing is enabled.
    """
    # Arrange:
    # 1. Mock the component's config to enable publishing
    mock_publish_func = MagicMock()

    # Get the actual component instance used by the test client
    from solace_agent_mesh.gateway.http_sse import dependencies

    component = dependencies.sac_component_instance

    # Monkeypatch the component's config and publish method
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

    # 2. Create a task via API
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for event publishing"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_result = task_response.json()["result"]
    task_id = task_result["id"]
    session_id = task_result["contextId"]

    # 3. Manually create a task record in the DB so that feedback service can find it
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for event publishing",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {"taskId": task_id, "sessionId": session_id, "feedbackType": "up"}

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202

    # Verify the publish function was called
    mock_publish_func.assert_called_once()
    call_args, call_kwargs = mock_publish_func.call_args

    published_topic = call_args[0]
    published_payload = call_args[1]

    assert published_topic == "sam/feedback/test/v1"
    assert published_payload["feedback"]["task_id"] == task_id
    assert published_payload["feedback"]["feedback_type"] == "up"
    assert "task_summary" in published_payload
    assert published_payload["task_summary"]["id"] == task_id


def test_feedback_publishing_with_include_task_info_none(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Tests that when include_task_info is 'none', no task info is included in the published event.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

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

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for none test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task in DB
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for none test",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {"taskId": task_id, "sessionId": session_id, "feedbackType": "down"}

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    
    published_payload = mock_publish_func.call_args[0][1]
    
    # Should have feedback but no task_summary or task_stim_data
    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == task_id
    assert "task_summary" not in published_payload
    assert "task_stim_data" not in published_payload


def test_feedback_publishing_with_include_task_info_stim(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Tests that when include_task_info is 'stim', full task history is included in the published event.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "stim",
            "max_payload_size_bytes": 9000000,  # Large enough to not trigger fallback
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for stim test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task and events in DB
    from solace_agent_mesh.gateway.http_sse.repository.models import TaskEventModel
    
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for stim test",
            status="completed",
        )
        db_session.add(new_task)
        
        # Add some task events
        event1 = TaskEventModel(
            id=str(uuid.uuid4()),
            task_id=task_id,
            user_id="sam_dev_user",
            created_time=now_epoch_ms(),
            topic="test/topic/request",
            direction="request",
            payload={"test": "request_payload"},
        )
        event2 = TaskEventModel(
            id=str(uuid.uuid4()),
            task_id=task_id,
            user_id="sam_dev_user",
            created_time=now_epoch_ms() + 1000,
            topic="test/topic/response",
            direction="response",
            payload={"test": "response_payload"},
        )
        db_session.add(event1)
        db_session.add(event2)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {"taskId": task_id, "sessionId": session_id, "feedbackType": "up"}

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    
    published_payload = mock_publish_func.call_args[0][1]
    
    # Should have feedback and task_stim_data
    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == task_id
    assert "task_stim_data" in published_payload
    
    # Verify stim structure
    stim_data = published_payload["task_stim_data"]
    assert "invocation_details" in stim_data
    assert "invocation_flow" in stim_data
    assert stim_data["invocation_details"]["task_id"] == task_id
    assert len(stim_data["invocation_flow"]) == 2  # Two events we created


def test_feedback_publishing_stim_fallback_to_summary_on_size_limit(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Tests that when include_task_info is 'stim' but payload exceeds max_payload_size_bytes,
    it falls back to 'summary' mode.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": "sam/feedback/test/v1",
            "include_task_info": "stim",
            "max_payload_size_bytes": 100,  # Very small to trigger fallback
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for fallback test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task and events in DB
    from solace_agent_mesh.gateway.http_sse.repository.models import TaskEventModel
    
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for fallback test",
            status="completed",
        )
        db_session.add(new_task)
        
        # Add events with large payloads
        event1 = TaskEventModel(
            id=str(uuid.uuid4()),
            task_id=task_id,
            user_id="sam_dev_user",
            created_time=now_epoch_ms(),
            topic="test/topic/request",
            direction="request",
            payload={"large_data": "x" * 1000},  # Large payload
        )
        db_session.add(event1)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {"taskId": task_id, "sessionId": session_id, "feedbackType": "up"}

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    
    published_payload = mock_publish_func.call_args[0][1]
    
    # Should have feedback and task_summary (not stim_data due to fallback)
    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == task_id
    assert "task_summary" in published_payload
    assert "task_stim_data" not in published_payload
    
    # Should have truncation details explaining the fallback
    assert "truncation_details" in published_payload
    assert published_payload["truncation_details"]["strategy"] == "fallback_to_summary"
    assert published_payload["truncation_details"]["reason"] == "payload_too_large"


def test_feedback_publishing_disabled_skips_event_but_saves_to_db(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Tests that when feedback_publishing.enabled = False, no event is published
    but feedback is still saved to the database.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

    # Disable feedback publishing
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": False,  # Publishing disabled
            "topic": "sam/feedback/test/v1",
            "include_task_info": "summary",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for disabled publishing test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task in DB
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for disabled publishing test",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "down",
        "feedbackText": "This needs improvement"
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    
    # Verify publish was NOT called
    mock_publish_func.assert_not_called()
    
    # But feedback should still be saved to database
    db_session = Session()
    try:
        feedback_record = (
            db_session.query(FeedbackModel).filter_by(task_id=task_id).one_or_none()
        )
        assert feedback_record is not None
        assert feedback_record.task_id == task_id
        assert feedback_record.session_id == session_id
        assert feedback_record.rating == "down"
        assert feedback_record.comment == "This needs improvement"
        assert feedback_record.user_id == "sam_dev_user"
    finally:
        db_session.close()


def test_feedback_publishing_uses_custom_topic(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Test 3: Custom Topic Configuration
    Tests that the configured custom topic is used for publishing feedback events.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

    custom_topic = "custom/feedback/topic/v2"
    
    monkeypatch.setattr(
        component,
        "get_config",
        lambda key, default=None: {
            "enabled": True,
            "topic": custom_topic,  # Custom topic
            "include_task_info": "none",
        }
        if key == "feedback_publishing"
        else default,
    )
    monkeypatch.setattr(component, "publish_a2a", mock_publish_func)

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for custom topic test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task in DB
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for custom topic test",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "up"
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    
    # Verify publish was called with custom topic
    mock_publish_func.assert_called_once()
    call_args = mock_publish_func.call_args[0]
    
    published_topic = call_args[0]
    published_payload = call_args[1]
    
    # Verify custom topic was used
    assert published_topic == custom_topic
    assert published_payload["feedback"]["task_id"] == task_id
    assert published_payload["feedback"]["feedback_type"] == "up"


def test_feedback_publishing_failure_does_not_break_saving(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Test 4: Publishing Failure Doesn't Break Feedback Saving
    Tests that if publish_a2a raises an exception, the feedback is still saved to the database.
    """
    # Arrange
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

    # Create a mock that raises an exception when called
    def mock_publish_that_fails(topic, payload, user_properties=None):
        raise Exception("Simulated publishing failure")
    
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
    monkeypatch.setattr(component, "publish_a2a", mock_publish_that_fails)

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for publish failure test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task in DB
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            initial_request_text="Task for publish failure test",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "down",
        "feedbackText": "Testing resilience"
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    # Should still return 202 even though publishing failed
    assert response.status_code == 202
    
    # Verify feedback was still saved to database despite publishing failure
    db_session = Session()
    try:
        feedback_record = (
            db_session.query(FeedbackModel).filter_by(task_id=task_id).one_or_none()
        )
        assert feedback_record is not None
        assert feedback_record.task_id == task_id
        assert feedback_record.session_id == session_id
        assert feedback_record.rating == "down"
        assert feedback_record.comment == "Testing resilience"
        assert feedback_record.user_id == "sam_dev_user"
    finally:
        db_session.close()


def test_feedback_publishing_payload_structure_with_summary(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Test 5: Payload Structure Validation
    Tests that the published payload has the correct structure with task_summary.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

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

    # Create task
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for payload structure test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Create task in DB with specific data
    Session = sessionmaker(bind=test_database_engine)
    db_session = Session()
    try:
        new_task = TaskModel(
            id=task_id,
            user_id="sam_dev_user",
            start_time=now_epoch_ms(),
            end_time=now_epoch_ms() + 5000,
            status="completed",
            initial_request_text="Task for payload structure test",
        )
        db_session.add(new_task)
        db_session.commit()
    finally:
        db_session.close()

    feedback_payload = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "up",
        "feedbackText": "Great response!"
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    
    published_payload = mock_publish_func.call_args[0][1]
    
    # Verify feedback object structure
    assert "feedback" in published_payload
    feedback_obj = published_payload["feedback"]
    assert feedback_obj["task_id"] == task_id
    assert feedback_obj["session_id"] == session_id
    assert feedback_obj["feedback_type"] == "up"
    assert feedback_obj["feedback_text"] == "Great response!"
    assert feedback_obj["user_id"] == "sam_dev_user"
    
    # Verify task_summary structure
    assert "task_summary" in published_payload
    task_summary = published_payload["task_summary"]
    assert task_summary["id"] == task_id
    assert task_summary["user_id"] == "sam_dev_user"
    assert task_summary["status"] == "completed"
    assert task_summary["initial_request_text"] == "Task for payload structure test"
    assert "start_time" in task_summary
    assert "end_time" in task_summary


def test_feedback_publishing_with_missing_task(
    api_client: TestClient, monkeypatch, test_database_engine
):
    """
    Test 6: Task Not Found Handling
    Tests behavior when include_task_info is set but the task doesn't exist in the database.
    """
    # Arrange
    mock_publish_func = MagicMock()
    from solace_agent_mesh.gateway.http_sse import dependencies
    component = dependencies.sac_component_instance

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

    # Create task via API but DON'T create it in the database
    task_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/stream",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "kind": "message",
                "parts": [{"kind": "text", "text": "Task for missing task test"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    task_response = api_client.post("/api/v1/message:stream", json=task_payload)
    assert task_response.status_code == 200
    task_id = task_response.json()["result"]["id"]
    session_id = task_response.json()["result"]["contextId"]

    # Note: We intentionally do NOT create the task in the database

    feedback_payload = {
        "taskId": task_id,
        "sessionId": session_id,
        "feedbackType": "down",
        "feedbackText": "Task not found test"
    }

    # Act
    response = api_client.post("/api/v1/feedback", json=feedback_payload)

    # Assert
    assert response.status_code == 202
    mock_publish_func.assert_called_once()
    
    published_payload = mock_publish_func.call_args[0][1]
    
    # Should have feedback object
    assert "feedback" in published_payload
    assert published_payload["feedback"]["task_id"] == task_id
    assert published_payload["feedback"]["feedback_type"] == "down"
    
    # Should NOT have task_summary since task doesn't exist
    assert "task_summary" not in published_payload
    
    # Should NOT have task_stim_data
    assert "task_stim_data" not in published_payload
