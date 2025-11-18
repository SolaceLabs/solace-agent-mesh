"""
Error response consistency tests for FastAPI HTTP endpoints.

Tests that error responses are consistently formatted and contain appropriate
information across all API endpoints.
"""

import json

import pytest
from fastapi.testclient import TestClient


def test_404_error_response_consistency(api_client: TestClient):
    """Test that all 404 errors have consistent response format"""

    # List of endpoints that should return 404 for non-existent resources
    not_found_endpoints = [
        ("GET", "/api/v1/sessions/nonexistent_session_id"),
        ("GET", "/api/v1/sessions/nonexistent_session_id/messages"),
        ("PATCH", "/api/v1/sessions/nonexistent_session_id", {"name": "Test"}),
        ("DELETE", "/api/v1/sessions/nonexistent_session_id"),
    ]

    for method, endpoint, *data in not_found_endpoints:
        if method == "GET":
            response = api_client.get(endpoint)
        elif method == "PATCH":
            response = api_client.patch(endpoint, json=data[0])
        elif method == "DELETE":
            response = api_client.delete(endpoint)

        # All should return 404
        assert response.status_code == 404

        # Should have JSON content type
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

        # Should be valid JSON
        try:
            error_data = response.json()
            assert isinstance(error_data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"404 response from {method} {endpoint} is not valid JSON")

        # Should contain error message
        assert "detail" in error_data
        assert isinstance(error_data["detail"], str)
        assert len(error_data["detail"]) > 0
        assert "session not found" in error_data["detail"].lower()


def test_422_validation_error_response_consistency(api_client: TestClient):
    """Test that all validation errors have consistent response format"""

    # List of requests that should trigger validation errors
    validation_error_requests = [
        ("POST", "/api/v1/message:send", {}),  # Missing required fields
        ("POST", "/api/v1/message:stream", {}),  # Missing required fields
    ]

    for method, endpoint, data in validation_error_requests:
        if method == "POST":
            response = api_client.post(endpoint, json=data)

        # Should return 422 for validation errors
        assert response.status_code == 422

        # Should have JSON content type
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

        # Should be valid JSON
        try:
            error_data = response.json()
            assert isinstance(error_data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"422 response from {method} {endpoint} is not valid JSON")

        # FastAPI validation errors should have specific structure
        if "detail" in error_data:
            # Should have message field
            assert isinstance(error_data["detail"], str)

        # May have validationDetails for field-specific errors
        if "validationDetails" in error_data and error_data["validationDetails"]:
            assert isinstance(error_data["validationDetails"], dict)


def test_error_response_headers_consistency(api_client: TestClient):
    """Test that error responses have consistent headers"""

    # Test various error scenarios
    error_scenarios = [
        # 404 errors
        ("GET", "/api/v1/sessions/nonexistent", 404),
        ("PATCH", "/api/v1/sessions/nonexistent", 404, {"name": "Test"}),
        ("DELETE", "/api/v1/sessions/nonexistent", 404),
        # 422 validation errors
        ("POST", "/api/v1/message:send", 422, {}),
        ("POST", "/api/v1/message:stream", 422, {}),
    ]

    for scenario in error_scenarios:
        method, endpoint, expected_status = scenario[:3]
        data = scenario[3] if len(scenario) > 3 else None

        if method == "GET":
            response = api_client.get(endpoint)
        elif method == "POST":
            response = api_client.post(endpoint, json=data or {})
        elif method == "PATCH":
            response = api_client.patch(endpoint, json=data or {})
        elif method == "DELETE":
            response = api_client.delete(endpoint)

        assert response.status_code == expected_status

        # Check headers
        headers = response.headers

        # Should have content-type header
        assert "content-type" in headers
        content_type = headers["content-type"]
        assert "application/json" in content_type

        # Should not have any sensitive headers in errors
        sensitive_headers = ["authorization", "x-api-key", "cookie"]
        for sensitive_header in sensitive_headers:
            assert sensitive_header not in headers


def test_error_message_security_no_leakage(api_client: TestClient):
    """Test that error messages don't leak sensitive information"""

    # Create a session first to test access control
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
                "parts": [{"kind": "text", "text": "Security test session"}],
                "metadata": {"agent_name": "TestAgent"},
            }
        },
    }
    response = api_client.post("/api/v1/message:stream", json=task_data)
    assert response.status_code == 200
    valid_session_id = response.json()["result"]["contextId"]

    # Test accessing non-existent resources (should not reveal existence)
    security_test_cases = [
        ("GET", "/api/v1/sessions/completely_fake_session_id"),
        ("GET", f"/api/v1/sessions/{valid_session_id}_fake/messages"),
        ("PATCH", "/api/v1/sessions/fake_session_123", {"name": "Test"}),
        ("DELETE", "/api/v1/sessions/another_fake_session"),
    ]

    for method, endpoint, *data in security_test_cases:
        if method == "GET":
            response = api_client.get(endpoint)
        elif method == "PATCH":
            response = api_client.patch(endpoint, json=data[0])
        elif method == "DELETE":
            response = api_client.delete(endpoint)

        assert response.status_code == 404

        error_data = response.json()
        error_message = error_data.get("detail").lower()

        # Error message should not reveal sensitive information
        sensitive_terms = [
            "exist",  # Avoid "session exists but access denied"
            "permission",  # Avoid "no permission"
            "unauthorized",  # Should be "not found" instead
            "forbidden",  # Should be "not found" instead
            "user",  # Avoid revealing user information
            "database",  # Avoid revealing database details
            "internal",  # Avoid internal error details
        ]

        for term in sensitive_terms:
            if term in ["exist", "permission", "unauthorized", "forbidden", "user"]:
                # These terms should definitely not appear
                assert term not in error_message, (
                    f"Error message contains sensitive term '{term}': {error_message}"
                )

        # Should contain generic "not found" message
        assert "not found" in error_message


