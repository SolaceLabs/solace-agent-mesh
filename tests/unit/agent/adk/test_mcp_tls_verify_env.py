"""Tests for SAM_MCP_CONNECTOR_TLS_VERIFY env var override in MCP loader."""

from unittest.mock import Mock

import pytest

from solace_agent_mesh.agent.adk.embed_resolving_mcp_toolset import (
    EmbedResolvingMCPToolset,
)
from solace_agent_mesh.agent.adk.mcp_ssl_config import ENV_MCP_TLS_VERIFY
from solace_agent_mesh.agent.adk.setup import _load_mcp_tool
from solace_agent_mesh.agent.adk.ssl_mcp_session_manager import (
    SslConfigurableMCPSessionManager,
)


@pytest.fixture
def component():
    component = Mock()
    component.log_identifier = "[TestAgent]"
    return component


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(ENV_MCP_TLS_VERIFY, raising=False)


def _sse_tool_config():
    return {
        "tool_type": "mcp",
        "connection_params": {
            "type": "sse",
            "url": "https://example.test/sse",
        },
    }


def _streamable_http_tool_config():
    return {
        "tool_type": "mcp",
        "connection_params": {
            "type": "streamable-http",
            "url": "https://example.test/mcp",
        },
    }


def _stdio_tool_config():
    return {
        "tool_type": "mcp",
        "connection_params": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
    }


@pytest.mark.asyncio
async def test_sse_with_env_var_unset_does_not_disable_verify(component):
    tools, _, _, _ = await _load_mcp_tool(component, _sse_tool_config())

    toolset = tools[0]
    assert isinstance(toolset, EmbedResolvingMCPToolset)
    # No ssl_config in YAML and no env override → no SslConfigurableMCPSessionManager.
    assert not isinstance(
        toolset._mcp_session_manager, SslConfigurableMCPSessionManager
    )


@pytest.mark.asyncio
async def test_sse_with_env_var_false_disables_verify(component, monkeypatch):
    monkeypatch.setenv(ENV_MCP_TLS_VERIFY, "false")

    tools, _, _, _ = await _load_mcp_tool(component, _sse_tool_config())

    toolset = tools[0]
    assert isinstance(
        toolset._mcp_session_manager, SslConfigurableMCPSessionManager
    )
    assert toolset._mcp_session_manager._ssl_config.verify is False


@pytest.mark.asyncio
async def test_streamable_http_with_env_var_false_disables_verify(
    component, monkeypatch
):
    monkeypatch.setenv(ENV_MCP_TLS_VERIFY, "FALSE")

    tools, _, _, _ = await _load_mcp_tool(
        component, _streamable_http_tool_config()
    )

    toolset = tools[0]
    assert isinstance(
        toolset._mcp_session_manager, SslConfigurableMCPSessionManager
    )
    assert toolset._mcp_session_manager._ssl_config.verify is False


@pytest.mark.asyncio
async def test_env_var_overrides_config_level_verify_true(component, monkeypatch):
    monkeypatch.setenv(ENV_MCP_TLS_VERIFY, "false")

    tool_config = _sse_tool_config()
    tool_config["connection_params"]["ssl_config"] = {"verify": True}

    tools, _, _, _ = await _load_mcp_tool(component, tool_config)

    toolset = tools[0]
    assert isinstance(
        toolset._mcp_session_manager, SslConfigurableMCPSessionManager
    )
    # Env var must override the explicit verify=True from config.
    assert toolset._mcp_session_manager._ssl_config.verify is False


@pytest.mark.asyncio
async def test_env_var_true_does_not_disable_config_verify_true(
    component, monkeypatch
):
    monkeypatch.setenv(ENV_MCP_TLS_VERIFY, "true")

    tool_config = _sse_tool_config()
    tool_config["connection_params"]["ssl_config"] = {"verify": True}

    tools, _, _, _ = await _load_mcp_tool(component, tool_config)

    toolset = tools[0]
    assert isinstance(
        toolset._mcp_session_manager, SslConfigurableMCPSessionManager
    )
    assert toolset._mcp_session_manager._ssl_config.verify is True


@pytest.mark.asyncio
async def test_stdio_ignores_env_var(component, monkeypatch):
    monkeypatch.setenv(ENV_MCP_TLS_VERIFY, "false")

    tools, _, _, _ = await _load_mcp_tool(component, _stdio_tool_config())

    toolset = tools[0]
    # Stdio has no TLS, so the env var must not force an SSL session manager.
    assert not isinstance(
        toolset._mcp_session_manager, SslConfigurableMCPSessionManager
    )