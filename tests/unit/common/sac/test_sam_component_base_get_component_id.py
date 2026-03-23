"""Unit tests for SamComponentBase.get_component_id and _start_model_listener."""

import pytest
from typing import Any
from unittest.mock import patch, MagicMock, AsyncMock

from sam_test_infrastructure.feature_flags import mock_flags
from solace_agent_mesh.common.features import core as feature_flags
from solace_agent_mesh.common.sac.sam_component_base import SamComponentBase
from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm


@pytest.fixture(autouse=True)
def _feature_flags():
    feature_flags.initialize()
    yield
    feature_flags._reset_for_testing()


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
        pass


def _make_component(model_config=None, model_provider=None, lazy=False, extra_attrs=None):
    """Create a ConcreteSamComponent with mocked config."""
    test_info = {
        "component_name": "test_component",
        "component_module": "test_module",
        "component_config": {
            "namespace": "test/namespace/",
            "max_message_size_bytes": 1024000,
        },
    }
    config_map = {
        "namespace": "test/namespace/",
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
            component = ConcreteSamComponent(test_info)

    # Apply extra attributes after creation
    if extra_attrs:
        for attr, value in extra_attrs.items():
            setattr(component, attr, value)

    return component


class TestGetComponentId:
    """Test get_component_id method."""

    def test_returns_cached_component_id(self):
        """Should return _component_id if already set."""
        component = _make_component()
        component._component_id = "cached_id"
        assert component.get_component_id() == "cached_id"

    def test_returns_agent_name_when_set(self):
        """Should return agent_name when available."""
        component = _make_component()
        # Clear any cached _component_id
        if hasattr(component, "_component_id"):
            delattr(component, "_component_id")
        component.agent_name = "my_agent"
        assert component.get_component_id() == "my_agent"

    def test_returns_gateway_id_when_set(self):
        """Should return gateway_id when agent_name is not available."""
        component = _make_component()
        if hasattr(component, "_component_id"):
            delattr(component, "_component_id")
        component.gateway_id = "my_gateway"
        assert component.get_component_id() == "my_gateway"

    def test_returns_workflow_name_when_set(self):
        """Should return workflow_name when agent_name and gateway_id are not available."""
        component = _make_component()
        if hasattr(component, "_component_id"):
            delattr(component, "_component_id")
        component.workflow_name = "my_workflow"
        assert component.get_component_id() == "my_workflow"

    def test_prefers_agent_name_over_gateway_id(self):
        """agent_name should take precedence over gateway_id."""
        component = _make_component()
        if hasattr(component, "_component_id"):
            delattr(component, "_component_id")
        component.agent_name = "my_agent"
        component.gateway_id = "my_gateway"
        assert component.get_component_id() == "my_agent"

    def test_falls_back_to_generic_id(self):
        """Should return a generic identifier when no specific id is available."""
        component = _make_component()
        if hasattr(component, "_component_id"):
            delattr(component, "_component_id")
        result = component.get_component_id()
        assert result.startswith("component_")

    def test_caches_result(self):
        """Should cache the component_id after first call."""
        component = _make_component()
        if hasattr(component, "_component_id"):
            delattr(component, "_component_id")
        component.agent_name = "my_agent"

        id1 = component.get_component_id()
        # Change agent_name - should still return cached value
        component.agent_name = "different_agent"
        id2 = component.get_component_id()
        assert id1 == id2 == "my_agent"

    def test_explicitly_set_component_id(self):
        """Directly setting _component_id should be returned."""
        component = _make_component()
        component._component_id = "platform_service"
        assert component.get_component_id() == "platform_service"


class TestStartModelListener:
    """Test _start_model_listener method."""

    @pytest.mark.asyncio
    async def test_skips_when_no_model_provider(self):
        """Should return early when model_provider is not configured."""
        component = _make_component(model_provider=None)

        with patch(
            "solace_agent_mesh.common.sac.sam_component_base.start_model_listener"
        ) as mock_start:
            await component._start_model_listener()
            mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_start_model_listener_with_provider(self):
        """Should call start_model_listener when model_provider is configured."""
        component = _make_component(model_provider=["general"], lazy=True)
        mock_litellm = MagicMock(spec=LiteLlm)

        with patch.object(
            component, "get_lite_llm_model", return_value=mock_litellm
        ):
            with patch(
                "solace_agent_mesh.common.sac.sam_component_base.start_model_listener",
                new_callable=AsyncMock,
            ) as mock_start:
                await component._start_model_listener()
                mock_start.assert_awaited_once_with(
                    mock_litellm, component, "general"
                )

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self):
        """Should log warning and not raise when start_model_listener fails."""
        component = _make_component(model_provider=["general"], lazy=True)

        with patch.object(
            component, "get_lite_llm_model", side_effect=RuntimeError("fail")
        ):
            # Should not raise
            await component._start_model_listener()
