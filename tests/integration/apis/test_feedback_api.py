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


@pytest.mark.parametrize(
    "configured_feedback_client",
    [({"type": "csv", "filename": "feedback.csv"})],
    indirect=True,
)
def test_feedback_csv_append(configured_feedback_client):
    """
    Tests that subsequent feedback submissions append to the existing CSV file
    without adding a new header.
    """
    client, tmp_path = configured_feedback_client
    payload1 = {
        "messageId": "msg-1",
        "sessionId": "session-1",
        "feedbackType": "up",
        "feedbackText": "First feedback",
    }
    payload2 = {
        "messageId": "msg-2",
        "sessionId": "session-1",
        "feedbackType": "down",
        "feedbackText": "Second feedback, not good.",
    }

    # Act
    client.post("/api/v1/feedback", json=payload1)
    response = client.post("/api/v1/feedback", json=payload2)

    # Assert HTTP response
    assert response.status_code == 202

    # Assert file content
    csv_file = tmp_path / "feedback.csv"
    with open(csv_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert len(rows) == 3  # Header + 2 data rows
    assert rows[0][0] == "timestamp_utc"  # Check header is still there
    assert rows[2][3] == "msg-2"  # Check second data row content
    assert rows[2][4] == "down"
    assert rows[2][5] == "Second feedback, not good."


@pytest.mark.parametrize(
    "configured_feedback_client",
    [({"type": "log"})],
    indirect=True,
)
def test_feedback_logging_fallback(configured_feedback_client, caplog):
    """
    Tests that feedback is logged when the service type is 'log' and
    no CSV file is created.
    """
    client, tmp_path = configured_feedback_client
    feedback_payload = {
        "messageId": "msg-log",
        "sessionId": "session-log",
        "feedbackType": "up",
    }

    # Act
    with caplog.at_level(logging.INFO):
        response = client.post("/api/v1/feedback", json=feedback_payload)

    # Assert HTTP response
    assert response.status_code == 202

    # Assert logging
    assert "Feedback received from user 'sam_dev_user'" in caplog.text
    assert '"feedbackType":"up"' in caplog.text
    assert '"messageId":"msg-log"' in caplog.text

    # Assert no file was created
    csv_file = tmp_path / "feedback.csv"
    assert not csv_file.exists()


@pytest.mark.parametrize(
    "configured_feedback_client",
    [({"type": "csv", "filename": "feedback.csv"})],
    indirect=True,
)
def test_feedback_invalid_payload(configured_feedback_client):
    """
    Tests that an invalid payload returns a 422 Unprocessable Entity error.
    """
    client, tmp_path = configured_feedback_client
    invalid_payload = {
        "messageId": "msg-invalid",
        # "feedbackType" is missing
    }

    # Act
    response = client.post("/api/v1/feedback", json=invalid_payload)

    # Assert HTTP response
    assert response.status_code == 422

    # Assert no file was created
    csv_file = tmp_path / "feedback.csv"
    assert not csv_file.exists()
