"""
Unit tests for agent_cards router tool filtering functions.

Tests cover the _filter_tools_by_user_scopes function which filters tools
based on user's scopes using the config resolver.
"""

import pytest
from unittest.mock import MagicMock

from solace_agent_mesh.gateway.http_sse.routers.agent_cards import (
    _filter_tools_by_user_scopes,
)


class TestFilterToolsByUserScopes:
    """Tests for _filter_tools_by_user_scopes function."""

    @pytest.fixture
    def config_resolver_allows_all(self):
        """Config resolver that allows all operations."""
        resolver = MagicMock()
        resolver.validate_operation_config.return_value = {"valid": True}
        return resolver

    @pytest.fixture
    def config_resolver_denies_all(self):
        """Config resolver that denies all operations."""
        resolver = MagicMock()
        resolver.validate_operation_config.return_value = {"valid": False}
        return resolver

    def test_empty_tools_list_returns_empty(self, config_resolver_allows_all):
        """Empty tools list returns empty list."""
        result = _filter_tools_by_user_scopes(
            tools=[],
            user_config={"scopes": []},
            config_resolver=config_resolver_allows_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        assert result == []
        # Config resolver should not be called for empty list
        config_resolver_allows_all.validate_operation_config.assert_not_called()

    def test_none_tools_returns_none(self, config_resolver_allows_all):
        """None tools list returns None (passthrough)."""
        result = _filter_tools_by_user_scopes(
            tools=None,
            user_config={"scopes": []},
            config_resolver=config_resolver_allows_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        assert result is None
        config_resolver_allows_all.validate_operation_config.assert_not_called()

    def test_tools_without_scopes_always_included(self, config_resolver_denies_all):
        """Tools without requiredScopes are always included regardless of resolver."""
        tools = [
            {"name": "public_tool_1", "description": "A public tool"},
            {"name": "public_tool_2", "description": "Another public tool"},
        ]

        result = _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": []},
            config_resolver=config_resolver_denies_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        # All tools should be included since they have no requiredScopes
        assert len(result) == 2
        assert result[0]["name"] == "public_tool_1"
        assert result[1]["name"] == "public_tool_2"
        # Resolver should not be called for tools without scopes
        config_resolver_denies_all.validate_operation_config.assert_not_called()

    def test_tools_with_empty_scopes_always_included(self, config_resolver_denies_all):
        """Tools with empty requiredScopes array are always included."""
        tools = [
            {"name": "tool_1", "description": "Tool 1", "requiredScopes": []},
            {"name": "tool_2", "description": "Tool 2", "requiredScopes": []},
        ]

        result = _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": []},
            config_resolver=config_resolver_denies_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        assert len(result) == 2
        config_resolver_denies_all.validate_operation_config.assert_not_called()

    def test_tools_with_scopes_filtered_when_denied(self, config_resolver_denies_all):
        """Tools with requiredScopes are filtered out when resolver denies access."""
        tools = [
            {
                "name": "protected_tool",
                "description": "Protected",
                "requiredScopes": ["tool:artifact:manage"],
            },
        ]

        result = _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": []},
            config_resolver=config_resolver_denies_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        assert len(result) == 0
        config_resolver_denies_all.validate_operation_config.assert_called_once()

    def test_tools_with_scopes_included_when_allowed(self, config_resolver_allows_all):
        """Tools with requiredScopes are included when resolver allows access."""
        tools = [
            {
                "name": "protected_tool",
                "description": "Protected",
                "requiredScopes": ["tool:artifact:manage"],
            },
        ]

        result = _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": ["tool:artifact:manage"]},
            config_resolver=config_resolver_allows_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        assert len(result) == 1
        assert result[0]["name"] == "protected_tool"
        config_resolver_allows_all.validate_operation_config.assert_called_once()

    def test_mixed_tools_partial_filtering(self):
        """Mix of public and protected tools filters correctly."""
        tools = [
            {"name": "public_tool", "description": "Public"},
            {
                "name": "artifact_tool",
                "description": "Artifact",
                "requiredScopes": ["tool:artifact:manage"],
            },
            {
                "name": "web_tool",
                "description": "Web",
                "requiredScopes": ["tool:web:access"],
            },
        ]

        # Resolver that only allows artifact scope
        resolver = MagicMock()

        def validate_side_effect(user_config, operation_spec, context):
            scopes = operation_spec.get("required_scopes", [])
            if "tool:artifact:manage" in scopes:
                return {"valid": True}
            return {"valid": False}

        resolver.validate_operation_config.side_effect = validate_side_effect

        result = _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": ["tool:artifact:manage"]},
            config_resolver=resolver,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        # Should include public_tool (no scopes) and artifact_tool (allowed)
        # Should exclude web_tool (denied)
        assert len(result) == 2
        tool_names = [t["name"] for t in result]
        assert "public_tool" in tool_names
        assert "artifact_tool" in tool_names
        assert "web_tool" not in tool_names

    def test_operation_spec_contains_correct_data(self, config_resolver_allows_all):
        """Verify operation_spec passed to resolver contains correct data."""
        tools = [
            {
                "name": "my_tool",
                "description": "Test tool",
                "requiredScopes": ["scope:one", "scope:two"],
            },
        ]
        user_config = {"user_id": "test_user", "scopes": ["scope:one"]}

        _filter_tools_by_user_scopes(
            tools=tools,
            user_config=user_config,
            config_resolver=config_resolver_allows_all,
            agent_name="MyAgent",
            log_prefix="[test] ",
        )

        # Verify the operation_spec passed to resolver
        call_args = config_resolver_allows_all.validate_operation_config.call_args
        passed_user_config = call_args[0][0]
        passed_operation_spec = call_args[0][1]
        passed_context = call_args[0][2]

        assert passed_user_config == user_config
        assert passed_operation_spec["operation_type"] == "tool_access"
        assert passed_operation_spec["target_agent"] == "MyAgent"
        assert passed_operation_spec["target_tool"] == "my_tool"
        assert passed_operation_spec["required_scopes"] == ["scope:one", "scope:two"]
        assert passed_context == {"source": "agent_cards_endpoint"}

    def test_preserves_tool_structure(self, config_resolver_allows_all):
        """Filtered tools preserve their full structure."""
        tools = [
            {
                "name": "complex_tool",
                "description": "A complex tool",
                "requiredScopes": ["tool:complex:use"],
                "inputSchema": {"type": "object", "properties": {"arg1": {"type": "string"}}},
                "outputSchema": {"type": "string"},
                "customField": "custom_value",
            },
        ]

        result = _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": ["tool:complex:use"]},
            config_resolver=config_resolver_allows_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        assert len(result) == 1
        assert result[0] == tools[0]  # Exact same object
        assert result[0]["inputSchema"]["properties"]["arg1"]["type"] == "string"
        assert result[0]["customField"] == "custom_value"

    def test_multiple_scopes_on_single_tool(self, config_resolver_allows_all):
        """Tool with multiple requiredScopes passes all to resolver."""
        tools = [
            {
                "name": "multi_scope_tool",
                "description": "Requires multiple scopes",
                "requiredScopes": ["scope:a", "scope:b", "scope:c"],
            },
        ]

        _filter_tools_by_user_scopes(
            tools=tools,
            user_config={"scopes": []},
            config_resolver=config_resolver_allows_all,
            agent_name="TestAgent",
            log_prefix="[test] ",
        )

        # Verify all scopes were passed to resolver
        call_args = config_resolver_allows_all.validate_operation_config.call_args
        passed_operation_spec = call_args[0][1]
        assert passed_operation_spec["required_scopes"] == ["scope:a", "scope:b", "scope:c"]
