"""Tests for MCP tool filtering in McpToolConfig and setup.py."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pydantic import ValidationError

from solace_agent_mesh.agent.tools.tool_config_types import McpToolConfig
from solace_agent_mesh.agent.adk.setup import _load_mcp_tool


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


@pytest.fixture
def mock_component():
    """Mock SamAgentComponent for testing."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    return component


class TestLoadMcpToolFiltering:
    """Test that _load_mcp_tool correctly handles filtering options."""

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset')
    async def test_load_mcp_tool_no_filter(self, mock_toolset_class, mock_component):
        """Test that _load_mcp_tool works with no filter specified."""
        mock_toolset_instance = Mock()
        mock_toolset_class.return_value = mock_toolset_instance

        tool_config = {
            "tool_type": "mcp",
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        result = await _load_mcp_tool(mock_component, tool_config)

        # Verify result structure
        assert len(result) == 3  # tools, builtins, cleanups
        assert len(result[0]) == 1
        assert result[0][0] is mock_toolset_instance
        assert result[0][0].origin == "mcp"

        # Verify toolset was created with tool_filter=None
        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["tool_filter"] is None

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset')
    async def test_load_mcp_tool_with_tool_name(self, mock_toolset_class, mock_component):
        """Test that _load_mcp_tool creates list filter for tool_name."""
        mock_toolset_instance = Mock()
        mock_toolset_class.return_value = mock_toolset_instance

        tool_config = {
            "tool_type": "mcp",
            "tool_name": "read_file",
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        result = await _load_mcp_tool(mock_component, tool_config)

        # Verify toolset was created with tool_filter as single-item list
        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["tool_filter"] == ["read_file"]

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset')
    async def test_load_mcp_tool_with_allow_list(self, mock_toolset_class, mock_component):
        """Test that _load_mcp_tool passes allow_list directly as tool_filter."""
        mock_toolset_instance = Mock()
        mock_toolset_class.return_value = mock_toolset_instance

        tool_config = {
            "tool_type": "mcp",
            "allow_list": ["read_file", "write_file", "list_directory"],
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        result = await _load_mcp_tool(mock_component, tool_config)

        # Verify toolset was created with tool_filter as the allow_list
        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        assert call_kwargs["tool_filter"] == ["read_file", "write_file", "list_directory"]

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset')
    async def test_load_mcp_tool_with_deny_list(self, mock_toolset_class, mock_component):
        """Test that _load_mcp_tool creates predicate for deny_list."""
        mock_toolset_instance = Mock()
        mock_toolset_class.return_value = mock_toolset_instance

        tool_config = {
            "tool_type": "mcp",
            "deny_list": ["delete_file", "move_file"],
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        result = await _load_mcp_tool(mock_component, tool_config)

        # Verify toolset was created with a callable tool_filter (predicate)
        mock_toolset_class.assert_called_once()
        call_kwargs = mock_toolset_class.call_args[1]
        tool_filter = call_kwargs["tool_filter"]

        assert callable(tool_filter)

        # Test the predicate behavior
        allowed_tool = Mock()
        allowed_tool.name = "read_file"
        denied_tool = Mock()
        denied_tool.name = "delete_file"

        assert tool_filter(allowed_tool) is True
        assert tool_filter(denied_tool) is False

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset')
    async def test_load_mcp_tool_deny_list_predicate_with_context(self, mock_toolset_class, mock_component):
        """Test that deny_list predicate works when ADK passes context parameter."""
        mock_toolset_instance = Mock()
        mock_toolset_class.return_value = mock_toolset_instance

        tool_config = {
            "tool_type": "mcp",
            "deny_list": ["dangerous_tool"],
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        await _load_mcp_tool(mock_component, tool_config)

        call_kwargs = mock_toolset_class.call_args[1]
        tool_filter = call_kwargs["tool_filter"]

        # ADK may pass a readonly_context as second parameter
        safe_tool = Mock()
        safe_tool.name = "safe_tool"
        dangerous_tool = Mock()
        dangerous_tool.name = "dangerous_tool"
        mock_context = Mock()

        assert tool_filter(safe_tool, mock_context) is True
        assert tool_filter(dangerous_tool, mock_context) is False

    @pytest.mark.asyncio
    async def test_load_mcp_tool_mutual_exclusivity_validation(self, mock_component):
        """Test that pydantic validation catches mutually exclusive filters."""
        tool_config = {
            "tool_type": "mcp",
            "tool_name": "read_file",
            "allow_list": ["write_file"],
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        with pytest.raises(ValueError) as exc_info:
            await _load_mcp_tool(mock_component, tool_config)

        assert "mutually exclusive" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_load_mcp_tool_missing_connection_params(self, mock_component):
        """Test that missing connection_params raises appropriate error."""
        tool_config = {
            "tool_type": "mcp",
            "allow_list": ["read_file"]
            # Missing connection_params
        }

        with pytest.raises(Exception):  # Pydantic validation error
            await _load_mcp_tool(mock_component, tool_config)

    @pytest.mark.asyncio
    @patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset')
    async def test_load_mcp_tool_empty_allow_list(self, mock_toolset_class, mock_component):
        """Test that empty allow_list is passed correctly."""
        mock_toolset_instance = Mock()
        mock_toolset_class.return_value = mock_toolset_instance

        tool_config = {
            "tool_type": "mcp",
            "allow_list": [],
            "connection_params": {
                "type": "sse",
                "url": "http://localhost:8080"
            }
        }

        await _load_mcp_tool(mock_component, tool_config)

        call_kwargs = mock_toolset_class.call_args[1]
        # Empty list is falsy, so tool_filter should be None
        # This matches the behavior: `elif tool_config_model.allow_list:` is False for []
        assert call_kwargs["tool_filter"] is None
