"""
Unit tests for WebUIBackendComponent._init_feature_checker().

_init_feature_checker() is a thin log-only method. Community flags, enterprise
flags, and provider registration are all handled by initialize() (called from
SamComponentBase.__init__). These tests verify the method behaves correctly
after initialize() has already run, as it would in production.
"""

from unittest.mock import MagicMock

import pytest

from solace_agent_mesh.common.features.core import (
    _reset_for_testing,
    get_registry,
    initialize,
)
from solace_agent_mesh.gateway.http_sse.component import WebUIBackendComponent


@pytest.fixture(autouse=True)
def _reset_openfeature():
    _reset_for_testing()
    yield
    _reset_for_testing()


def _call_init_feature_checker():
    """Invoke _init_feature_checker on a minimal mock component instance."""
    mock_self = MagicMock()
    mock_self.log_identifier = "[test]"
    WebUIBackendComponent._init_feature_checker(mock_self)
    return mock_self


class TestInitFeatureChecker:
    """_init_feature_checker() logs the flag count without errors."""

    def test_logs_flag_count_after_initialize(self):
        initialize()
        _call_init_feature_checker()
        assert len(get_registry().all()) > 0

    def test_does_not_raise_when_called_before_explicit_initialize(self):
        # initialize() is idempotent; calling _init_feature_checker without
        # prior explicit init should trigger lazy init and not raise.
        _call_init_feature_checker()
        assert len(get_registry().all()) > 0
