"""
Unit tests for workflow utility functions.

Tests the parse_duration function for converting duration strings to seconds.
"""

import pytest
from solace_agent_mesh.workflow.utils import parse_duration


class TestParseDuration:
    """Tests for parse_duration function."""

    # --- Numeric input tests ---

    def test_integer_input_treated_as_seconds(self):
        """Integer input should be treated as seconds."""
        assert parse_duration(30) == 30.0

    def test_float_input_treated_as_seconds(self):
        """Float input should be treated as seconds."""
        assert parse_duration(30.5) == 30.5

    def test_zero_returns_zero(self):
        """Zero should return zero seconds."""
        assert parse_duration(0) == 0.0

    # --- String with seconds suffix ---

    def test_seconds_suffix_lowercase(self):
        """'30s' should return 30 seconds."""
        assert parse_duration("30s") == 30.0

    def test_seconds_suffix_with_decimal(self):
        """'1.5s' should return 1.5 seconds."""
        assert parse_duration("1.5s") == 1.5

    def test_seconds_suffix_uppercase(self):
        """'30S' should return 30 seconds (case insensitive)."""
        assert parse_duration("30S") == 30.0

    # --- String with minutes suffix ---

    def test_minutes_suffix(self):
        """'5m' should return 300 seconds (5 * 60)."""
        assert parse_duration("5m") == 300.0

    def test_minutes_suffix_with_decimal(self):
        """'1.5m' should return 90 seconds."""
        assert parse_duration("1.5m") == 90.0

    def test_one_minute(self):
        """'1m' should return 60 seconds."""
        assert parse_duration("1m") == 60.0

    # --- String with hours suffix ---

    def test_hours_suffix(self):
        """'2h' should return 7200 seconds (2 * 3600)."""
        assert parse_duration("2h") == 7200.0

    def test_one_hour(self):
        """'1h' should return 3600 seconds."""
        assert parse_duration("1h") == 3600.0

    def test_hours_with_decimal(self):
        """'0.5h' should return 1800 seconds (half hour)."""
        assert parse_duration("0.5h") == 1800.0

    # --- String with days suffix ---

    def test_days_suffix(self):
        """'1d' should return 86400 seconds."""
        assert parse_duration("1d") == 86400.0

    def test_days_with_decimal(self):
        """'0.5d' should return 43200 seconds (half day)."""
        assert parse_duration("0.5d") == 43200.0

    # --- String without suffix (defaults to seconds) ---

    def test_string_number_without_suffix(self):
        """'30' (string without suffix) should default to seconds."""
        assert parse_duration("30") == 30.0

    def test_string_decimal_without_suffix(self):
        """'30.5' (string without suffix) should default to seconds."""
        assert parse_duration("30.5") == 30.5

    # --- Whitespace handling ---

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed."""
        assert parse_duration("  30s  ") == 30.0

    def test_whitespace_between_number_and_suffix(self):
        """Whitespace between number and suffix should work."""
        assert parse_duration("30 s") == 30.0

    # --- Invalid input tests ---

    def test_invalid_format_raises_value_error(self):
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_duration("invalid")
        assert "Invalid duration format" in str(exc_info.value)

    def test_negative_number_raises_value_error(self):
        """Negative numbers should raise ValueError (regex doesn't match)."""
        with pytest.raises(ValueError) as exc_info:
            parse_duration("-30s")
        assert "Invalid duration format" in str(exc_info.value)

    def test_invalid_suffix_raises_value_error(self):
        """Invalid suffix should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_duration("30x")
        assert "Invalid duration format" in str(exc_info.value)

    def test_empty_string_raises_value_error(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_duration("")
        assert "Invalid duration format" in str(exc_info.value)

    def test_only_suffix_raises_value_error(self):
        """Just a suffix without number should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_duration("s")
        assert "Invalid duration format" in str(exc_info.value)
