"""Unit test for _check_and_register_tool_name_mcp function."""
import pytest
from unittest.mock import Mock, AsyncMock
from solace_agent_mesh.agent.adk.setup import _check_and_register_tool_name_mcp


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