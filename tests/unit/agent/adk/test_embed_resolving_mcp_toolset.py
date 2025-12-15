"""Tests for EmbedResolvingMCPToolset with tool_name_prefix support."""
import pytest
from unittest.mock import patch, MagicMock
from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import EmbedResolvingMCPToolset


class TestEmbedResolvingMCPToolsetPrefix:
    """Test EmbedResolvingMCPToolset with tool_name_prefix parameter."""

    @pytest.mark.asyncio
    async def test_init_with_tool_name_prefix(self):
        """Test initialization with tool_name_prefix parameter."""
        connection_params = {"type": "stdio", "command": "test", "args": []}

        with patch('solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._BaseMcpToolsetClass') as mock_base:
            toolset = EmbedResolvingMCPToolset(
                connection_params=connection_params,
                tool_name_prefix="test_prefix"
            )
            assert toolset is not None

    @pytest.mark.asyncio
    async def test_init_without_tool_name_prefix(self):
        """Test initialization without tool_name_prefix (backward compatibility)."""
        connection_params = {"type": "stdio", "command": "test", "args": []}

        with patch('solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset._BaseMcpToolsetClass') as mock_base:
            toolset = EmbedResolvingMCPToolset(connection_params=connection_params)
            assert toolset is not None