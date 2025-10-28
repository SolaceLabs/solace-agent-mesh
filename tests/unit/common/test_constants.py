"""
Unit tests for common/constants.py
Tests common constants used across the system.
"""

from solace_agent_mesh.common.constants import (
    DEFAULT_COMMUNICATION_TIMEOUT,
    HEALTH_CHECK_TTL_SECONDS,
    HEALTH_CHECK_INTERVAL_SECONDS,
    TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY,
    TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH,
)


class TestConstants:
    """Test that constants have expected values and types."""

    def test_default_communication_timeout(self):
        """Test DEFAULT_COMMUNICATION_TIMEOUT constant."""
        assert DEFAULT_COMMUNICATION_TIMEOUT == 600
        assert isinstance(DEFAULT_COMMUNICATION_TIMEOUT, int)
        assert DEFAULT_COMMUNICATION_TIMEOUT > 0

    def test_health_check_ttl_seconds(self):
        """Test HEALTH_CHECK_TTL_SECONDS constant."""
        assert HEALTH_CHECK_TTL_SECONDS == 60
        assert isinstance(HEALTH_CHECK_TTL_SECONDS, int)
        assert HEALTH_CHECK_TTL_SECONDS > 0

    def test_health_check_interval_seconds(self):
        """Test HEALTH_CHECK_INTERVAL_SECONDS constant."""
        assert HEALTH_CHECK_INTERVAL_SECONDS == 10
        assert isinstance(HEALTH_CHECK_INTERVAL_SECONDS, int)
        assert HEALTH_CHECK_INTERVAL_SECONDS > 0

    def test_text_artifact_context_max_length_capacity(self):
        """Test TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY constant."""
        assert TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY == 200000
        assert isinstance(TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY, int)
        assert TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY > 0

    def test_text_artifact_context_default_length(self):
        """Test TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH constant."""
        assert TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH == 100000
        assert isinstance(TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH, int)
        assert TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH > 0

    def test_health_check_interval_less_than_ttl(self):
        """Test that health check interval is less than TTL."""
        assert HEALTH_CHECK_INTERVAL_SECONDS < HEALTH_CHECK_TTL_SECONDS

    def test_default_length_less_than_max_capacity(self):
        """Test that default length is less than max capacity."""
        assert TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH < TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY

    def test_timeout_values_are_reasonable(self):
        """Test that timeout values are within reasonable ranges."""
        # Communication timeout should be at least 1 minute
        assert DEFAULT_COMMUNICATION_TIMEOUT >= 60
        
        # Health check TTL should be at least 10 seconds
        assert HEALTH_CHECK_TTL_SECONDS >= 10
        
        # Health check interval should be at least 1 second
        assert HEALTH_CHECK_INTERVAL_SECONDS >= 1

    def test_artifact_length_values_are_reasonable(self):
        """Test that artifact length values are within reasonable ranges."""
        # Max capacity should be at least 100KB
        assert TEXT_ARTIFACT_CONTEXT_MAX_LENGTH_CAPACITY >= 100000
        
        # Default length should be at least 50KB
        assert TEXT_ARTIFACT_CONTEXT_DEFAULT_LENGTH >= 50000