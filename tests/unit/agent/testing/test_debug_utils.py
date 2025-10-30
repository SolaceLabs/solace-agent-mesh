"""
Unit tests for src/solace_agent_mesh/agent/testing/debug_utils.py

Tests the debugging utilities for the declarative test framework including:
- String truncation functionality
- A2A message parts formatting
- Dictionary string truncation (recursive)
- Event history pretty printing
- Various event types handling
- Edge cases and error conditions
"""

from unittest.mock import patch
import pytest

from src.solace_agent_mesh.agent.testing.debug_utils import (
    _truncate,
    _format_a2a_parts,
    _truncate_dict_strings,
    pretty_print_event_history
)


class TestTruncateFunction:
    """Tests for _truncate helper function"""

    def test_truncate_short_string(self):
        """Test truncating string shorter than max length"""
        result = _truncate("hello", 10)
        assert result == "hello"

    def test_truncate_exact_length_string(self):
        """Test truncating string exactly at max length"""
        result = _truncate("hello", 5)
        assert result == "hello"

    def test_truncate_long_string(self):
        """Test truncating string longer than max length"""
        result = _truncate("hello world", 8)
        assert result == "hello..."

    def test_truncate_very_short_max_len(self):
        """Test truncating with very short max length"""
        result = _truncate("hello", 3)
        assert result == "hel"

    def test_truncate_max_len_less_than_ellipsis(self):
        """Test truncating with max length less than ellipsis length"""
        result = _truncate("hello", 2)
        assert result == "he"

    def test_truncate_zero_max_len(self):
        """Test truncating with zero max length"""
        result = _truncate("hello", 0)
        assert result == "hello"  # Should return original when max_len <= 0

    def test_truncate_negative_max_len(self):
        """Test truncating with negative max length"""
        result = _truncate("hello", -5)
        assert result == "hello"  # Should return original when max_len <= 0

    def test_truncate_non_string_input(self):
        """Test truncating non-string input"""
        result = _truncate(12345, 3)
        assert result == "123"

    def test_truncate_none_input(self):
        """Test truncating None input"""
        result = _truncate(None, 10)
        assert result == "None"

    def test_truncate_empty_string(self):
        """Test truncating empty string"""
        result = _truncate("", 10)
        assert result == ""


class TestFormatA2AParts:
    """Tests for _format_a2a_parts helper function"""

    def test_format_empty_parts(self):
        """Test formatting empty parts list"""
        result = _format_a2a_parts([], 100)
        assert result == "[No Parts]"

    def test_format_text_part(self):
        """Test formatting text part"""
        parts = [{"type": "text", "text": "Hello, world!"}]
        result = _format_a2a_parts(parts, 100)
        assert "- [Text]: 'Hello, world!'" in result

    def test_format_text_part_truncated(self):
        """Test formatting text part with truncation"""
        parts = [{"type": "text", "text": "This is a very long text message"}]
        result = _format_a2a_parts(parts, 20)
        assert "- [Text]: 'This is a very lo..." in result

    def test_format_data_part(self):
        """Test formatting data part"""
        parts = [{"type": "data", "data": {"key": "value", "number": 42}}]
        result = _format_a2a_parts(parts, 100)
        assert "- [Data]:" in result
        assert "key" in result
        assert "value" in result

    def test_format_data_part_truncated(self):
        """Test formatting data part with truncation"""
        large_data = {"key": "very_long_value_that_should_be_truncated"}
        parts = [{"type": "data", "data": large_data}]
        result = _format_a2a_parts(parts, 20)
        assert "- [Data]:" in result
        assert "..." in result

    def test_format_file_part(self):
        """Test formatting file part"""
        parts = [{
            "type": "file",
            "file": {
                "name": "document.pdf",
                "mimeType": "application/pdf"
            }
        }]
        result = _format_a2a_parts(parts, 100)
        assert "- [File]: document.pdf (application/pdf)" in result

    def test_format_file_part_missing_fields(self):
        """Test formatting file part with missing fields"""
        parts = [{"type": "file", "file": {}}]
        result = _format_a2a_parts(parts, 100)
        assert "- [File]: N/A (N/A)" in result

    def test_format_file_part_truncated_name(self):
        """Test formatting file part with truncated name"""
        parts = [{
            "type": "file",
            "file": {
                "name": "very_long_filename_that_should_be_truncated.pdf",
                "mimeType": "application/pdf"
            }
        }]
        result = _format_a2a_parts(parts, 30)
        assert "- [File]:" in result
        assert "..." in result

    def test_format_unknown_part_type(self):
        """Test formatting unknown part type"""
        parts = [{"type": "unknown", "custom_field": "custom_value"}]
        result = _format_a2a_parts(parts, 100)
        assert "- [Unknown Part]:" in result
        assert "custom_field" in result

    def test_format_multiple_parts(self):
        """Test formatting multiple parts"""
        parts = [
            {"type": "text", "text": "Hello"},
            {"type": "data", "data": {"key": "value"}},
            {"type": "file", "file": {"name": "test.txt", "mimeType": "text/plain"}}
        ]
        result = _format_a2a_parts(parts, 100)
        
        lines = result.split('\n')
        assert len(lines) == 3
        assert "- [Text]: 'Hello'" in lines[0]
        assert "- [Data]:" in lines[1]
        assert "- [File]: test.txt (text/plain)" in lines[2]

    def test_format_part_without_type(self):
        """Test formatting part without type field"""
        parts = [{"text": "Hello"}]  # Missing "type" field
        result = _format_a2a_parts(parts, 100)
        assert "- [Unknown Part]:" in result


