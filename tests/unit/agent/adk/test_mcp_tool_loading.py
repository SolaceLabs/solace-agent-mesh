"""Tests for MCP tool loading in setup.py with tool_name_prefix."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from solace_agent_mesh.agent.adk.setup import _load_mcp_tool


@pytest.fixture
def mock_component():
    """Mock SamAgentComponent for testing."""
    component = Mock()
    component.log_identifier = "[TestAgent]"
    return component


class TestMCPToolLoadingWithPrefix:
    """Test _load_mcp_tool with tool_name_prefix parameter."""

    @pytest.mark.asyncio
    async def test_load_mcp_tool_with_prefix(self, mock_component):
        """Test loading MCP tool with tool_name_prefix."""
        tool_config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"},
            "tool_name_prefix": "custom"
        }

        with patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset') as mock_toolset_class:
            mock_toolset = Mock()
            mock_toolset_class.return_value = mock_toolset

            result = await _load_mcp_tool(mock_component, tool_config)

            assert len(result) == 3
            assert result[0][0] == mock_toolset
            mock_toolset_class.assert_called_once()
            call_kwargs = mock_toolset_class.call_args.kwargs
            assert call_kwargs['tool_name_prefix'] == "custom"

    @pytest.mark.asyncio
    async def test_load_mcp_tool_without_prefix(self, mock_component):
        """Test loading MCP tool without tool_name_prefix (backward compatibility)."""
        tool_config = {
            "tool_type": "mcp",
            "connection_params": {"type": "stdio", "command": "test"}
        }

        with patch('solace_agent_mesh.agent.adk.setup.EmbedResolvingMCPToolset') as mock_toolset_class:
            mock_toolset = Mock()
            mock_toolset_class.return_value = mock_toolset

            result = await _load_mcp_tool(mock_component, tool_config)

            assert len(result) == 3
            assert result[0][0] == mock_toolset
            mock_toolset_class.assert_called_once()
            call_kwargs = mock_toolset_class.call_args.kwargs
            assert call_kwargs['tool_name_prefix'] is None