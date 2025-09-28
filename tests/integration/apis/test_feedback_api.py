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

from solace_agent_mesh.gateway.http_sse.repository.models import FeedbackModel


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