class TestTruncateDictStrings:
    """Tests for _truncate_dict_strings helper function"""

    def test_truncate_dict_strings_simple_dict(self):
        """Test truncating strings in simple dictionary"""
        data = {"key1": "short", "key2": "this is a very long string"}
        result = _truncate_dict_strings(data, 10)
        
        assert result["key1"] == "short"
        assert result["key2"] == "this is..."

    def test_truncate_dict_strings_nested_dict(self):
        """Test truncating strings in nested dictionary"""
        data = {
            "level1": {
                "level2": {
                    "short": "ok",
                    "long": "this is a very long string"
                }
            }
        }
        result = _truncate_dict_strings(data, 10)
        
        assert result["level1"]["level2"]["short"] == "ok"
        assert result["level1"]["level2"]["long"] == "this is..."

    def test_truncate_dict_strings_list_values(self):
        """Test truncating strings in lists within dictionary"""
        data = {
            "strings": ["short", "this is a very long string"],
            "mixed": [1, "long string here", {"nested": "another long string"}]
        }
        result = _truncate_dict_strings(data, 8)
        
        assert result["strings"][0] == "short"
        assert result["strings"][1] == "this ..."
        assert result["mixed"][0] == 1  # Non-string unchanged
        assert result["mixed"][1] == "long ..."
        assert result["mixed"][2]["nested"] == "anoth..."

    def test_truncate_dict_strings_non_string_values(self):
        """Test that non-string values are unchanged"""
        data = {
            "number": 42,
            "boolean": True,
            "none": None,
            "list": [1, 2, 3]
        }
        result = _truncate_dict_strings(data, 5)
        
        assert result["number"] == 42
        assert result["boolean"] is True
        assert result["none"] is None
        assert result["list"] == [1, 2, 3]

    def test_truncate_dict_strings_zero_max_len(self):
        """Test truncating with zero max length"""
        data = {"key": "value"}
        result = _truncate_dict_strings(data, 0)
        
        assert result == data  # Should return unchanged

    def test_truncate_dict_strings_negative_max_len(self):
        """Test truncating with negative max length"""
        data = {"key": "value"}
        result = _truncate_dict_strings(data, -5)
        
        assert result == data  # Should return unchanged

    def test_truncate_dict_strings_empty_dict(self):
        """Test truncating empty dictionary"""
        data = {}
        result = _truncate_dict_strings(data, 10)
        
        assert result == {}

    def test_truncate_dict_strings_empty_list(self):
        """Test truncating empty list"""
        data = []
        result = _truncate_dict_strings(data, 10)
        
        assert result == []

    def test_truncate_dict_strings_string_input(self):
        """Test truncating string input directly"""
        data = "this is a long string"
        result = _truncate_dict_strings(data, 10)
        
        assert result == "this is..."


