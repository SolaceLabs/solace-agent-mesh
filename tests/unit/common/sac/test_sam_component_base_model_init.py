"""Unit tests for SamComponentBase model initialization (lazy loading)."""

import unittest
from typing import Any
from unittest.mock import patch, MagicMock

from sam_test_infrastructure.feature_flags import mock_flags
from solace_agent_mesh.common.features import core as feature_flags
from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase
from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm


class ConcreteSamComponent(SamComponentBase):
    """Concrete test implementation of SamComponentBase."""

    def __init__(self, info: dict[str, Any], **kwargs: Any):
        super().__init__(info, **kwargs)

    async def _handle_message_async(self, message, topic: str) -> None:
        pass

    def _get_component_id(self) -> str:
        return "test_component_id"

    def _get_component_type(self) -> str:
        return "test_component"

    def _pre_async_cleanup(self) -> None:
        pass

    async def _async_setup_and_run(self) -> None:
        pass

    def _on_model_status_change(self, old_status: str, new_status: str):
        self.last_status_change = (old_status, new_status)


class TestSamComponentBaseModelInit(unittest.TestCase):
    """Test _initialize_model and get_lite_llm_model."""

    def setUp(self):
        feature_flags.initialize()
        self.test_info = {
            "component_name": "test_component",
            "component_module": "test_module",
            "component_config": {
                "namespace": "test/namespace",
                "max_message_size_bytes": 1024000,
            },
        }

    def _make_component(self, model_config=None, model_provider=None, lazy=False):
        """Create a ConcreteSamComponent with mocked config."""
        config_map = {
            "namespace": "test/namespace",
            "max_message_size_bytes": 1024000,
            "model": model_config,
            "model_provider": model_provider,
        }
        with mock_flags(model_config_ui=lazy):
            with patch.object(
                SamComponentBase,
                "get_config",
                side_effect=lambda key, *args: config_map.get(
                    key, args[0] if args else None
                ),
            ):
                component = ConcreteSamComponent(self.test_info)
        # Re-patch get_config for subsequent calls
        self._config_patcher = patch.object(
            SamComponentBase,
            "get_config",
            side_effect=lambda key, *args: config_map.get(
                key, args[0] if args else None
            ),
        )
        self._config_patcher.start()
        return component

    def tearDown(self):
        if hasattr(self, "_config_patcher"):
            self._config_patcher.stop()
        feature_flags._reset_for_testing()

    def test_initialize_model_with_string_config(self):
        """String model config should create a LiteLlm instance."""
        component = self._make_component(model_config="gpt-4")
        model = component._initialize_model()
        assert isinstance(model, LiteLlm)
        assert model.status == "ready"
        assert component.adk_model_instance is model

    def test_initialize_model_with_dict_config(self):
        """Dict model config should create a LiteLlm instance with settings."""
        component = self._make_component(
            model_config={"model": "gpt-4", "timeout": 300}
        )
        model = component._initialize_model()
        assert isinstance(model, LiteLlm)
        assert model.status == "ready"
        assert model._model_config["timeout"] == 300

    def test_initialize_model_dict_applies_default_resilience(self):
        """Dict config without 'type' should get default num_retries and timeout."""
        component = self._make_component(model_config={"model": "gpt-4"})
        model = component._initialize_model()
        assert model._model_config["num_retries"] == 3
        assert model._model_config["timeout"] == 120

    def test_initialize_model_dict_no_defaults_when_type_set(self):
        """Dict config with 'type' should not get default resilience settings."""
        component = self._make_component(
            model_config={"model": "gpt-4", "type": "custom"}
        )
        model = component._initialize_model()
        assert "num_retries" not in model._model_config
        assert "timeout" not in model._model_config

    def test_initialize_model_invalid_type_raises(self):
        """Non-string, non-dict model config should raise ValueError."""
        component = self._make_component(model_config=12345)
        with self.assertRaises(ValueError):
            component._initialize_model()

    def test_initialize_model_lazy_mode_with_provider(self):
        """In lazy mode with model_provider, LiteLlm starts in 'initializing'."""
        component = self._make_component(
            model_provider=["dynamic-provider"], lazy=True
        )
        model = component._initialize_model()
        assert isinstance(model, LiteLlm)
        assert model.status == "initializing"

    def test_get_lite_llm_model_returns_cached_instance(self):
        """get_lite_llm_model should return the same instance on repeated calls."""
        component = self._make_component(model_config="gpt-4")
        model1 = component.get_lite_llm_model()
        model2 = component.get_lite_llm_model()
        assert model1 is model2

    def test_get_lite_llm_model_initializes_on_first_call(self):
        """get_lite_llm_model should call _initialize_model if no instance exists."""
        component = self._make_component(model_config="gpt-4")
        assert component.adk_model_instance is None
        model = component.get_lite_llm_model()
        assert model is not None
        assert component.adk_model_instance is model

    def test_get_lite_llm_model_returns_none_when_no_config(self):
        """get_lite_llm_model returns None when no model or provider configured."""
        component = self._make_component(model_config=None, model_provider=None)
        result = component.get_lite_llm_model()
        assert result is None

    def test_on_model_status_change_callback_wired(self):
        """_on_model_status_change should be wired to LiteLlm instance."""
        component = self._make_component(model_config="gpt-4")
        model = component._initialize_model()
        # Trigger unconfigure -> should call component's callback
        model.unconfigure_model()
        assert hasattr(component, "last_status_change")
        assert component.last_status_change == ("ready", "none")


