"""Unit test for _check_and_register_tool_name_mcp function."""
import pytest
from unittest.mock import Mock, AsyncMock
from solace_agent_mesh.agent.adk.setup import _check_and_register_tool_name_mcp, _load_mcp_tool
from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import (
    EmbedResolvingMCPToolset,
)


@pytest.mark.asyncio
async def test_register_mcp_tools_with_prefix():
    """Register MCP tools with prefix and detect duplicates."""
    component = Mock()
    component.log_identifier = "[TestAgent]"

    loaded_tool_names = set()

    tool1 = Mock()
    tool1.name = "read"
    tool2 = Mock()
    tool2.name = "write"

    toolset = Mock()
    toolset.tool_name_prefix = "test"
    toolset.get_tools = AsyncMock(return_value=[tool1, tool2])

    await _check_and_register_tool_name_mcp(component, loaded_tool_names, toolset)

    assert "test_read" in loaded_tool_names
    assert "test_write" in loaded_tool_names
    assert len(loaded_tool_names) == 2

    # Test duplicate detection
    with pytest.raises(ValueError, match="Configuration Error: Duplicate tool name 'test_read'"):
        await _check_and_register_tool_name_mcp(component, loaded_tool_names, toolset)


@pytest.mark.asyncio
async def test_register_mcp_tools_without_prefix():
    """Register MCP tools without prefix and detect duplicates."""
    component = Mock()
    component.log_identifier = "[TestAgent]"

    loaded_tool_names = set()

    tool1 = Mock()
    tool1.name = "read"
    tool2 = Mock()
    tool2.name = "write"

    toolset = Mock()
    toolset.tool_name_prefix = None
    toolset.get_tools = AsyncMock(return_value=[tool1, tool2])

    await _check_and_register_tool_name_mcp(component, loaded_tool_names, toolset)

    assert "read" in loaded_tool_names
    assert "write" in loaded_tool_names
    assert len(loaded_tool_names) == 2

    # Test duplicate detection
    with pytest.raises(ValueError, match="Configuration Error: Duplicate tool name 'read'"):
        await _check_and_register_tool_name_mcp(component, loaded_tool_names, toolset)


def test_embed_resolving_mcp_toolset_with_prefix():
    """EmbedResolvingMCPToolset construction with mcp prefix."""
    connection_params = Mock()
    toolset = EmbedResolvingMCPToolset(
        connection_params=connection_params,
        tool_filter=None,
        tool_name_prefix="mcp",
        tool_config={"test_key": "test_value"},
    )

    assert toolset.tool_name_prefix == "mcp"
    assert toolset._tool_config == {"test_key": "test_value"}


@pytest.mark.asyncio
async def test_load_mcp_tool_passes_prefix():
    """_load_mcp_tool passes tool_name_prefix to EmbedResolvingMCPToolset."""
    component = Mock()
    component.log_identifier = "[TestAgent]"

    tool_config = {
        "tool_type": "mcp",
        "tool_name_prefix": "fs",
        "connection_params": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
    }

    tools, builtins, cleanups = await _load_mcp_tool(component, tool_config)

    assert len(tools) == 1
    toolset = tools[0]
    assert isinstance(toolset, EmbedResolvingMCPToolset)
    assert toolset.tool_name_prefix == "fs"
    assert toolset._tool_config == tool_config