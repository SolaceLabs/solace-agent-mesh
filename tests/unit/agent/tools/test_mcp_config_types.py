"""Tests for MCP tool configuration types, specifically tool_name_prefix."""
import pytest
from pydantic import ValidationError, TypeAdapter
from solace_agent_mesh.agent.tools.tool_config_types import McpToolConfig, AnyToolConfig


class TestMcpToolConfigPrefix:
    """Test McpToolConfig model validation for tool_name_prefix feature."""

    def test_mcp_config_with_tool_name_prefix(self):
        """Test valid config with tool_name_prefix."""
        config = {
            "tool_type": "mcp",
            "connection_params": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"]
            },
            "tool_name_prefix": "fs1"
        }
        result = McpToolConfig.model_validate(config)
        assert result.tool_type == "mcp"
        assert result.tool_name_prefix == "fs1"
        assert result.connection_params["type"] == "stdio"

    def test_mcp_config_without_tool_name_prefix(self):
        """Test valid config without tool_name_prefix (backward compatibility)."""
        config = {
            "tool_type": "mcp",
            "connection_params": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem"]
            }
        }
        result = McpToolConfig.model_validate(config)
        assert result.tool_type == "mcp"
        assert result.tool_name_prefix is None

    def test_mcp_config_with_none_prefix(self):
        """Test config with explicit None for tool_name_prefix."""
        config = {
            "tool_type": "mcp",
            "connection_params": {
                "type": "stdio",
                "command": "test"
            },
            "tool_name_prefix": None
        }
        result = McpToolConfig.model_validate(config)
        assert result.tool_name_prefix is None

    def test_mcp_config_prefix_with_other_fields(self):
        """Test tool_name_prefix works with other optional fields."""
        config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": "custom",
            "tool_name": "read_file",
            "environment_variables": {"VAR": "value"}
        }
        result = McpToolConfig.model_validate(config)
        assert result.tool_name_prefix == "custom"
        assert result.tool_name == "read_file"
        assert result.environment_variables == {"VAR": "value"}

    def test_mcp_config_prefix_invalid_type(self):
        """Test that non-string tool_name_prefix fails validation."""
        config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": 123  # Invalid: should be string
        }
        with pytest.raises(ValidationError):
            McpToolConfig.model_validate(config)

    def test_mcp_config_prefix_empty_string(self):
        """Test that empty string prefix is accepted."""
        config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": ""
        }
        result = McpToolConfig.model_validate(config)
        assert result.tool_name_prefix == ""

    def test_anytools_config_includes_mcp_with_prefix(self):
        """Test that AnyToolConfig union includes McpToolConfig with prefix."""
        config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": "test_prefix"
        }
        adapter = TypeAdapter(AnyToolConfig)
        result = adapter.validate_python(config)
        assert isinstance(result, McpToolConfig)
        assert result.tool_name_prefix == "test_prefix"

    def test_mcp_config_multiple_instances_different_prefixes(self):
        """Test creating multiple MCP configs with different prefixes."""
        config1 = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test1"},
            "tool_name_prefix": "fs1"
        }
        config2 = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test2"},
            "tool_name_prefix": "fs2"
        }

        result1 = McpToolConfig.model_validate(config1)
        result2 = McpToolConfig.model_validate(config2)

        assert result1.tool_name_prefix == "fs1"
        assert result2.tool_name_prefix == "fs2"
        assert result1.tool_name_prefix != result2.tool_name_prefix