class TestPrettyPrintEventHistory:
    """Tests for pretty_print_event_history function"""

    def test_pretty_print_empty_history(self):
        """Test pretty printing empty event history"""
        with patch('builtins.print') as mock_print:
            pretty_print_event_history([])
            
            # Should print "NO EVENTS RECORDED" message
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("NO EVENTS RECORDED" in call for call in print_calls)
            assert any("test failed before any events" in call for call in print_calls)

    def test_pretty_print_error_event(self):
        """Test pretty printing error event"""
        events = [{
            "error": {
                "code": "TIMEOUT",
                "message": "Request timed out after 30 seconds"
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Error Response" in call for call in print_calls)
            assert any("TIMEOUT" in call for call in print_calls)
            assert any("Request timed out" in call for call in print_calls)

    def test_pretty_print_task_status_update(self):
        """Test pretty printing task status update event"""
        events = [{
            "result": {
                "status": {
                    "state": "RUNNING",
                    "message": {
                        "parts": [
                            {"type": "text", "text": "Processing request..."}
                        ]
                    }
                },
                "final": False
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Task Status Update" in call for call in print_calls)
            assert any("RUNNING" in call for call in print_calls)
            assert any("Processing request" in call for call in print_calls)

    def test_pretty_print_final_task_response(self):
        """Test pretty printing final task response event"""
        events = [{
            "result": {
                "status": {
                    "state": "COMPLETED",
                    "message": {
                        "parts": [
                            {"type": "text", "text": "Task completed successfully"}
                        ]
                    }
                },
                "sessionId": "session-123",
                "artifacts": [
                    {"name": "output.txt", "version": 1}
                ]
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Final Task Response" in call for call in print_calls)
            assert any("COMPLETED" in call for call in print_calls)
            assert any("Task completed successfully" in call for call in print_calls)
            assert any("output.txt" in call for call in print_calls)

    def test_pretty_print_artifact_update(self):
        """Test pretty printing artifact update event"""
        events = [{
            "result": {
                "artifact": {
                    "name": "generated_report.pdf",
                    "parts": [
                        {"type": "file", "file": {"name": "report.pdf", "mimeType": "application/pdf"}}
                    ]
                }
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Task Artifact Update" in call for call in print_calls)
            assert any("generated_report.pdf" in call for call in print_calls)

    def test_pretty_print_unknown_event(self):
        """Test pretty printing unknown event type"""
        events = [{
            "result": {
                "unknown_field": "unknown_value"
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Unknown Event" in call for call in print_calls)

    def test_pretty_print_multiple_events(self):
        """Test pretty printing multiple events"""
        events = [
            {
                "result": {
                    "status": {
                        "state": "RUNNING",
                        "message": {"parts": [{"type": "text", "text": "Starting..."}]}
                    },
                    "final": False
                }
            },
            {
                "result": {
                    "status": {
                        "state": "COMPLETED",
                        "message": {"parts": [{"type": "text", "text": "Done!"}]}
                    },
                    "sessionId": "session-123"
                }
            }
        ]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Event 1" in call for call in print_calls)
            assert any("Event 2" in call for call in print_calls)
            assert any("Task Status Update" in call for call in print_calls)
            assert any("Final Task Response" in call for call in print_calls)

    def test_pretty_print_with_string_truncation(self):
        """Test pretty printing with string truncation"""
        long_message = "This is a very long message that should be truncated when the max_string_length is set to a small value"
        events = [{
            "result": {
                "status": {
                    "state": "RUNNING",
                    "message": {"parts": [{"type": "text", "text": long_message}]}
                },
                "final": False
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=20)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            # Should contain truncated version
            assert any("..." in call for call in print_calls)

    def test_pretty_print_raw_payload_truncation(self):
        """Test that raw payload is also truncated"""
        events = [{
            "result": {
                "very_long_field": "This is a very long value that should be truncated in the raw payload output"
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=20)
            
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            # Should print "Raw Payload:" and contain truncated JSON
            assert any("Raw Payload:" in call for call in print_calls)

    def test_pretty_print_default_max_string_length(self):
        """Test pretty printing with default max string length"""
        events = [{
            "result": {
                "status": {
                    "state": "RUNNING",
                    "message": {"parts": [{"type": "text", "text": "Test message"}]}
                },
                "final": False
            }
        }]
        
        with patch('builtins.print') as mock_print:
            # Call without max_string_length parameter (should use default 200)
            pretty_print_event_history(events)
            
            # Should not raise any exceptions
            assert mock_print.called

    def test_pretty_print_malformed_event(self):
        """Test pretty printing malformed event"""
        events = [
            {"malformed": "event"},
            {"result": {"payload": None}},  # This will cause the AttributeError
            {"result": None}
        ]
        
        with patch('builtins.print') as mock_print:
            with pytest.raises(AttributeError):
                pretty_print_event_history(events, max_string_length=100)
            
            # Verify that print was called before the exception
            assert mock_print.called

    def test_pretty_print_event_with_missing_message_parts(self):
        """Test pretty printing event with missing message parts"""
        events = [{
            "result": {
                "status": {
                    "state": "RUNNING",
                    "message": {}  # Missing "parts"
                },
                "final": False
            }
        }]
        
        with patch('builtins.print') as mock_print:
            pretty_print_event_history(events, max_string_length=100)
            
            # Should handle missing parts gracefully
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            assert any("Task Status Update" in call for call in print_calls)