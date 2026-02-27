#!/usr/bin/env python3
"""
Unit tests for the SamAgentAppConfig class
"""

import pytest
from pydantic import ValidationError
from unittest.mock import MagicMock, patch

from src.solace_agent_mesh.agent.sac.app import SamAgentAppConfig, AgentIdentityConfig, SamAgentApp

class TestAgentIdentityConfig:
    """Test cases for the AgentIdentityConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = AgentIdentityConfig()
        assert config.key_mode == "auto"
        assert config.key_identity is None
        assert config.key_persistence is None

    def test_manual_mode_requires_key_identity(self):
        """Test that key_identity is required when key_mode is manual."""
        with pytest.raises(ValidationError) as excinfo:
            AgentIdentityConfig(key_mode="manual")
        assert "'key_identity' is required when 'key_mode' is 'manual'" in str(excinfo.value)

    def test_auto_mode_with_key_identity_warning(self, caplog):
        """Test that a warning is logged when key_identity is provided with auto mode."""
        AgentIdentityConfig(key_mode="auto", key_identity="test-key")
        assert "Configuration Warning: 'key_identity' is ignored when 'key_mode' is 'auto'" in caplog.text

    def test_custom_values(self):
        """Test that custom values are set correctly."""
        config = AgentIdentityConfig(
            key_mode="manual",
            key_identity="test-key",
            key_persistence="/path/to/keys/agent_test.key"
        )
        assert config.key_mode == "manual"
        assert config.key_identity == "test-key"
        assert config.key_persistence == "/path/to/keys/agent_test.key"


class TestSamAgentAppConfig:
    """Test cases for the SamAgentAppConfig class with agent_identity."""

    def test_default_agent_identity(self):
        """Test that default agent_identity is set correctly."""
        # Create minimal valid config
        config = SamAgentAppConfig(
            namespace="test",
            agent_name="test-agent",
            model="test-model",
            agent_card={"description": "Test agent"},
            agent_card_publishing={"interval_seconds": 60}
        )
        assert config.agent_identity is not None
        assert config.agent_identity.key_mode == "auto"
        assert config.agent_identity.key_identity is None
        assert config.agent_identity.key_persistence is None

    def test_custom_agent_identity(self):
        """Test that custom agent_identity is set correctly."""
        # Create config with custom agent_identity
        config = SamAgentAppConfig(
            namespace="test",
            agent_name="test-agent",
            model="test-model",
            agent_card={"description": "Test agent"},
            agent_card_publishing={"interval_seconds": 60},
            agent_identity={
                "key_mode": "manual",
                "key_identity": "test-key",
                "key_persistence": "/path/to/keys/agent_test.key"
            }
        )
        assert config.agent_identity is not None
        assert config.agent_identity.key_mode == "manual"
        assert config.agent_identity.key_identity == "test-key"
        assert config.agent_identity.key_persistence == "/path/to/keys/agent_test.key"

    def test_yaml_omitted_agent_identity(self):
        """Test that agent_identity is set to default when omitted from YAML."""
        # Simulate YAML parsing by creating a dict without agent_identity
        yaml_dict = {
            "namespace": "test",
            "agent_name": "test-agent",
            "model": "test-model",
            "agent_card": {"description": "Test agent"},
            "agent_card_publishing": {"interval_seconds": 60}
        }
        config = SamAgentAppConfig.model_validate(yaml_dict)
        assert config.agent_identity is not None
        assert config.agent_identity.key_mode == "auto"


class TestAgentNameSanitization:
    """Test cases for agent name sanitization during app initialization."""

    @pytest.fixture
    def minimal_app_info(self):
        """Minimal app_info for testing agent initialization."""
        return {
            "name": "test_app",
            "app_config": {
                "namespace": "test/namespace",
                "agent_name": "test-agent",  # Agent name with dash
                "model": "gemini-1.5-pro",
                "instruction": "Test agent",
                "agent_card": {
                    "description": "Test agent"
                },
                "agent_card_publishing": {
                    "interval_seconds": 60
                },
                "session_service": {
                    "type": "memory"
                },
                "artifact_service": {
                    "type": "memory"
                }
            }
        }

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_agent_name_with_dash_gets_sanitized(self, mock_super_init, minimal_app_info, caplog):
        """Test that agent names with dashes are sanitized to underscores."""
        mock_super_init.return_value = None

        # Initialize the app
        app = SamAgentApp(minimal_app_info)

        # Verify the agent_name was sanitized
        sanitized_name = minimal_app_info["app_config"].agent_name
        assert sanitized_name == "test_agent"
        assert "-" not in sanitized_name

        # Verify warning was logged
        assert "contains invalid characters" in caplog.text
        assert "test-agent" in caplog.text
        assert "test_agent" in caplog.text

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_agent_name_with_multiple_dashes(self, mock_super_init, minimal_app_info, caplog):
        """Test that multiple dashes are all converted to underscores."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "my-test-agent-name"

        app = SamAgentApp(minimal_app_info)

        sanitized_name = minimal_app_info["app_config"].agent_name
        assert sanitized_name == "my_test_agent_name"
        assert "-" not in sanitized_name

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_agent_name_with_special_characters(self, mock_super_init, minimal_app_info, caplog):
        """Test that special characters are converted to underscores."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "test@agent#name!"

        app = SamAgentApp(minimal_app_info)

        sanitized_name = minimal_app_info["app_config"].agent_name
        assert sanitized_name == "test_agent_name_"
        # Verify only alphanumeric and underscores remain
        assert all(c.isalnum() or c == '_' for c in sanitized_name)

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_valid_agent_name_unchanged(self, mock_super_init, minimal_app_info, caplog):
        """Test that valid agent names (alphanumeric + underscore) are not modified."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "ValidAgentName123"

        app = SamAgentApp(minimal_app_info)

        # Should remain unchanged
        assert minimal_app_info["app_config"].agent_name == "ValidAgentName123"
        # No warning should be logged
        assert "contains invalid characters" not in caplog.text

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_agent_name_with_underscores_unchanged(self, mock_super_init, minimal_app_info, caplog):
        """Test that agent names with underscores are not modified."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "test_agent_name"

        app = SamAgentApp(minimal_app_info)

        assert minimal_app_info["app_config"].agent_name == "test_agent_name"
        # No warning should be logged
        assert "contains invalid characters" not in caplog.text

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_agent_name_with_spaces(self, mock_super_init, minimal_app_info, caplog):
        """Test that spaces in agent names are converted to underscores."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "test agent name"

        app = SamAgentApp(minimal_app_info)

        sanitized_name = minimal_app_info["app_config"].agent_name
        assert sanitized_name == "test_agent_name"
        assert " " not in sanitized_name

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_mixed_valid_invalid_characters(self, mock_super_init, minimal_app_info, caplog):
        """Test agent name with mix of valid characters, dashes, and underscores."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "my_agent-name-123"

        app = SamAgentApp(minimal_app_info)

        sanitized_name = minimal_app_info["app_config"].agent_name
        assert sanitized_name == "my_agent_name_123"
        # Underscores preserved, dashes converted
        assert "-" not in sanitized_name
        assert "_" in sanitized_name

    @patch('src.solace_agent_mesh.agent.sac.app.SamAppBase.__init__')
    def test_sanitization_affects_topics(self, mock_super_init, minimal_app_info):
        """Test that sanitized agent name is used in topic construction."""
        mock_super_init.return_value = None
        minimal_app_info["app_config"]["agent_name"] = "test-agent"

        with patch('src.solace_agent_mesh.agent.sac.app.get_agent_request_topic') as mock_topic:
            app = SamAgentApp(minimal_app_info)

            # Verify that topic functions are called with sanitized name
            # The sanitized name should be "test_agent"
            mock_topic.assert_called()
            call_args = mock_topic.call_args
            assert call_args[0][1] == "test_agent"  # Second argument is agent_name
