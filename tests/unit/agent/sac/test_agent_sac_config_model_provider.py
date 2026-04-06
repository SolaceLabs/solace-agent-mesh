"""Unit tests for SamAgentAppConfig model and model_provider validation."""

import pytest
from pydantic import ValidationError

from sam_test_infrastructure.feature_flags import mock_flags
from solace_agent_mesh.common.features import core as feature_flags
from src.solace_agent_mesh.agent.sac.app import SamAgentAppConfig


@pytest.fixture(autouse=True)
def _feature_flags():
    feature_flags.initialize()
    yield
    feature_flags._reset_for_testing()


def _minimal_config(**overrides):
    """Return a minimal valid SamAgentAppConfig dict with overrides applied."""
    base = {
        "namespace": "test",
        "agent_name": "test-agent",
        "model": "test-model",
        "agent_card": {"description": "Test agent"},
        "agent_card_publishing": {"interval_seconds": 60},
    }
    base.update(overrides)
    return base


class TestModelFieldOptional:
    """Test that 'model' is now optional under the right conditions."""

    def test_model_required_when_feature_flag_off(self):
        """Without MODEL_CONFIG_UI, model is required."""
        with mock_flags(model_config_ui=False):
            with pytest.raises(ValidationError, match="model"):
                SamAgentAppConfig.model_validate(_minimal_config(model=None))

    def test_model_provided_when_feature_flag_off(self):
        """With model provided and no feature flag, config is valid."""
        with mock_flags(model_config_ui=False):
            config = SamAgentAppConfig.model_validate(_minimal_config())
            assert config.model == "test-model"

    def test_model_none_allowed_with_model_provider_and_feature_flag(self):
        """With MODEL_CONFIG_UI=true and model_provider set, model can be None."""
        with mock_flags(model_config_ui=True):
            config = SamAgentAppConfig.model_validate(
                _minimal_config(model=None, model_provider=["some-provider"])
            )
            assert config.model is None
            assert config.model_provider == ["some-provider"]

    def test_model_and_provider_both_none_raises_with_feature_flag(self):
        """With feature flag but neither model nor model_provider, validation fails."""
        with mock_flags(model_config_ui=True):
            with pytest.raises(ValidationError, match="model_provider.*model"):
                SamAgentAppConfig.model_validate(
                    _minimal_config(model=None, model_provider=None)
                )

    def test_model_provided_with_feature_flag(self):
        """With feature flag and model provided (no provider), config is valid."""
        with mock_flags(model_config_ui=True):
            config = SamAgentAppConfig.model_validate(_minimal_config())
            assert config.model == "test-model"


class TestModelProviderField:
    """Test the model_provider field."""

    def test_model_provider_defaults_to_none(self):
        """model_provider should default to None."""
        config = SamAgentAppConfig.model_validate(_minimal_config())
        assert config.model_provider is None

    def test_model_provider_accepts_list(self):
        """model_provider should accept a list of strings."""
        with mock_flags(model_config_ui=True):
            config = SamAgentAppConfig.model_validate(
                _minimal_config(model_provider=["provider-a", "provider-b"])
            )
            assert config.model_provider == ["provider-a", "provider-b"]

    def test_model_dict_config_still_works(self):
        """model can still be a dict config (not just a string)."""
        config = SamAgentAppConfig.model_validate(
            _minimal_config(model={"model": "gpt-4", "timeout": 60})
        )
        assert isinstance(config.model, dict)
        assert config.model["model"] == "gpt-4"
