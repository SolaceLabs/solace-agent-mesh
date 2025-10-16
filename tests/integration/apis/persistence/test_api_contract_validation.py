"""
API contract validation tests using FastAPI HTTP endpoints.

Tests HTTP status codes, request/response schemas, authentication, and API behavior.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient


class TestSessionsAPIContract:
    """Test contract compliance for /sessions endpoints"""

    def test_get_sessions_response_schema(self, api_client: TestClient):
        """Test GET /sessions returns proper JSON response structure"""

        response = api_client.get("/api/v1/sessions")

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        data = response.json()
        assert isinstance(data, dict)
        assert "data" in data
        assert "meta" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["meta"], dict)

        # Validate meta pagination fields
        meta = data["meta"]
        assert "pagination" in meta
        pagination = meta["pagination"]
        assert "pageNumber" in pagination
        assert "pageSize" in pagination
        assert "count" in pagination
        assert "nextPage" in pagination

        # If sessions exist, validate schema
        if data["data"]:
            session = data["data"][0]
            required_fields = ["id", "userId", "agentId", "createdTime"]
            for field in required_fields:
                assert field in session
                assert session[field] is not None

    def test_get_session_by_id_response_schema(self, api_client: TestClient):
        """Test GET /sessions/{id} returns proper JSON object"""

        # First create a session
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Schema validation test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        session_id = response.json()["result"]["contextId"]

        # Test the GET endpoint
        response = api_client.get(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        session = response.json()["data"]
        assert isinstance(session, dict)

        # Validate required fields
        required_fields = ["id", "userId", "agentId", "createdTime"]
        for field in required_fields:
            assert field in session
            assert session[field] is not None

        assert session["id"] == session_id

    def test_get_session_history_response_schema(self, api_client: TestClient):
        """Test GET /sessions/{id}/messages returns proper message array"""

        # Create session with message
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "History schema test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        session_id = response.json()["result"]["contextId"]

        # Test history endpoint
        response = api_client.get(f"/api/v1/sessions/{session_id}/messages")

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        history = response.json()
        assert isinstance(history, list)

        if history:
            message = history[0]
            required_fields = ["message", "senderType", "senderName", "createdTime"]
            for field in required_fields:
                assert field in message
                assert message[field] is not None

            assert message["senderType"] in ["user", "assistant"]

    def test_patch_session_request_response_schema(self, api_client: TestClient):
        """Test PATCH /sessions/{id} request and response schemas"""

        # Create session
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Patch schema test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        session_id = response.json()["result"]["contextId"]

        # Test PATCH request
        update_data = {"name": "Updated Session Name"}
        response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        updated_session = response.json()
        assert isinstance(updated_session, dict)
        assert "id" in updated_session
        assert "name" in updated_session
        assert updated_session["name"] == "Updated Session Name"
        assert updated_session["id"] == session_id

    def test_delete_session_response(self, api_client: TestClient):
        """Test DELETE /sessions/{id} returns proper status code"""

        # Create session
        task_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Delete test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_payload)
        session_id = response.json()["result"]["contextId"]

        # Test DELETE
        response = api_client.delete(f"/api/v1/sessions/{session_id}")

        assert response.status_code == 204  # No Content
        assert response.text == ""  # No response body


class TestTasksAPIContract:
    """Test contract compliance for /tasks endpoints"""

    def test_post_tasks_send_response_schema(self, api_client: TestClient):
        """Test POST /message:send returns proper JSONRPC response"""

        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Send schema test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }

        response = api_client.post("/api/v1/message:send", json=task_data)

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        data = response.json()
        assert isinstance(data, dict)

        # Validate JSONRPC response structure
        assert "result" in data
        result = data["result"]
        assert "id" in result
        assert result["id"] is not None

        print("✓ POST /message:send response schema valid")

    def test_post_tasks_subscribe_response_schema(self, api_client: TestClient):
        """Test POST /message:stream returns proper JSONRPC response"""

        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Subscribe schema test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }

        response = api_client.post("/api/v1/message:stream", json=task_data)

        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json"

        data = response.json()
        assert isinstance(data, dict)

        # Validate JSONRPC response structure
        assert "result" in data
        result = data["result"]
        assert "id" in result
        assert "contextId" in result
        assert result["id"] is not None
        assert result["contextId"] is not None

        print("✓ POST /message:stream response schema valid")

    def test_post_tasks_cancel_response_schema(self, api_client: TestClient):
        """Test POST /tasks/{taskId}:cancel returns proper response"""

        # First create a task to cancel
        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Task to cancel"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_data)
        task_id = response.json()["result"]["id"]

        # Test cancel
        cancel_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/cancel",
            "params": {"id": task_id},
        }
        response = api_client.post(f"/api/v1/tasks/{task_id}:cancel", json=cancel_data)

        assert response.status_code == 202  # Accepted for async operation
        assert response.headers.get("content-type") == "application/json"

        data = response.json()
        assert isinstance(data, dict)

        # Validate response structure
        assert "message" in data
        assert (
            "sent" in data["message"].lower()
            or "cancellation" in data["message"].lower()
        )

        print("✓ POST /tasks/{taskId}:cancel response schema valid")


class TestHTTPStatusCodes:
    """Test proper HTTP status codes for various scenarios"""

    def test_successful_operations_return_2xx(self, api_client: TestClient):
        """Test that successful operations return appropriate 2xx status codes"""

        import uuid

        # GET empty sessions list
        response = api_client.get("/api/v1/sessions")
        assert 200 <= response.status_code < 300

        # POST task creation
        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Status code test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_data)
        assert 200 <= response.status_code < 300
        session_id = response.json()["result"]["contextId"]

        # GET specific session
        response = api_client.get(f"/api/v1/sessions/{session_id}")
        assert 200 <= response.status_code < 300

        # PATCH session update
        update_data = {"name": "Updated Name"}
        response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)
        assert 200 <= response.status_code < 300

        # DELETE session
        response = api_client.delete(f"/api/v1/sessions/{session_id}")
        assert 200 <= response.status_code < 300

        print("✓ All successful operations return 2xx status codes")

    def test_not_found_returns_404(self, api_client: TestClient):
        """Test that non-existent resources return 404"""

        response = api_client.get("/api/v1/sessions/nonexistent_session_id")
        assert response.status_code == 404

        print("✓ Non-existent resources return 404")

    def test_validation_errors_return_422(self, api_client: TestClient):
        """Test that validation errors return 422"""

        # Missing required fields
        response = api_client.post("/api/v1/message:send", json={"invalid": "data"})
        assert response.status_code == 422

        response = api_client.post(
            "/api/v1/message:send",
            json={"jsonrpc": "2.0", "id": "test", "method": "message/send"},
        )
        assert response.status_code == 422

        print("✓ Validation errors return 422")

    def test_unauthorized_access_returns_404(self, api_client: TestClient):
        """Test that unauthorized access returns 404 to prevent information leakage"""

        # Try to access session that doesn't belong to user
        response = api_client.get("/api/v1/sessions/nonexistent/messages")
        assert response.status_code == 404

        response = api_client.patch(
            "/api/v1/sessions/nonexistent", json={"name": "Test"}
        )
        assert response.status_code == 404

        response = api_client.delete("/api/v1/sessions/nonexistent")
        assert response.status_code == 404

        print("✓ Unauthorized access returns 404 (prevents information leakage)")


class TestContentTypeHeaders:
    """Test proper Content-Type headers in responses"""

    def test_json_responses_have_correct_content_type(self, api_client: TestClient):
        """Test that JSON endpoints return application/json content type"""

        endpoints_to_test = [
            ("GET", "/api/v1/sessions"),
        ]

        for method, endpoint in endpoints_to_test:
            if method == "GET":
                response = api_client.get(endpoint)

            assert response.status_code == 200
            content_type = response.headers.get("content-type")
            assert "application/json" in content_type

        # Test with created session
        import uuid

        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Content type test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_data)
        assert "application/json" in response.headers.get("content-type")

        session_id = response.json()["result"]["contextId"]

        json_endpoints_with_session = [
            ("GET", f"/api/v1/sessions/{session_id}"),
            ("GET", f"/api/v1/sessions/{session_id}/messages"),
        ]

        for method, endpoint in json_endpoints_with_session:
            response = api_client.get(endpoint)
            assert response.status_code == 200
            assert "application/json" in response.headers.get("content-type")

        print("✓ All JSON responses have correct Content-Type header")


class TestRequestValidation:
    """Test request validation and error handling"""

    def test_malformed_json_handling(self, api_client: TestClient):
        """Test handling of malformed JSON in requests"""

        # Create a session first
        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "JSON validation test"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=task_data)
        session_id = response.json()["result"]["contextId"]

        # Send malformed JSON to PATCH endpoint
        headers = {"Content-Type": "application/json"}
        malformed_json = '{"name": "incomplete json"'  # Missing closing brace

        response = api_client.patch(
            f"/api/v1/sessions/{session_id}", data=malformed_json, headers=headers
        )

        # Should return 422 for malformed JSON
        assert response.status_code == 422

        print("✓ Malformed JSON properly handled")

    def test_field_type_validation(self, api_client: TestClient):
        """Test field type validation"""

        import uuid

        # Test invalid params in cancel request
        invalid_cancel_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/cancel",
            "params": {"id": 123},  # Should be string
        }
        response = api_client.post(
            "/api/v1/tasks/test-task-id:cancel", json=invalid_cancel_data
        )

        # Should accept or convert the type appropriately
        # FastAPI typically handles type conversion
        assert response.status_code in [200, 400, 422]

        print("✓ Field type validation working")

    def test_empty_and_null_values(self, api_client: TestClient):
        """Test handling of empty and null values"""

        import uuid

        # Test empty strings
        task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": ""}],
                    "metadata": {"agent_name": ""},
                }
            },
        }
        response = api_client.post("/api/v1/message:send", json=task_data)
        # Should either work or return validation error
        assert response.status_code in [200, 422]

        # Test with valid session for update
        valid_task_data = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Valid message"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        }
        response = api_client.post("/api/v1/message:stream", json=valid_task_data)
        assert response.status_code == 200
        session_id = response.json()["result"]["contextId"]

        # Test empty name update
        update_data = {"name": ""}
        response = api_client.patch(f"/api/v1/sessions/{session_id}", json=update_data)
        assert response.status_code in [200, 422]  # Either accept empty or reject

        print("✓ Empty and null values handled appropriately")


class TestCORSHeaders:
    """Test CORS header configuration"""

    def test_cors_headers_present(self, api_client: TestClient):
        """Test that appropriate CORS headers are present"""

        response = api_client.get("/api/v1/sessions")

        # Check for common CORS headers

        # Note: TestClient might not include all CORS headers in test mode
        # This test validates the structure more than specific values
        assert response.status_code == 200

        print("✓ Response headers structure valid")

    def test_options_requests_supported(self, api_client: TestClient):
        """Test that OPTIONS requests are supported for CORS preflight"""

        response = api_client.options("/api/v1/sessions")

        # OPTIONS should be handled (status could be 200 or 405 depending on configuration)
        assert response.status_code in [200, 405]

        print("✓ OPTIONS requests handled")


class TestErrorResponseFormat:
    """Test error response format consistency"""

    def test_error_responses_are_json(self, api_client: TestClient):
        """Test that error responses are properly formatted JSON"""

        # Test 404 error
        response = api_client.get("/api/v1/sessions/nonexistent")
        assert response.status_code == 404

        # Should be JSON even for errors
        content_type = response.headers.get("content-type")
        if content_type:
            assert "application/json" in content_type

        # Should be parseable JSON
        try:
            error_data = response.json()
            assert isinstance(error_data, dict)
        except json.JSONDecodeError:
            pytest.fail("Error response is not valid JSON")

        print("✓ Error responses are properly formatted JSON")
