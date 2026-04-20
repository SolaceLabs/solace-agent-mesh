"""
Unit tests for the scopes-map builder inside _load_python_tool (setup.py).

The scopes map must be keyed by the real tool name, not the
"dynamic_tool_placeholder" value that DynamicTool.__init__ sets on `name`.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.solace_agent_mesh.agent.adk.setup import _load_python_tool


# ---------------------------------------------------------------------------
# Fake tools
# ---------------------------------------------------------------------------


class _FakeDynamicTool:
    """Simulates a DynamicTool instance returned by PythonToolLoader."""

    name = "dynamic_tool_placeholder"
    description = "dynamic_tool_placeholder"

    @property
    def tool_name(self):
        return "my_real_tool"

    @property
    def tool_description(self):
        return "Does something useful."


class _FakeRegularTool:
    """Simulates a plain function-based tool returned by PythonToolLoader."""

    def __init__(self, name="plain_func"):
        self.name = name
        self.description = "A plain function tool."


# ---------------------------------------------------------------------------
# Minimal tool_config dict accepted by PythonToolConfig
# ---------------------------------------------------------------------------

_BASE_TOOL_CONFIG = {
    "tool_type": "python",
    "component_module": "fake.module",
}


# ---------------------------------------------------------------------------
# Helper: patch PythonToolLoader and lifecycle hooks
# ---------------------------------------------------------------------------


def _patch_loader(tools, required_scopes=None):
    """Patch PythonToolLoader to return `tools` and skip lifecycle hooks."""
    mock_loader = MagicMock()
    mock_loader.initialize = AsyncMock()
    mock_loader.get_loaded_tools.return_value = tools

    tool_config = dict(_BASE_TOOL_CONFIG)
    if required_scopes is not None:
        tool_config["required_scopes"] = required_scopes

    loader_patch = patch(
        "src.solace_agent_mesh.agent.adk.setup.PythonToolLoader",
        return_value=mock_loader,
    )
    hooks_patch = patch(
        "src.solace_agent_mesh.agent.adk.setup._create_python_tool_lifecycle_hooks",
        new_callable=AsyncMock,
        return_value=[],
    )
    return loader_patch, hooks_patch, tool_config


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPythonToolScopesMap:
    """_load_python_tool must key the scopes map by tool_name, not by name."""

    async def test_dynamic_tool_scopes_keyed_by_real_name(self):
        """DynamicTool: scopes_map key is tool_name ('my_real_tool'), not placeholder."""
        component = Mock()
        component.log_identifier = "[Test]"

        loader_patch, hooks_patch, tool_config = _patch_loader(
            [_FakeDynamicTool()], required_scopes=["read:data"]
        )

        with loader_patch, hooks_patch:
            _, _, _, scopes_map = await _load_python_tool(component, tool_config)

        assert "my_real_tool" in scopes_map
        assert scopes_map["my_real_tool"] == ["read:data"]
        assert "dynamic_tool_placeholder" not in scopes_map

    async def test_regular_tool_scopes_keyed_by_name_attr(self):
        """Non-DynamicTool: scopes_map key is the `name` attribute."""
        component = Mock()
        component.log_identifier = "[Test]"

        loader_patch, hooks_patch, tool_config = _patch_loader(
            [_FakeRegularTool(name="fetch_data")], required_scopes=["read:api"]
        )

        with loader_patch, hooks_patch:
            _, _, _, scopes_map = await _load_python_tool(component, tool_config)

        assert "fetch_data" in scopes_map
        assert scopes_map["fetch_data"] == ["read:api"]

    async def test_mixed_tools_all_keyed_by_real_names(self):
        """Mix of DynamicTool and regular tool → each keyed correctly."""
        component = Mock()
        component.log_identifier = "[Test]"

        tools = [_FakeDynamicTool(), _FakeRegularTool(name="plain_func")]
        loader_patch, hooks_patch, tool_config = _patch_loader(
            tools, required_scopes=["scope:x"]
        )

        with loader_patch, hooks_patch:
            _, _, _, scopes_map = await _load_python_tool(component, tool_config)

        assert set(scopes_map.keys()) == {"my_real_tool", "plain_func"}
        assert "dynamic_tool_placeholder" not in scopes_map

    async def test_dynamic_tool_no_required_scopes(self):
        """DynamicTool with no required_scopes → key present, value is empty list."""
        component = Mock()
        component.log_identifier = "[Test]"

        loader_patch, hooks_patch, tool_config = _patch_loader(
            [_FakeDynamicTool()], required_scopes=[]
        )

        with loader_patch, hooks_patch:
            _, _, _, scopes_map = await _load_python_tool(component, tool_config)

        assert "my_real_tool" in scopes_map
        assert scopes_map["my_real_tool"] == []
        assert "dynamic_tool_placeholder" not in scopes_map

    async def test_multiple_dynamic_tools_each_keyed_by_own_name(self):
        """Multiple DynamicTools from the same config → each has its own scopes entry."""

        class _OtherDynamicTool:
            name = "dynamic_tool_placeholder"
            description = "dynamic_tool_placeholder"

            @property
            def tool_name(self):
                return "other_tool"

            @property
            def tool_description(self):
                return "Another dynamic tool."

        component = Mock()
        component.log_identifier = "[Test]"

        tools = [_FakeDynamicTool(), _OtherDynamicTool()]
        loader_patch, hooks_patch, tool_config = _patch_loader(
            tools, required_scopes=["admin:access"]
        )

        with loader_patch, hooks_patch:
            _, _, _, scopes_map = await _load_python_tool(component, tool_config)

        assert set(scopes_map.keys()) == {"my_real_tool", "other_tool"}
        assert scopes_map["my_real_tool"] == ["admin:access"]
        assert scopes_map["other_tool"] == ["admin:access"]
        assert "dynamic_tool_placeholder" not in scopes_map

    async def test_empty_tool_list_produces_empty_scopes_map(self):
        """No tools → empty scopes_map (sanity check)."""
        component = Mock()
        component.log_identifier = "[Test]"

        loader_patch, hooks_patch, tool_config = _patch_loader([], required_scopes=["r"])

        with loader_patch, hooks_patch:
            _, _, _, scopes_map = await _load_python_tool(component, tool_config)

        assert scopes_map == {}