class TestSamComponentBaseLazyModelMode(unittest.TestCase):
    """Test the _lazy_model_mode flag."""

    def setUp(self):
        feature_flags.initialize()
        self.test_info = {
            "component_name": "test_component",
            "component_module": "test_module",
            "component_config": {
                "namespace": "test/namespace",
                "max_message_size_bytes": 1024000,
            },
        }

    def tearDown(self):
        feature_flags._reset_for_testing()

    def _make_component_with_config(self, config_map, lazy=False):
        with mock_flags(model_config_ui=lazy):
            with patch.object(
                SamComponentBase,
                "get_config",
                side_effect=lambda key, *args: config_map.get(
                    key, args[0] if args else None
                ),
            ):
                return ConcreteSamComponent(self.test_info)

    def test_lazy_mode_enabled_when_env_true(self):
        """_lazy_model_mode should be True when MODEL_CONFIG_UI=true."""
        config_map = {
            "namespace": "test/namespace",
            "max_message_size_bytes": 1024000,
            "model_provider": None,
        }
        component = self._make_component_with_config(config_map, lazy=True)
        assert component._lazy_model_mode is True

    def test_lazy_mode_disabled_by_default(self):
        """_lazy_model_mode should be False when flag is not enabled."""
        config_map = {
            "namespace": "test/namespace",
            "max_message_size_bytes": 1024000,
            "model_provider": None,
        }
        component = self._make_component_with_config(config_map, lazy=False)
        assert component._lazy_model_mode is False

    def test_model_provider_extracted_from_list(self):
        """model_provider should be extracted as the first element of the list."""
        config_map = {
            "namespace": "test/namespace",
            "max_message_size_bytes": 1024000,
            "model_provider": ["provider-a", "provider-b"],
        }
        component = self._make_component_with_config(config_map)
        assert component.model_provider == "provider-a"

    def test_model_provider_none_when_empty_list(self):
        """model_provider should be None when config is an empty list."""
        config_map = {
            "namespace": "test/namespace",
            "max_message_size_bytes": 1024000,
            "model_provider": [],
        }
        component = self._make_component_with_config(config_map)
        assert component.model_provider is None

    def test_model_provider_none_when_not_configured(self):
        """model_provider should be None when not in config."""
        config_map = {
            "namespace": "test/namespace",
            "max_message_size_bytes": 1024000,
            "model_provider": None,
        }
        component = self._make_component_with_config(config_map)
        assert component.model_provider is None
