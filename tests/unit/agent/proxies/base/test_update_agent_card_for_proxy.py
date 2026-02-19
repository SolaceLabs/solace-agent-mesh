"""
Unit tests for _update_agent_card_for_proxy method in BaseProxyComponent.
"""

import pytest
from unittest.mock import Mock, patch

from solace_agent_mesh.agent.proxies.base.component import BaseProxyComponent
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentExtension,
)


class TestUpdateAgentCardForProxy:
    """Tests for _update_agent_card_for_proxy method."""

    @pytest.fixture
    def mock_component(self):
        """Create a mock BaseProxyComponent instance for testing."""
        with patch.multiple(
            BaseProxyComponent,
            __abstractmethods__=set(),
        ):
            component = BaseProxyComponent()
            component.log_identifier = "[TEST]"
            return component

    @pytest.fixture
    def basic_agent_card(self):
        """Create a basic agent card for testing."""
        return AgentCard(
            name="Original Agent",
            description="Test agent",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(),
        )

    def test_config_display_name_provided(self, mock_component, basic_agent_card):
        """Test that config display_name takes highest priority."""
        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name="Custom Name"
        )

        assert result.name == "proxy_alias"
        assert result.capabilities is not None
        assert result.capabilities.extensions is not None
        assert len(result.capabilities.extensions) == 1

        ext = result.capabilities.extensions[0]
        assert ext.uri == "https://solace.com/a2a/extensions/display-name"
        assert ext.params["display_name"] == "Custom Name"

    def test_no_config_display_name_uses_card_name(self, mock_component, basic_agent_card):
        """Test that card's name is used when config display_name is None."""
        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name=None
        )

        assert result.name == "proxy_alias"
        ext = result.capabilities.extensions[0]
        assert ext.params["display_name"] == "Original Agent"

    def test_empty_string_display_name_uses_card_name(self, mock_component, basic_agent_card):
        """Test that empty string is treated as None."""
        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name=""
        )

        ext = result.capabilities.extensions[0]
        assert ext.params["display_name"] == "Original Agent"

    def test_whitespace_only_display_name_uses_card_name(self, mock_component, basic_agent_card):
        """Test that whitespace-only string is treated as None."""
        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name="   "
        )

        ext = result.capabilities.extensions[0]
        assert ext.params["display_name"] == "Original Agent"

    def test_config_display_name_whitespace_is_stripped(self, mock_component, basic_agent_card):
        """Test that config display_name with surrounding whitespace is stripped."""
        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name="  Custom Name  "
        )

        ext = result.capabilities.extensions[0]
        assert ext.params["display_name"] == "Custom Name"

    def test_priority_config_over_extension(self, mock_component):
        """Test config display_name takes priority over existing extension."""
        card_with_extension = AgentCard(
            name="Agent Name",
            description="Test",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(
                extensions=[
                    AgentExtension(
                        uri="https://solace.com/a2a/extensions/display-name",
                        params={"display_name": "Extension Name"}
                    )
                ]
            ),
        )

        result = mock_component._update_agent_card_for_proxy(
            card_with_extension, "proxy_alias", config_display_name="Config Name"
        )

        ext = result.capabilities.extensions[0]
        assert ext.params["display_name"] == "Config Name"

    def test_priority_extension_over_card_name(self, mock_component):
        """Test existing extension takes priority over card name when no config provided."""
        card_with_extension = AgentCard(
            name="Agent Name",
            description="Test",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(
                extensions=[
                    AgentExtension(
                        uri="https://solace.com/a2a/extensions/display-name",
                        params={"display_name": "Extension Name"}
                    )
                ]
            ),
        )

        result = mock_component._update_agent_card_for_proxy(
            card_with_extension, "proxy_alias", config_display_name=None
        )

        ext = result.capabilities.extensions[0]
        assert ext.params["display_name"] == "Extension Name"

    def test_extension_created_when_none_exists(self, mock_component, basic_agent_card):
        """Test that extension is created when card has no extensions."""
        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name="New Name"
        )

        assert result.capabilities is not None
        assert result.capabilities.extensions is not None
        assert len(result.capabilities.extensions) == 1
        assert result.capabilities.extensions[0].uri == "https://solace.com/a2a/extensions/display-name"

    def test_extension_updated_when_exists(self, mock_component):
        """Test that existing extension is updated, not duplicated."""
        card_with_extension = AgentCard(
            name="Agent Name",
            description="Test",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(
                extensions=[
                    AgentExtension(
                        uri="https://solace.com/a2a/extensions/display-name",
                        params={"display_name": "Old Name"}
                    )
                ]
            ),
        )

        result = mock_component._update_agent_card_for_proxy(
            card_with_extension, "proxy_alias", config_display_name="New Name"
        )

        assert len(result.capabilities.extensions) == 1
        assert result.capabilities.extensions[0].params["display_name"] == "New Name"

    def test_card_with_no_capabilities(self, mock_component):
        """Test handling of card with no capabilities field."""
        minimal_card = AgentCard(
            name="Minimal Agent",
            description="Test",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(),
        )

        result = mock_component._update_agent_card_for_proxy(
            minimal_card, "proxy_alias", config_display_name="Test Name"
        )

        assert result.capabilities is not None
        assert result.capabilities.extensions is not None
        assert len(result.capabilities.extensions) == 1

    def test_card_with_capabilities_but_no_extensions(self, mock_component):
        """Test handling of card with capabilities but no extensions list."""
        card = AgentCard(
            name="Agent",
            description="Test",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(),
        )

        result = mock_component._update_agent_card_for_proxy(
            card, "proxy_alias", config_display_name="Test Name"
        )

        assert result.capabilities.extensions is not None
        assert len(result.capabilities.extensions) == 1

    def test_preserves_other_extensions(self, mock_component):
        """Test that other extensions are preserved."""
        card_with_extensions = AgentCard(
            name="Agent",
            description="Test",
            url="https://example.com",
            version="1.0.0",
            skills=[],
            default_input_modes=["text"],
            default_output_modes=["text"],
            capabilities=AgentCapabilities(
                extensions=[
                    AgentExtension(
                        uri="https://example.com/other-extension",
                        params={"key": "value"}
                    )
                ]
            ),
        )

        result = mock_component._update_agent_card_for_proxy(
            card_with_extensions, "proxy_alias", config_display_name="Test Name"
        )

        assert len(result.capabilities.extensions) == 2
        assert any(ext.uri == "https://example.com/other-extension" for ext in result.capabilities.extensions)
        assert any(ext.uri == "https://solace.com/a2a/extensions/display-name" for ext in result.capabilities.extensions)

    def test_original_card_not_modified(self, mock_component, basic_agent_card):
        """Test that original card is not modified (deep copy)."""
        original_name = basic_agent_card.name

        result = mock_component._update_agent_card_for_proxy(
            basic_agent_card, "proxy_alias", config_display_name="New Name"
        )

        assert basic_agent_card.name == original_name
        assert result.name == "proxy_alias"
