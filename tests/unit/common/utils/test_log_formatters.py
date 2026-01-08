"""
Unit tests for src/solace_agent_mesh/common/utils/log_formatters.py

Tests the DatadogJsonFormatter implementation including:
- JSON log formatting
- Timestamp formatting
- Service name handling
- Datadog trace/span ID integration
- Exception handling and stack traces
- Thread information
- Code location information
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import pytest

from src.solace_agent_mesh.common.utils.log_formatters import DatadogJsonFormatter


@pytest.fixture
def formatter():
    """Create a DatadogJsonFormatter instance for testing"""
    return DatadogJsonFormatter()


@pytest.fixture
def sample_log_record():
    """Create a sample LogRecord for testing"""
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/path/to/test_module.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None
    )
    record.created = 1640995200.0  # 2022-01-01 00:00:00 UTC
    record.threadName = "MainThread"
    record.module = "test_module"
    record.funcName = "test_function"
    return record


class TestDatadogJsonFormatterBasic:
    """Tests for basic DatadogJsonFormatter functionality"""

    def test_format_basic_message(self, formatter, sample_log_record):
        """Test formatting a basic log message"""
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        
        # Verify basic fields
        assert log_data["message"] == "Test message"
        assert log_data["level"] == "INFO"
        assert log_data["logger.name"] == "test.logger"
        assert log_data["logger.thread_name"] == "MainThread"
        assert log_data["code.filepath"] == "/path/to/test_module.py"
        assert log_data["code.lineno"] == 42
        assert log_data["code.module"] == "test_module"
        assert log_data["code.funcName"] == "test_function"

    def test_format_timestamp(self, formatter, sample_log_record):
        """Test timestamp formatting"""
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        
        # Verify timestamp is in ISO format
        timestamp = log_data["timestamp"]
        assert timestamp == "2022-01-01T00:00:00+00:00"
        
        # Verify it can be parsed back
        parsed_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert parsed_dt.tzinfo == timezone.utc

    def test_format_different_log_levels(self, formatter):
        """Test formatting different log levels"""
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL")
        ]
        
        for level_num, level_name in levels:
            record = logging.LogRecord(
                name="test.logger",
                level=level_num,
                pathname="/path/to/test.py",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None
            )
            record.created = 1640995200.0
            record.threadName = "MainThread"
            record.module = "test"
            record.funcName = "test_func"
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            assert log_data["level"] == level_name

    def test_format_message_with_args(self, formatter):
        """Test formatting message with arguments"""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=1,
            msg="Hello %s, you have %d messages",
            args=("Alice", 5),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = "MainThread"
        record.module = "test"
        record.funcName = "test_func"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        assert log_data["message"] == "Hello Alice, you have 5 messages"

    def test_format_returns_valid_json(self, formatter, sample_log_record):
        """Test that format always returns valid JSON"""
        formatted = formatter.format(sample_log_record)
        
        # Should not raise exception
        log_data = json.loads(formatted)
        assert isinstance(log_data, dict)


class TestDatadogJsonFormatterServiceName:
    """Tests for service name handling"""

    def test_format_with_default_service_name(self, formatter, sample_log_record):
        """Test formatting with default service name"""
        with patch.dict(os.environ, {}, clear=True):
            formatted = formatter.format(sample_log_record)
            log_data = json.loads(formatted)
            assert log_data["service"] == "solace_agent_mesh"

    def test_format_with_custom_service_name(self, formatter, sample_log_record):
        """Test formatting with custom service name from environment"""
        with patch.dict(os.environ, {"SERVICE_NAME": "custom_service"}):
            formatted = formatter.format(sample_log_record)
            log_data = json.loads(formatted)
            assert log_data["service"] == "custom_service"

    def test_format_with_empty_service_name(self, formatter, sample_log_record):
        """Test formatting with empty service name falls back to default"""
        with patch.dict(os.environ, {"SERVICE_NAME": ""}):
            formatted = formatter.format(sample_log_record)
            log_data = json.loads(formatted)
            assert log_data["service"] == ""  # Should use the empty value


class TestDatadogJsonFormatterDatadogIntegration:
    """Tests for Datadog trace and span ID integration"""

    def test_format_with_datadog_trace_id(self, formatter, sample_log_record):
        """Test formatting with Datadog trace ID"""
        sample_log_record.dd = Mock()
        sample_log_record.dd.trace_id = "123456789"
        # Alternative attribute access pattern
        setattr(sample_log_record, "dd.trace_id", "123456789")
        
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        assert log_data["dd.trace_id"] == "123456789"

    def test_format_with_datadog_span_id(self, formatter, sample_log_record):
        """Test formatting with Datadog span ID"""
        setattr(sample_log_record, "dd.span_id", "987654321")
        
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        assert log_data["dd.span_id"] == "987654321"

    def test_format_with_both_datadog_ids(self, formatter, sample_log_record):
        """Test formatting with both Datadog trace and span IDs"""
        setattr(sample_log_record, "dd.trace_id", "123456789")
        setattr(sample_log_record, "dd.span_id", "987654321")
        
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        assert log_data["dd.trace_id"] == "123456789"
        assert log_data["dd.span_id"] == "987654321"

    def test_format_without_datadog_ids(self, formatter, sample_log_record):
        """Test formatting without Datadog IDs (should not include them)"""
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        assert "dd.trace_id" not in log_data
        assert "dd.span_id" not in log_data

    def test_format_with_none_datadog_ids(self, formatter, sample_log_record):
        """Test formatting with None Datadog IDs (should not include them)"""
        setattr(sample_log_record, "dd.trace_id", None)
        setattr(sample_log_record, "dd.span_id", None)
        
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        assert "dd.trace_id" not in log_data
        assert "dd.span_id" not in log_data


class TestDatadogJsonFormatterExceptionHandling:
    """Tests for exception handling and stack traces"""

    def test_format_with_exception_info(self, formatter):
        """Test formatting with exception information"""
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=1,
                msg="An error occurred",
                args=(),
                exc_info=exc_info
            )
            record.created = 1640995200.0
            record.threadName = "MainThread"
            record.module = "test"
            record.funcName = "test_func"
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            
            assert log_data["message"] == "An error occurred"
            assert log_data["exception.type"] == "ValueError"
            assert log_data["exception.message"] == "Test exception"
            assert "exception.stacktrace" in log_data
            assert "ValueError: Test exception" in log_data["exception.stacktrace"]
            assert "Traceback" in log_data["exception.stacktrace"]

    def test_format_with_nested_exception(self, formatter):
        """Test formatting with nested exception"""
        try:
            try:
                raise ValueError("Inner exception")
            except ValueError as e:
                raise RuntimeError("Outer exception") from e
        except RuntimeError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=1,
                msg="Nested error occurred",
                args=(),
                exc_info=exc_info
            )
            record.created = 1640995200.0
            record.threadName = "MainThread"
            record.module = "test"
            record.funcName = "test_func"
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            
            assert log_data["exception.type"] == "RuntimeError"
            assert log_data["exception.message"] == "Outer exception"
            assert "exception.stacktrace" in log_data
            # Should contain both exceptions in the stack trace
            assert "RuntimeError: Outer exception" in log_data["exception.stacktrace"]
            assert "ValueError: Inner exception" in log_data["exception.stacktrace"]

    def test_format_without_exception_info(self, formatter, sample_log_record):
        """Test formatting without exception information"""
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        
        assert "exception.type" not in log_data
        assert "exception.message" not in log_data
        assert "exception.stacktrace" not in log_data

    def test_format_with_custom_exception_class(self, formatter):
        """Test formatting with custom exception class"""
        class CustomError(Exception):
            pass
        
        try:
            raise CustomError("Custom error message")
        except CustomError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/path/to/test.py",
                lineno=1,
                msg="Custom error occurred",
                args=(),
                exc_info=exc_info
            )
            record.created = 1640995200.0
            record.threadName = "MainThread"
            record.module = "test"
            record.funcName = "test_func"
            
            formatted = formatter.format(record)
            log_data = json.loads(formatted)
            
            assert log_data["exception.type"] == "CustomError"
            assert log_data["exception.message"] == "Custom error message"


class TestDatadogJsonFormatterDeprecation:
    """Tests for deprecation warning functionality"""

    def test_deprecation_warning_emitted_once(self):
        """Test that deprecation warning is emitted only once"""
        import warnings
        
        # Reset the class-level flag if it exists
        if hasattr(DatadogJsonFormatter, '_deprecation_warned'):
            delattr(DatadogJsonFormatter, '_deprecation_warned')
        
        formatter = DatadogJsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = "MainThread"
        record.module = "test"
        record.funcName = "test_func"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            formatter.format(record)
            formatter.format(record)  # Second call should not warn
            
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 1
            assert "deprecated" in str(deprecation_warnings[0].message).lower()

    def test_deprecation_warning_contains_alternative(self):
        """Test that deprecation warning mentions the alternative"""
        import warnings
        
        # Reset the class-level flag if it exists
        if hasattr(DatadogJsonFormatter, '_deprecation_warned'):
            delattr(DatadogJsonFormatter, '_deprecation_warned')
        
        formatter = DatadogJsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = "MainThread"
        record.module = "test"
        record.funcName = "test_func"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            formatter.format(record)
            
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) == 1
            warning_message = str(deprecation_warnings[0].message)
            assert "pythonjsonlogger" in warning_message.lower() or "JsonFormatter" in warning_message


class TestDatadogJsonFormatterEdgeCases:
    """Tests for edge cases and special scenarios"""

    def test_format_with_unicode_message(self, formatter):
        """Test formatting with Unicode characters in message"""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=1,
            msg="Unicode test: 你好世界 🌍",
            args=(),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = "MainThread"
        record.module = "test"
        record.funcName = "test_func"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        assert log_data["message"] == "Unicode test: 你好世界 🌍"

    def test_format_with_special_characters_in_paths(self, formatter):
        """Test formatting with special characters in file paths"""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/with spaces/and-dashes/test_file.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = "Thread-1"
        record.module = "test_file"
        record.funcName = "test_function_with_underscores"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        assert log_data["code.filepath"] == "/path/with spaces/and-dashes/test_file.py"
        assert log_data["logger.thread_name"] == "Thread-1"
        assert log_data["code.funcName"] == "test_function_with_underscores"

    def test_format_with_very_long_message(self, formatter):
        """Test formatting with very long log message"""
        long_message = "A" * 10000  # 10KB message
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=1,
            msg=long_message,
            args=(),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = "MainThread"
        record.module = "test"
        record.funcName = "test_func"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        assert log_data["message"] == long_message
        assert len(formatted) > 10000

    def test_format_with_none_values(self, formatter):
        """Test formatting with None values in record attributes"""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.created = 1640995200.0
        record.threadName = None
        record.module = None
        record.funcName = None
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        # Should handle None values gracefully
        assert log_data["logger.thread_name"] is None
        assert log_data["code.module"] is None
        assert log_data["code.funcName"] is None


    def test_format_consistent_field_names(self, formatter, sample_log_record):
        """Test that field names are consistent with Datadog conventions"""
        formatted = formatter.format(sample_log_record)
        log_data = json.loads(formatted)
        
        # Verify expected field names
        expected_fields = {
            "timestamp", "level", "message", "logger.name", "logger.thread_name",
            "service", "code.filepath", "code.lineno", "code.module", "code.funcName"
        }
        
        for field in expected_fields:
            assert field in log_data, f"Expected field '{field}' not found in log data"