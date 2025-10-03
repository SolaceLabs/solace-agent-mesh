#!/usr/bin/env python3
"""
Unit tests for the SamAgentAppConfig class
"""

import pytest
from pydantic import ValidationError

from src.solace_agent_mesh.agent.sac.app import SamAgentAppConfig, AgentIdentityConfig


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