def test_error_response_structure_validation(api_client: TestClient):
    """Test that error responses follow consistent structure"""

    # Generate various types of errors
    error_test_cases = [
        # 404 errors
        {
            "request": ("GET", "/api/v1/sessions/nonexistent"),
            "expected_status": 404,
            "expected_fields": ["detail"],
        },
        # 422 validation errors
        {
            "request": ("POST", "/api/v1/message:send", {}),
            "expected_status": 422,
            "expected_fields": ["detail"],
        },
    ]

    for test_case in error_test_cases:
        method, endpoint, *data = test_case["request"]
        expected_status = test_case["expected_status"]
        test_case["expected_fields"]

        if method == "GET":
            response = api_client.get(endpoint)
        elif method == "POST":
            response = api_client.post(endpoint, json=data[0] if data else {})

        assert response.status_code == expected_status

        # Validate response structure
        try:
            error_data = response.json()
            assert isinstance(error_data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"Error response is not valid JSON: {response.text}")

        # Check required fields are present
        # Handle both standard HTTP error format and JSON-RPC format
        if "jsonrpc" in error_data:
            # JSON-RPC format - check for error field
            assert "error" in error_data, (
                "Missing 'error' field in JSON-RPC error response"
            )
            assert error_data["error"] is not None
            assert "data" in error_data["error"], "Missing 'data' in JSON-RPC error"
        else:
            # Standard HTTP error format - should have 'detail' field
            assert "detail" in error_data, (
                "Missing required field 'detail' in error response"
            )
            assert error_data["detail"] is not None
            assert len(str(error_data["detail"])) > 0

        # Ensure no internal/debug fields are exposed
        internal_fields = [
            "traceback",
            "stack_trace",
            "exception",
            "debug",
            "internal_error",
            "sql",
            "database",
            "file_path",
        ]

        for internal_field in internal_fields:
            assert internal_field not in error_data, (
                f"Internal field '{internal_field}' exposed in error response"
            )


def test_content_type_consistency_in_errors(api_client: TestClient):
    """Test that error responses have consistent content-type headers"""

    # Test different types of errors
    error_endpoints = [
        ("GET", "/api/v1/sessions/nonexistent", 404),
        ("POST", "/api/v1/message:send", 422, {}),
        ("PATCH", "/api/v1/sessions/nonexistent", 404, {"name": "Test"}),
        ("DELETE", "/api/v1/sessions/nonexistent", 404),
    ]

    for scenario in error_endpoints:
        method, endpoint, expected_status = scenario[:3]
        data = scenario[3] if len(scenario) > 3 else None

        if method == "GET":
            response = api_client.get(endpoint)
        elif method == "POST":
            response = api_client.post(endpoint, data=data or {})
        elif method == "PATCH":
            response = api_client.patch(endpoint, json=data or {})
        elif method == "DELETE":
            response = api_client.delete(endpoint)

        assert response.status_code == expected_status

        # Check content-type consistency
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

        # Ensure charset is specified if present
        if "charset" in content_type:
            assert "utf-8" in content_type.lower()

    print("✓ Error response content-type headers are consistent")


def test_error_response_encoding_handling(api_client: TestClient):
    """Test that error responses handle encoding correctly"""

    import uuid

    # Test with unicode characters in request that causes error
    unicode_test_cases = [
        {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "测试消息 🚀"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        },  # Valid unicode
        {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Test"}],
                    "metadata": {},  # Missing agent_name
                }
            },
        },
        {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": str(uuid.uuid4()),
                    "kind": "message",
                    "parts": [{"kind": "text", "text": "Test with émojis 🎉"}],
                    "metadata": {"agent_name": "TestAgent"},
                }
            },
        },
    ]

    for test_data in unicode_test_cases:
        response = api_client.post("/api/v1/message:send", json=test_data)

        # Should handle unicode correctly even in errors
        if response.status_code != 200:
            # Should be valid JSON even with unicode
            try:
                error_data = response.json()
                assert isinstance(error_data, dict)

                # Error messages should be properly encoded strings
                if "message" in error_data:
                    message = error_data["message"]
                    assert isinstance(message, str)

                    # Should not contain encoding artifacts
                    assert "\\u" not in message  # No escaped unicode
                    assert "\\x" not in message  # No escaped bytes

            except (json.JSONDecodeError, UnicodeDecodeError):
                pytest.fail(
                    f"Error response with unicode data failed to decode: {response.content}"
                )

    print("✓ Error responses handle encoding correctly")
