"""
Unit tests for intelligent MCP callback functions.
Tests cover schema configuration resolution from tool config and agent config.
"""

from unittest.mock import Mock

from solace_agent_mesh.agent.adk.intelligent_mcp_callbacks import (
    _get_schema_config_from_tool_or_agent,
)
from solace_agent_mesh.agent.utils.artifact_helpers import DEFAULT_SCHEMA_MAX_KEYS


class TestGetSchemaConfigFromToolOrAgent:
    """Test the _get_schema_config_from_tool_or_agent helper function."""

    def test_returns_tool_config_when_present(self):
        """Tool config should take precedence over agent config."""
        # Create a mock tool with _tool_config
        mock_tool = Mock()
        mock_tool._tool_config = {
            "schema_inference_depth": 6,
            "schema_max_keys": 30,
        }

        # Create a mock host component with different values
        mock_host = Mock()
        mock_host.get_config.return_value = 4  # Agent default

        # Tool config should be returned
        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 6

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_max_keys", 20
        )
        assert result == 30

        # Agent config should not have been called for these keys
        mock_host.get_config.assert_not_called()

    def test_falls_back_to_agent_config_when_tool_config_missing_key(self):
        """Agent config should be used when tool config doesn't have the key."""
        mock_tool = Mock()
        mock_tool._tool_config = {
            "schema_inference_depth": 6,
            # schema_max_keys not present
        }

        mock_host = Mock()
        mock_host.get_config.return_value = 25  # Agent value

        # schema_inference_depth from tool config
        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 6
        mock_host.get_config.assert_not_called()

        # schema_max_keys should fall back to agent config
        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_max_keys", 20
        )
        assert result == 25
        mock_host.get_config.assert_called_once_with("schema_max_keys", 20)

    def test_falls_back_to_agent_config_when_no_tool_config(self):
        """Agent config should be used when tool has no _tool_config."""
        mock_tool = Mock(spec=[])  # No _tool_config attribute

        mock_host = Mock()
        mock_host.get_config.return_value = 5

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 5
        mock_host.get_config.assert_called_once_with("schema_inference_depth", 4)

    def test_falls_back_to_agent_config_when_tool_config_is_none(self):
        """Agent config should be used when _tool_config is None."""
        mock_tool = Mock()
        mock_tool._tool_config = None

        mock_host = Mock()
        mock_host.get_config.return_value = 7

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 7
        mock_host.get_config.assert_called_once_with("schema_inference_depth", 4)

    def test_falls_back_to_agent_config_when_tool_config_is_not_dict(self):
        """Agent config should be used when _tool_config is not a dict."""
        mock_tool = Mock()
        mock_tool._tool_config = "not a dict"

        mock_host = Mock()
        mock_host.get_config.return_value = 8

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 8
        mock_host.get_config.assert_called_once_with("schema_inference_depth", 4)

    def test_falls_back_to_agent_config_when_tool_config_empty(self):
        """Agent config should be used when _tool_config is empty dict."""
        mock_tool = Mock()
        mock_tool._tool_config = {}

        mock_host = Mock()
        mock_host.get_config.return_value = 9

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 9
        mock_host.get_config.assert_called_once_with("schema_inference_depth", 4)

    def test_default_value_used_when_not_in_agent_config(self):
        """Default value should be passed through to agent config lookup."""
        mock_tool = Mock()
        mock_tool._tool_config = {}

        mock_host = Mock()
        # Simulate agent config returning the default
        mock_host.get_config.side_effect = lambda key, default: default

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 4

        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_max_keys", DEFAULT_SCHEMA_MAX_KEYS
        )
        assert result == DEFAULT_SCHEMA_MAX_KEYS

    def test_tool_config_value_zero_is_used(self):
        """Zero values in tool config should be used (not treated as falsy)."""
        mock_tool = Mock()
        mock_tool._tool_config = {
            "schema_inference_depth": 0,  # Explicitly set to 0
        }

        mock_host = Mock()
        mock_host.get_config.return_value = 4

        # Note: Current implementation uses `if config_key in tool_config`
        # so 0 should be properly returned
        result = _get_schema_config_from_tool_or_agent(
            mock_tool, mock_host, "schema_inference_depth", 4
        )
        assert result == 0
        mock_host.get_config.assert_not_called()
