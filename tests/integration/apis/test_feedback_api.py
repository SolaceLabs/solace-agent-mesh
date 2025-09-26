"""
API integration tests for the feedback router.

These tests verify that the /feedback endpoint correctly processes
feedback payloads and interacts with the configured FeedbackService,
including writing to CSV files and logging.
"""

import csv
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from solace_ai_connector.common.log import log


@pytest.mark.parametrize(
    "configured_feedback_client",
    [({"type": "csv", "filename": "feedback.csv"})],
    indirect=True,
)
def test_feedback_csv_creation_and_write(configured_feedback_client):
    """
    Tests that the first feedback submission creates a CSV file with a header
    and the correct data row.
    """
    client, tmp_path = configured_feedback_client
    feedback_payload = {
        "messageId": "msg-123",
        "sessionId": "session-abc",
        "feedbackType": "up",
        "feedbackText": "Very helpful!",
    }

    # Act
    response = client.post("/api/v1/feedback", json=feedback_payload)

    # Assert HTTP response
    assert response.status_code == 202
    assert response.json() == {"status": "feedback received"}

    # Assert file content
    csv_file = tmp_path / "feedback.csv"
    assert csv_file.exists()

    with open(csv_file, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert len(rows) == 2  # Header + 1 data row
    assert rows[0] == [
        "timestamp_utc",
        "user_id",
        "session_id",
        "message_id",
        "feedback_type",
        "feedback_text",
    ]
    data_row = rows[1]
    assert data_row[1] == "sam_dev_user"  # Default user from auth middleware
    assert data_row[2] == feedback_payload["sessionId"]
    assert data_row[3] == feedback_payload["messageId"]
    assert data_row[4] == feedback_payload["feedbackType"]
    assert data_row[5] == feedback_payload["feedbackText"]


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
    with caplog.at_level(log.INFO):
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
