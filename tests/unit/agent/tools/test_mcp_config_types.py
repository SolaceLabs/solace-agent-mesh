"""Tests for MCP tool configuration types, specifically tool_name_prefix."""
import pytest
from pydantic import ValidationError
from solace_agent_mesh.agent.tools.tool_config_types import McpToolConfig


class TestMcpToolConfigPrefix:
    """Test McpToolConfig model validation for tool_name_prefix feature."""

    def test_mcp_config_prefix_valid_cases(self):
        """Test tool_name_prefix with valid values and backward compatibility."""
        # With prefix
        config_with_prefix = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]},
            "tool_name_prefix": "fs1"
        }
        result = McpToolConfig.model_validate(config_with_prefix)
        assert result.tool_name_prefix == "fs1"

        # Without prefix (backward compatibility)
        config_without_prefix = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"}
        }
        result = McpToolConfig.model_validate(config_without_prefix)
        assert result.tool_name_prefix is None

        # Explicit None
        config_none_prefix = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": None
        }
        result = McpToolConfig.model_validate(config_none_prefix)
        assert result.tool_name_prefix is None

    def test_mcp_config_prefix_invalid_type(self):
        """Test that non-string tool_name_prefix fails validation."""
        config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": 123
        }
        with pytest.raises(ValidationError):
            McpToolConfig.model_validate(config)