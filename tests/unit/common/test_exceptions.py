"""
Unit tests for common/exceptions.py
Tests custom exceptions for Solace Agent Mesh.
"""

import pytest
from solace_agent_mesh.common.exceptions import MessageSizeExceededError


class TestMessageSizeExceededError:
    """Test MessageSizeExceededError exception."""

    def test_init_with_default_message(self):
        """Test initialization with default error message."""
        actual_size = 1500
        max_size = 1000
        
        error = MessageSizeExceededError(actual_size, max_size)
        
        assert error.actual_size == actual_size
        assert error.max_size == max_size
        assert "1500 bytes" in str(error)
        assert "1000 bytes" in str(error)
        assert "exceeds maximum limit" in str(error)

    def test_init_with_custom_message(self):
        """Test initialization with custom error message."""
        actual_size = 2000
        max_size = 1000
        custom_message = "Custom error: message too large"
        
        error = MessageSizeExceededError(actual_size, max_size, custom_message)
        
        assert error.actual_size == actual_size
        assert error.max_size == max_size
        assert str(error) == custom_message

    def test_exception_can_be_raised(self):
        """Test that the exception can be raised and caught."""
        with pytest.raises(MessageSizeExceededError) as exc_info:
            raise MessageSizeExceededError(1500, 1000)
        
        assert exc_info.value.actual_size == 1500
        assert exc_info.value.max_size == 1000

    def test_exception_inherits_from_exception(self):
        """Test that MessageSizeExceededError inherits from Exception."""
        error = MessageSizeExceededError(1500, 1000)
        assert isinstance(error, Exception)

    def test_exception_with_zero_sizes(self):
        """Test exception with zero sizes."""
        error = MessageSizeExceededError(0, 0)
        assert error.actual_size == 0
        assert error.max_size == 0
        assert "0 bytes" in str(error)

    def test_exception_with_large_sizes(self):
        """Test exception with very large sizes."""
        actual_size = 10_000_000  # 10 MB
        max_size = 5_000_000      # 5 MB
        
        error = MessageSizeExceededError(actual_size, max_size)
        
        assert error.actual_size == actual_size
        assert error.max_size == max_size
        assert "10000000" in str(error)
        assert "5000000" in str(error)

    def test_exception_with_negative_sizes(self):
        """Test exception with negative sizes (edge case)."""
        error = MessageSizeExceededError(-100, 1000)
        assert error.actual_size == -100
        assert error.max_size == 1000

    def test_exception_message_format(self):
        """Test the default message format is correct."""
        error = MessageSizeExceededError(1234, 1000)
        expected_message = (
            "Message size 1234 bytes exceeds maximum limit of 1000 bytes"
        )
        assert str(error) == expected_message
