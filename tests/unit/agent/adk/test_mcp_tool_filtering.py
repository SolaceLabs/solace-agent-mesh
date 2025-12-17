"""Tests for MCP tool filtering in McpToolConfig and setup.py."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pydantic import ValidationError

from solace_agent_mesh.agent.tools.tool_config_types import McpToolConfig


class TestMcpToolConfigFiltering:
    """Test McpToolConfig filtering field validation."""

    def test_no_filter_specified(self):
        """Test that config with no filter is valid."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio", "command": "npx"}
        )
        assert config.tool_name is None
        assert config.allow_list is None
        assert config.deny_list is None

    def test_tool_name_only(self):
        """Test that config with only tool_name is valid."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio", "command": "npx"},
            tool_name="read_file"
        )
        assert config.tool_name == "read_file"
        assert config.allow_list is None
        assert config.deny_list is None

    def test_allow_list_only(self):
        """Test that config with only allow_list is valid."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio", "command": "npx"},
            allow_list=["read_file", "write_file"]
        )
        assert config.tool_name is None
        assert config.allow_list == ["read_file", "write_file"]
        assert config.deny_list is None

    def test_deny_list_only(self):
        """Test that config with only deny_list is valid."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio", "command": "npx"},
            deny_list=["delete_file", "move_file"]
        )
        assert config.tool_name is None
        assert config.allow_list is None
        assert config.deny_list == ["delete_file", "move_file"]

    def test_tool_name_and_allow_list_mutually_exclusive(self):
        """Test that tool_name and allow_list cannot both be specified."""
        with pytest.raises(ValidationError) as exc_info:
            McpToolConfig(
                tool_type="mcp",
                connection_params={"type": "stdio", "command": "npx"},
                tool_name="read_file",
                allow_list=["write_file"]
            )
        assert "mutually exclusive" in str(exc_info.value).lower()

    def test_tool_name_and_deny_list_mutually_exclusive(self):
        """Test that tool_name and deny_list cannot both be specified."""
        with pytest.raises(ValidationError) as exc_info:
            McpToolConfig(
                tool_type="mcp",
                connection_params={"type": "stdio", "command": "npx"},
                tool_name="read_file",
                deny_list=["delete_file"]
            )
        assert "mutually exclusive" in str(exc_info.value).lower()

    def test_allow_list_and_deny_list_mutually_exclusive(self):
        """Test that allow_list and deny_list cannot both be specified."""
        with pytest.raises(ValidationError) as exc_info:
            McpToolConfig(
                tool_type="mcp",
                connection_params={"type": "stdio", "command": "npx"},
                allow_list=["read_file"],
                deny_list=["delete_file"]
            )
        assert "mutually exclusive" in str(exc_info.value).lower()

    def test_all_three_filters_mutually_exclusive(self):
        """Test that all three filters cannot be specified together."""
        with pytest.raises(ValidationError) as exc_info:
            McpToolConfig(
                tool_type="mcp",
                connection_params={"type": "stdio", "command": "npx"},
                tool_name="read_file",
                allow_list=["write_file"],
                deny_list=["delete_file"]
            )
        assert "mutually exclusive" in str(exc_info.value).lower()

    def test_empty_allow_list_is_valid(self):
        """Test that empty allow_list is valid (though probably not useful)."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio", "command": "npx"},
            allow_list=[]
        )
        assert config.allow_list == []

    def test_empty_deny_list_is_valid(self):
        """Test that empty deny_list is valid (though probably not useful)."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio", "command": "npx"},
            deny_list=[]
        )
        assert config.deny_list == []


class TestMcpToolFilterLogic:
    """Test the filtering logic that would be applied in _load_mcp_tool."""

    def _create_filter(self, config: McpToolConfig):
        """Simulate the filtering logic from setup.py."""
        tool_filter = None
        filter_description = "none (all tools)"

        if config.tool_name:
            tool_filter = [config.tool_name]
            filter_description = f"tool_name='{config.tool_name}'"
        elif config.allow_list:
            tool_filter = config.allow_list
            filter_description = f"allow_list={config.allow_list}"
        elif config.deny_list:
            deny_set = set(config.deny_list)
            tool_filter = lambda tool, ctx=None, _deny=deny_set: tool.name not in _deny
            filter_description = f"deny_list={config.deny_list}"

        return tool_filter, filter_description

    def test_no_filter_returns_none(self):
        """Test that no filter specified returns None."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"}
        )
        tool_filter, desc = self._create_filter(config)
        assert tool_filter is None
        assert desc == "none (all tools)"

    def test_tool_name_creates_single_item_list(self):
        """Test that tool_name creates a list with single item."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"},
            tool_name="read_file"
        )
        tool_filter, desc = self._create_filter(config)
        assert tool_filter == ["read_file"]
        assert "tool_name='read_file'" in desc

    def test_allow_list_passed_directly(self):
        """Test that allow_list is passed directly as list."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"},
            allow_list=["read_file", "write_file", "list_dir"]
        )
        tool_filter, desc = self._create_filter(config)
        assert tool_filter == ["read_file", "write_file", "list_dir"]
        assert "allow_list=" in desc

    def test_deny_list_creates_predicate(self):
        """Test that deny_list creates a callable predicate."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"},
            deny_list=["delete_file", "move_file"]
        )
        tool_filter, desc = self._create_filter(config)
        assert callable(tool_filter)
        assert "deny_list=" in desc

    def test_deny_list_predicate_allows_non_denied_tools(self):
        """Test that deny_list predicate returns True for allowed tools."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"},
            deny_list=["delete_file", "move_file"]
        )
        tool_filter, _ = self._create_filter(config)

        # Mock tool objects
        read_tool = Mock(name="read_file")
        read_tool.name = "read_file"
        write_tool = Mock(name="write_file")
        write_tool.name = "write_file"

        assert tool_filter(read_tool) is True
        assert tool_filter(write_tool) is True

    def test_deny_list_predicate_denies_specified_tools(self):
        """Test that deny_list predicate returns False for denied tools."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"},
            deny_list=["delete_file", "move_file"]
        )
        tool_filter, _ = self._create_filter(config)

        # Mock tool objects
        delete_tool = Mock(name="delete_file")
        delete_tool.name = "delete_file"
        move_tool = Mock(name="move_file")
        move_tool.name = "move_file"

        assert tool_filter(delete_tool) is False
        assert tool_filter(move_tool) is False

    def test_deny_list_predicate_with_context_parameter(self):
        """Test that deny_list predicate works with optional context parameter."""
        config = McpToolConfig(
            tool_type="mcp",
            connection_params={"type": "stdio"},
            deny_list=["delete_file"]
        )
        tool_filter, _ = self._create_filter(config)

        read_tool = Mock(name="read_file")
        read_tool.name = "read_file"
        delete_tool = Mock(name="delete_file")
        delete_tool.name = "delete_file"

        # ADK may pass a context parameter
        mock_context = Mock()
        assert tool_filter(read_tool, mock_context) is True
        assert tool_filter(delete_tool, mock_context) is False
