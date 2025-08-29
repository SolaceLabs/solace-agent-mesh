"""
Unit tests for the A2AMessageValidator.
"""

import pytest
from sam_test_infrastructure.a2a_validator.validator import A2AMessageValidator


@pytest.fixture
def validator() -> A2AMessageValidator:
    """Provides an instance of the A2AMessageValidator."""
    return A2AMessageValidator()


def test_validator_initialization(validator: A2AMessageValidator):
    """Tests that the validator initializes correctly and loads the schema."""
    assert validator.active is False
    assert validator.schema is not None
    assert "definitions" in validator.schema
    assert validator.validator is not None


def test_valid_send_message_request(validator: A2AMessageValidator):
    """Tests validation of a valid SendMessageRequest."""
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "msg-1",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Hello"}],
            }
        },
    }
    validator.validate_message(payload, "a2a/v1/agent/request/TestAgent")


def test_valid_task_response(validator: A2AMessageValidator):
    """Tests validation of a valid response containing a Task object."""
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "result": {
            "id": "task-1",
            "contextId": "session-1",
            "kind": "task",
            "status": {
                "state": "completed",
                "message": {
                    "role": "agent",
                    "messageId": "msg-2",
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Done"}],
                },
            },
        },
    }
    validator.validate_message(payload, "a2a/v1/gateway/response/gw-1/task-1")


def test_valid_status_update_response(validator: A2AMessageValidator):
    """Tests validation of a valid response containing a TaskStatusUpdateEvent."""
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "result": {
            "kind": "status-update",
            "taskId": "task-1",
            "contextId": "session-1",
            "final": False,
            "status": {"state": "working"},
        },
    }
    validator.validate_message(payload, "a2a/v1/gateway/status/gw-1/task-1")


def test_invalid_request_missing_jsonrpc(validator: A2AMessageValidator):
    """Tests that a request missing 'jsonrpc' fails validation."""
    payload = {
        "id": "req-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "msg-1",
                "kind": "message",
                "parts": [{"kind": "text", "text": "Hello"}],
            }
        },
    }
    with pytest.raises(pytest.fail.Exception, match="'jsonrpc' is a required property"):
        validator.validate_message(payload, "a2a/v1/agent/request/TestAgent")


def test_invalid_request_bad_method(validator: A2AMessageValidator):
    """Tests that a request with an unknown method falls back to generic validation."""
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "method": "non/existent/method",
        "params": {},
    }
    # This should not fail because it validates against the generic request schema.
    validator.validate_message(payload, "a2a/v1/agent/request/TestAgent")


def test_invalid_response_both_result_and_error(validator: A2AMessageValidator):
    """Tests that a response with both 'result' and 'error' fails validation."""
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "result": {
            "id": "task-1",
            "contextId": "session-1",
            "kind": "task",
            "status": {"state": "completed"},
        },
        "error": {"code": -32000, "message": "An error"},
    }
    with pytest.raises(
        pytest.fail.Exception, match="'result' and 'error' are mutually exclusive"
    ):
        validator.validate_message(payload, "a2a/v1/gateway/response/gw-1/task-1")


def test_invalid_task_missing_id(validator: A2AMessageValidator):
    """Tests that a Task object in a result missing a required field fails validation."""
    payload = {
        "jsonrpc": "2.0",
        "id": "req-1",
        "result": {
            # "id": "task-1",  <-- Missing required field
            "contextId": "session-1",
            "kind": "task",
            "status": {"state": "completed"},
        },
    }
    with pytest.raises(pytest.fail.Exception, match="'id' is a required property"):
        validator.validate_message(payload, "a2a/v1/gateway/response/gw-1/task-1")
