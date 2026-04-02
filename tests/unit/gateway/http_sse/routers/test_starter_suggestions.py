"""
Unit tests for extract_agent_data in the starter_suggestions service.
"""

from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.services.starter_suggestions_service import (
    TOOLS_EXTENSION_URI,
    extract_agent_data,
)


def _make_agent(name, description=None, extensions=None):
    """Create a mock agent with the given attributes."""
    agent = MagicMock()
    agent.name = name
    agent.description = description
    if extensions is not None:
        agent.capabilities = MagicMock()
        agent.capabilities.extensions = extensions
    else:
        agent.capabilities = None
    return agent


def _make_extension(uri, params=None):
    """Create a mock extension."""
    ext = MagicMock()
    ext.uri = uri
    ext.params = params
    return ext


def _make_registry(agents_dict):
    """Create a mock AgentRegistry returning agents from a dict."""
    registry = MagicMock()
    registry.get_agent_names.return_value = list(agents_dict.keys())
    registry.get_agent.side_effect = lambda name: agents_dict.get(name)
    return registry


class TestExtractAgentData:
    def test_agent_with_tools(self):
        tools = [
            {"name": "search", "description": "Search the web"},
            {"name": "summarize", "description": "Summarize text"},
        ]
        ext = _make_extension(TOOLS_EXTENSION_URI, params={"tools": tools})
        agent = _make_agent("web-agent", "Web search agent", extensions=[ext])
        registry = _make_registry({"web-agent": agent})

        result = extract_agent_data(registry)

        assert len(result) == 1
        assert result[0]["name"] == "web-agent"
        assert result[0]["description"] == "Web search agent"
        assert len(result[0]["tools"]) == 2
        assert result[0]["tools"][0]["name"] == "search"

    def test_agent_without_capabilities(self):
        agent = _make_agent("simple-agent", "No caps", extensions=None)
        registry = _make_registry({"simple-agent": agent})

        result = extract_agent_data(registry)

        assert len(result) == 1
        assert result[0]["name"] == "simple-agent"
        assert result[0]["tools"] == []

    def test_non_dict_tools_in_params_are_skipped(self):
        tools = ["string-tool", {"name": "valid-tool", "description": "Valid"}]
        ext = _make_extension(TOOLS_EXTENSION_URI, params={"tools": tools})
        agent = _make_agent("mixed-agent", "Mixed tools", extensions=[ext])
        registry = _make_registry({"mixed-agent": agent})

        result = extract_agent_data(registry)

        assert len(result[0]["tools"]) == 1
        assert result[0]["tools"][0]["name"] == "valid-tool"

    def test_empty_registry(self):
        registry = _make_registry({})
        result = extract_agent_data(registry)
        assert result == []

    def test_agent_returns_none_is_skipped(self):
        registry = MagicMock()
        registry.get_agent_names.return_value = ["ghost"]
        registry.get_agent.return_value = None

        result = extract_agent_data(registry)
        assert result == []

    def test_agent_with_no_description(self):
        agent = _make_agent("nodesc-agent", description=None)
        registry = _make_registry({"nodesc-agent": agent})

        result = extract_agent_data(registry)

        assert result[0]["description"] == ""

    def test_extension_with_wrong_uri_ignored(self):
        ext = _make_extension("https://other.com/ext", params={"tools": [{"name": "t", "description": "d"}]})
        agent = _make_agent("other-agent", "Agent", extensions=[ext])
        registry = _make_registry({"other-agent": agent})

        result = extract_agent_data(registry)

        assert result[0]["tools"] == []
