#!/usr/bin/env python3
"""
Unit tests for the SamAgentComponent class
"""

import pytest
from unittest.mock import Mock

from src.solace_agent_mesh.agent.sac.component import SamAgentComponent


class TestExtractToolOrigin:
    """Test cases for the _extract_tool_origin static method in SamAgentComponent."""

    def test_extract_tool_origin_with_direct_origin(self):
        """Test _extract_tool_origin when tool has a direct origin attribute."""
        tool = Mock()
        tool.origin = "direct_origin"

        result = SamAgentComponent._extract_tool_origin(tool)
        assert result == "direct_origin"

    def test_extract_tool_origin_with_func_origin(self):
        """Test _extract_tool_origin when tool has a func with origin attribute."""

        tool = Mock()
        tool.origin = None
        tool.func = Mock()
        tool.func.origin = "func_origin"

        result = SamAgentComponent._extract_tool_origin(tool)
        assert result == "func_origin"

    def test_extract_tool_origin_with_getattr_fallback(self):
        """Test _extract_tool_origin when using getattr fallback."""

        class CustomTool:
            pass

        custom_tool = CustomTool()
        setattr(custom_tool, "origin", "getattr_origin")

        result = SamAgentComponent._extract_tool_origin(custom_tool)
        assert result == "getattr_origin"

    def test_extract_tool_origin_unknown_fallback(self):
        """Test _extract_tool_origin when no origin is found."""
        tool = Mock()
        tool.origin = None
        tool.func = None

        if hasattr(tool, "origin"):
            delattr(tool, "origin")

        result = SamAgentComponent._extract_tool_origin(tool)
        assert result == "unknown"
