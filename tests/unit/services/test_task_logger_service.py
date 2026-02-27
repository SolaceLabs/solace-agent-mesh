"""
Unit tests for TaskLoggerService.
"""

import json
import math
import pytest

from solace_agent_mesh.gateway.http_sse.services.task_logger_service import (
    TaskLoggerService,
)


class TestSanitizeNonFiniteFloats:
    """Tests for the _sanitize_non_finite_floats static method."""

    def test_sanitize_nan_value(self):
        """NaN values should be replaced with None."""
        result = TaskLoggerService._sanitize_non_finite_floats(float("nan"))
        assert result is None

    def test_sanitize_positive_infinity(self):
        """Positive infinity should be replaced with None."""
        result = TaskLoggerService._sanitize_non_finite_floats(float("inf"))
        assert result is None

    def test_sanitize_negative_infinity(self):
        """Negative infinity should be replaced with None."""
        result = TaskLoggerService._sanitize_non_finite_floats(float("-inf"))
        assert result is None

    def test_preserve_valid_float(self):
        """Valid float values should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats(42.5)
        assert result == 42.5

    def test_preserve_zero(self):
        """Zero should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats(0.0)
        assert result == 0.0

    def test_preserve_negative_float(self):
        """Negative floats should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats(-123.456)
        assert result == -123.456

    def test_preserve_integer(self):
        """Integers should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats(42)
        assert result == 42

    def test_preserve_string(self):
        """Strings should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats("hello")
        assert result == "hello"

    def test_preserve_none(self):
        """None should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats(None)
        assert result is None

    def test_preserve_boolean(self):
        """Booleans should be preserved."""
        assert TaskLoggerService._sanitize_non_finite_floats(True) is True
        assert TaskLoggerService._sanitize_non_finite_floats(False) is False

    def test_sanitize_dict_with_nan(self):
        """Dict containing NaN values should have them replaced with None."""
        input_dict = {
            "valid": 42.5,
            "nan_value": float("nan"),
            "inf_value": float("inf"),
            "neg_inf": float("-inf"),
            "string": "test",
        }
        result = TaskLoggerService._sanitize_non_finite_floats(input_dict)

        assert result["valid"] == 42.5
        assert result["nan_value"] is None
        assert result["inf_value"] is None
        assert result["neg_inf"] is None
        assert result["string"] == "test"

    def test_sanitize_nested_dict(self):
        """Nested dicts should be recursively sanitized."""
        input_dict = {
            "outer": 1.0,
            "nested": {
                "inner_nan": float("nan"),
                "inner_valid": 100,
                "deep": {"deep_inf": float("inf")},
            },
        }
        result = TaskLoggerService._sanitize_non_finite_floats(input_dict)

        assert result["outer"] == 1.0
        assert result["nested"]["inner_nan"] is None
        assert result["nested"]["inner_valid"] == 100
        assert result["nested"]["deep"]["deep_inf"] is None

    def test_sanitize_list_with_nan(self):
        """Lists containing NaN values should have them replaced with None."""
        input_list = [1, float("nan"), 3, float("inf"), 5]
        result = TaskLoggerService._sanitize_non_finite_floats(input_list)

        assert result == [1, None, 3, None, 5]

    def test_sanitize_list_of_dicts(self):
        """Lists of dicts should be recursively sanitized."""
        input_list = [
            {"value": float("nan")},
            {"value": 42.0},
            {"value": float("-inf")},
        ]
        result = TaskLoggerService._sanitize_non_finite_floats(input_list)

        assert result[0]["value"] is None
        assert result[1]["value"] == 42.0
        assert result[2]["value"] is None

    def test_sanitize_empty_dict(self):
        """Empty dict should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats({})
        assert result == {}

    def test_sanitize_empty_list(self):
        """Empty list should be preserved."""
        result = TaskLoggerService._sanitize_non_finite_floats([])
        assert result == []

    def test_result_is_json_serializable(self):
        """Sanitized output should be JSON serializable."""
        input_data = {
            "Fail_Percent_12_Months": float("nan"),
            "Success_Rate": float("inf"),
            "Other_Rate": float("-inf"),
            "Valid_Number": 42.5,
            "Nested": {"inner_nan": float("nan"), "inner_valid": 100},
            "List_with_nan": [1, float("nan"), 3],
        }
        result = TaskLoggerService._sanitize_non_finite_floats(input_data)

        # This should not raise an exception
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        assert parsed["Fail_Percent_12_Months"] is None
        assert parsed["Success_Rate"] is None
        assert parsed["Other_Rate"] is None
        assert parsed["Valid_Number"] == 42.5
        assert parsed["Nested"]["inner_nan"] is None
        assert parsed["Nested"]["inner_valid"] == 100
        assert parsed["List_with_nan"] == [1, None, 3]


class TestSanitizePayload:
    """Tests for the _sanitize_payload method."""

    @pytest.fixture
    def service(self):
        """Create a TaskLoggerService instance for testing."""
        return TaskLoggerService(session_factory=None, config={"enabled": True})

    def test_sanitize_payload_with_nan_values(self, service):
        """Payload with NaN values should be sanitized."""
        payload = {
            "result": {
                "data": {
                    "Fail_Percent_12_Months": float("nan"),
                    "Success_Count": 100,
                }
            }
        }
        result = service._sanitize_payload(payload)

        assert result["result"]["data"]["Fail_Percent_12_Months"] is None
        assert result["result"]["data"]["Success_Count"] == 100

    def test_sanitize_payload_preserves_structure(self, service):
        """Payload structure should be preserved after sanitization."""
        payload = {
            "id": "test-123",
            "jsonrpc": "2.0",
            "result": {
                "contextId": "session-456",
                "status": {"state": "completed"},
            },
        }
        result = service._sanitize_payload(payload)

        assert result["id"] == "test-123"
        assert result["jsonrpc"] == "2.0"
        assert result["result"]["contextId"] == "session-456"
        assert result["result"]["status"]["state"] == "completed"

    def test_sanitize_payload_does_not_modify_original(self, service):
        """Original payload should not be modified."""
        original_nan = float("nan")
        payload = {"value": original_nan}
        
        service._sanitize_payload(payload)
        
        # Original should still have NaN
        assert math.isnan(payload["value"])

    def test_sanitize_payload_with_parts_containing_nan(self, service):
        """Parts in payload should have NaN values sanitized."""
        payload = {
            "result": {
                "status": {
                    "message": {
                        "parts": [
                            {"kind": "text", "text": "hello"},
                            {"kind": "data", "data": {"value": float("nan")}},
                        ]
                    }
                }
            }
        }
        result = service._sanitize_payload(payload)

        parts = result["result"]["status"]["message"]["parts"]
        assert parts[0]["text"] == "hello"
        assert parts[1]["data"]["value"] is None
