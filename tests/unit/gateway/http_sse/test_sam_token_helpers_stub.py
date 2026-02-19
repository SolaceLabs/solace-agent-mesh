"""
Tests for sam_token_helpers stubs in base repository.

These tests verify that the stub functions work correctly when
enterprise package is not available.
"""

import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.utils.sam_token_helpers import (
    is_sam_token_enabled,
)

# Check if enterprise package is available
try:
    import solace_agent_mesh_enterprise
    ENTERPRISE_AVAILABLE = True
except ImportError:
    ENTERPRISE_AVAILABLE = False


@pytest.mark.skipif(ENTERPRISE_AVAILABLE, reason="This test is for stub behavior when enterprise is not available")
def test_is_sam_token_enabled_returns_false():
    """Test that stub always returns False."""
    component = MagicMock()
    assert is_sam_token_enabled(component) is False
