"""
Unit tests for src/solace_agent_mesh/common/utils/initializer.py

Tests the initialize function with basic functionality only.
"""

import pytest

from src.solace_agent_mesh.common.utils.initializer import initialize


class TestInitializeBasicFunctionality:
    """Test basic initialization functionality"""

    def test_initialize_runs_without_error(self):
        """Test that initialize runs without raising exceptions"""
        # Should not raise any exceptions
        try:
            initialize()
            assert True  # If we get here, no exception was raised
        except Exception as e:
            pytest.fail(f"initialize() raised an exception: {e}")

    def test_initialize_multiple_calls(self):
        """Test that initialize can be called multiple times without error"""
        # Should not raise any exceptions even when called multiple times
        try:
            initialize()
            initialize()
            initialize()
            assert True  # If we get here, no exception was raised
        except Exception as e:
            pytest.fail(f"Multiple initialize() calls raised an exception: {e}")
