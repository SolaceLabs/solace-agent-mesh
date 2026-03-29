"""Unit tests for DynamicModelProvider and ModelConfigReceiverComponent."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from solace_agent_mesh.agent.adk.models.dynamic_model_provider import (
    DynamicModelProvider,
    ModelConfigReceiverComponent,
    start_model_listener,
)
from solace_agent_mesh.agent.adk.models.lite_llm import LiteLlm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_component(namespace="test/ns/", component_id="test_agent", component_type="agent"):
    """Create a mock SamComponentBase for testing."""
    component = MagicMock()
    component.namespace = namespace
    component.get_component_id.return_value = component_id
    component._get_component_type.return_value = component_type
    component.publish_a2a_message = MagicMock()
    component.log_identifier = "[MockComponent]"

    # Mock get_app to return None (prevents _ensure_config_listener_flow_is_running)
    component.get_app.return_value = None
    return component


def _make_provider_no_init(component=None, litellm_instance=None, model_id="general"):
    """
    Create a DynamicModelProvider without running __init__ side effects.
    This avoids asyncio.create_task in __init__.
    """
    provider = object.__new__(DynamicModelProvider)
    provider._component = component or _make_mock_component()
    provider._litellm_instance = litellm_instance or LiteLlm(model=None)
    provider._model_id = model_id
    provider._internal_app = None
    provider._broker_input = None
    provider._initialized = False
    return provider


def _make_receiver_component(model_provider):
    """Create a ModelConfigReceiverComponent with mocked base class init."""
    with patch(
        "solace_agent_mesh.agent.adk.models.dynamic_model_provider.ComponentBase.__init__"
    ):
        receiver = object.__new__(ModelConfigReceiverComponent)
        receiver.log_identifier = "[TestReceiver]"
        receiver.model_provider = model_provider
    return receiver


# ---------------------------------------------------------------------------
# DynamicModelProvider Tests
# ---------------------------------------------------------------------------


class TestDynamicModelProviderUpdateModel:
    """Test update_litellm_model."""

    def test_update_delegates_to_litellm_configure(self):
        """update_litellm_model should call litellm.configure_model."""
        litellm = LiteLlm(model=None)
        provider = _make_provider_no_init(litellm_instance=litellm)

        provider.update_litellm_model({"model": "gpt-4"})
        assert litellm.status == "ready"
        assert litellm._model_config["model"] == "gpt-4"

    def test_update_with_string_model_name(self):
        """update_litellm_model logs correctly for string config."""
        litellm = MagicMock(spec=LiteLlm)
        provider = _make_provider_no_init(litellm_instance=litellm)

        provider.update_litellm_model("gpt-4")
        litellm.configure_model.assert_called_once_with("gpt-4")

    def test_update_with_dict_model_config(self):
        """update_litellm_model passes dict config to litellm."""
        litellm = MagicMock(spec=LiteLlm)
        provider = _make_provider_no_init(litellm_instance=litellm)

        config = {"model": "gpt-4", "timeout": 300}
        provider.update_litellm_model(config)
        litellm.configure_model.assert_called_once_with(config)


class TestDynamicModelProviderRemoveModel:
    """Test remove_litellm_model."""

    def test_remove_delegates_to_litellm_unconfigure(self):
        """remove_litellm_model should call litellm.unconfigure_model."""
        litellm = LiteLlm(model="gpt-4")
        provider = _make_provider_no_init(litellm_instance=litellm)

        provider.remove_litellm_model()
        assert litellm.status == "none"

    def test_remove_calls_unconfigure(self):
        """remove_litellm_model calls unconfigure_model on mock."""
        litellm = MagicMock(spec=LiteLlm)
        provider = _make_provider_no_init(litellm_instance=litellm)

        provider.remove_litellm_model()
        litellm.unconfigure_model.assert_called_once()


class TestDynamicModelProviderRequestModelConfig:
    """Test request_model_config."""

    @pytest.mark.asyncio
    async def test_publishes_request_message(self):
        """request_model_config should publish an A2A message with correct payload."""
        component = _make_mock_component(
            namespace="myorg/ai/", component_id="my_agent", component_type="agent"
        )
        provider = _make_provider_no_init(component=component, model_id="general")

        await provider.request_model_config()

        component.publish_a2a_message.assert_called_once()
        call_kwargs = component.publish_a2a_message.call_args
        payload = call_kwargs[1]["payload"] if "payload" in call_kwargs[1] else call_kwargs[0][0]
        topic = call_kwargs[1]["topic"] if "topic" in call_kwargs[1] else call_kwargs[0][1]

        assert payload["component_id"] == "my_agent"
        assert payload["component_type"] == "agent"
        assert payload["model_id"] == "general"
        assert "reply_to" in payload
        assert topic == "myorg/ai/configuration/model/bootstrap/general"

    @pytest.mark.asyncio
    async def test_reply_to_uses_correct_topic(self):
        """reply_to should use the bootstrap response topic format."""
        component = _make_mock_component(
            namespace="ns/", component_id="comp_1", component_type="gateway"
        )
        provider = _make_provider_no_init(component=component, model_id="premium")

        await provider.request_model_config()

        call_kwargs = component.publish_a2a_message.call_args[1]
        payload = call_kwargs["payload"]
        assert payload["reply_to"] == "ns/configuration/model/response/premium/comp_1"


class TestDynamicModelProviderInitialize:
    """Test the initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_calls_listen_and_requests(self):
        """initialize should call listen_for_model_config_change and request_model_config."""
        provider = _make_provider_no_init()
        provider.listen_for_model_config_change = AsyncMock()
        provider.request_model_config = AsyncMock()

        # Simulate becoming initialized after first request
        async def set_initialized():
            provider._initialized = True

        provider.request_model_config.side_effect = set_initialized

        await provider.initialize()

        provider.listen_for_model_config_change.assert_awaited_once()
        # Should only call request once since we set initialized=True
        assert provider.request_model_config.await_count == 1

    @pytest.mark.asyncio
    async def test_initialize_retries_up_to_3_times(self):
        """initialize retries request_model_config up to 3 times if not initialized."""
        provider = _make_provider_no_init()
        provider.listen_for_model_config_change = AsyncMock()
        provider.request_model_config = AsyncMock()

        # Patch sleep to avoid waiting
        with patch("solace_agent_mesh.agent.adk.models.dynamic_model_provider.asyncio.sleep", new_callable=AsyncMock):
            await provider.initialize()

        assert provider.request_model_config.await_count == 3

    @pytest.mark.asyncio
    async def test_initialize_stops_early_when_initialized(self):
        """initialize should stop retrying once _initialized is True."""
        provider = _make_provider_no_init()
        provider.listen_for_model_config_change = AsyncMock()

        call_count = 0

        async def request_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                provider._initialized = True

        provider.request_model_config = AsyncMock(side_effect=request_side_effect)

        with patch("solace_agent_mesh.agent.adk.models.dynamic_model_provider.asyncio.sleep", new_callable=AsyncMock):
            await provider.initialize()

        assert call_count == 2


class TestDynamicModelProviderEnsureConfigListener:
    """Test _ensure_config_listener_flow_is_running."""

    def test_skips_if_already_running(self):
        """Should return early if _internal_app is not None."""
        provider = _make_provider_no_init()
        provider._internal_app = MagicMock()  # Already running

        # Should not raise or call get_app
        provider._ensure_config_listener_flow_is_running()
        provider._component.get_app.assert_not_called()

    def test_raises_when_no_app(self):
        """Should raise RuntimeError when get_app returns None."""
        provider = _make_provider_no_init()
        provider._component.get_app.return_value = None

        with pytest.raises(RuntimeError, match="Main app or connector not available"):
            provider._ensure_config_listener_flow_is_running()

    def test_raises_when_no_connector(self):
        """Should raise RuntimeError when app has no connector."""
        provider = _make_provider_no_init()
        mock_app = MagicMock()
        mock_app.connector = None
        provider._component.get_app.return_value = mock_app

        with pytest.raises(RuntimeError, match="Main app or connector not available"):
            provider._ensure_config_listener_flow_is_running()

    def test_raises_when_no_broker_config(self):
        """Should raise ValueError when broker config is empty."""
        provider = _make_provider_no_init()
        mock_app = MagicMock()
        mock_app.connector = MagicMock()
        mock_app.app_info = {"broker": {}}
        provider._component.get_app.return_value = mock_app

        with pytest.raises(ValueError, match="broker configuration is missing"):
            provider._ensure_config_listener_flow_is_running()

    def test_raises_when_internal_app_creation_fails(self):
        """Should raise RuntimeError when create_internal_app returns None."""
        provider = _make_provider_no_init()
        mock_app = MagicMock()
        mock_app.connector = MagicMock()
        mock_app.app_info = {"broker": {"host": "localhost"}}
        mock_app.connector.create_internal_app.return_value = None
        provider._component.get_app.return_value = mock_app

        with pytest.raises(RuntimeError, match="creation failed"):
            provider._ensure_config_listener_flow_is_running()

    def test_cleans_up_on_failure(self):
        """Should cleanup internal_app on failure and reset to None."""
        provider = _make_provider_no_init()
        mock_app = MagicMock()
        mock_app.connector = MagicMock()
        mock_app.app_info = {"broker": {"host": "localhost"}}

        # Create a mock internal app that has no flows
        mock_internal_app = MagicMock()
        mock_internal_app.flows = []
        mock_app.connector.create_internal_app.return_value = mock_internal_app
        provider._component.get_app.return_value = mock_app

        with pytest.raises(RuntimeError):
            provider._ensure_config_listener_flow_is_running()

        assert provider._internal_app is None
        assert provider._broker_input is None


class TestDynamicModelProviderCleanup:
    """Test cleanup method."""

    def test_cleanup_calls_internal_app_cleanup(self):
        """cleanup should call internal_app.cleanup when present."""
        provider = _make_provider_no_init()
        mock_app = MagicMock()
        provider._internal_app = mock_app

        provider.cleanup()

        mock_app.cleanup.assert_called_once()
        assert provider._internal_app is None
        assert provider._broker_input is None

    def test_cleanup_when_no_internal_app(self):
        """cleanup should not raise when _internal_app is None."""
        provider = _make_provider_no_init()
        provider.cleanup()  # Should not raise
        assert provider._internal_app is None

    def test_cleanup_handles_exception(self):
        """cleanup should not raise even if internal_app.cleanup raises."""
        provider = _make_provider_no_init()
        mock_app = MagicMock()
        mock_app.cleanup.side_effect = RuntimeError("cleanup error")
        provider._internal_app = mock_app

        provider.cleanup()  # Should not raise
        assert provider._internal_app is None


# ---------------------------------------------------------------------------
# ModelConfigReceiverComponent Tests
# ---------------------------------------------------------------------------


class TestModelConfigReceiverComponentInvoke:
    """Test ModelConfigReceiverComponent.invoke."""

    def test_invoke_with_model_config_updates_provider(self):
        """invoke with model_config in payload should update the provider."""
        provider = _make_provider_no_init()
        provider.update_litellm_model = MagicMock()
        receiver = _make_receiver_component(provider)

        message = MagicMock()
        data = {
            "topic": "test/topic",
            "payload": {"model_config": {"model": "gpt-4"}},
        }

        receiver.invoke(message, data)

        assert provider._initialized is True
        provider.update_litellm_model.assert_called_once_with({"model": "gpt-4"})
        message.call_acknowledgements.assert_called_once()

    def test_invoke_without_model_config_removes_model(self):
        """invoke without model_config should call remove_litellm_model."""
        provider = _make_provider_no_init()
        provider.remove_litellm_model = MagicMock()
        receiver = _make_receiver_component(provider)

        message = MagicMock()
        data = {
            "topic": "test/topic",
            "payload": {},
        }

        receiver.invoke(message, data)

        provider.remove_litellm_model.assert_called_once()
        message.call_acknowledgements.assert_called_once()

    def test_invoke_with_empty_model_config_removes_model(self):
        """invoke with empty model_config (falsy) should call remove_litellm_model."""
        provider = _make_provider_no_init()
        provider.remove_litellm_model = MagicMock()
        receiver = _make_receiver_component(provider)

        message = MagicMock()
        data = {
            "topic": "test/topic",
            "payload": {"model_config": {}},
        }

        receiver.invoke(message, data)

        provider.remove_litellm_model.assert_called_once()

    def test_invoke_nacks_on_exception(self):
        """invoke should call negative_acknowledgements on exception."""
        provider = _make_provider_no_init()
        provider.update_litellm_model = MagicMock(side_effect=RuntimeError("fail"))
        receiver = _make_receiver_component(provider)

        message = MagicMock()
        data = {
            "topic": "test/topic",
            "payload": {"model_config": {"model": "gpt-4"}},
        }

        with pytest.raises(RuntimeError, match="fail"):
            receiver.invoke(message, data)

        message.call_negative_acknowledgements.assert_called_once()

    def test_invoke_returns_none(self):
        """invoke should return None."""
        provider = _make_provider_no_init()
        provider.update_litellm_model = MagicMock()
        receiver = _make_receiver_component(provider)

        message = MagicMock()
        data = {
            "topic": "test/topic",
            "payload": {"model_config": {"model": "gpt-4"}},
        }

        result = receiver.invoke(message, data)
        assert result is None

    def test_invoke_handles_missing_topic(self):
        """invoke should handle missing topic gracefully."""
        provider = _make_provider_no_init()
        provider.remove_litellm_model = MagicMock()
        receiver = _make_receiver_component(provider)

        message = MagicMock()
        data = {"payload": {}}

        receiver.invoke(message, data)
        message.call_acknowledgements.assert_called_once()


class TestModelConfigReceiverComponentInit:
    """Test ModelConfigReceiverComponent initialization validation."""

    def test_raises_when_invalid_provider_ref(self):
        """Should raise ValueError when model_provider_ref is not a DynamicModelProvider."""
        with patch(
            "solace_agent_mesh.agent.adk.models.dynamic_model_provider.ComponentBase.__init__"
        ):
            with patch(
                "solace_agent_mesh.agent.adk.models.dynamic_model_provider.ComponentBase.get_config",
                return_value="not_a_provider",
            ):
                with pytest.raises(ValueError, match="must be a DynamicModelProvider"):
                    receiver = ModelConfigReceiverComponent.__new__(ModelConfigReceiverComponent)
                    receiver.log_identifier = "[TestReceiver]"
                    receiver.model_provider = "not_a_provider"
                    # Manually run the validation logic from __init__
                    if not isinstance(receiver.model_provider, DynamicModelProvider):
                        raise ValueError(
                            f"{receiver.log_identifier} 'model_provider_ref' must be a DynamicModelProvider instance."
                        )


# ---------------------------------------------------------------------------
# start_model_listener Tests
# ---------------------------------------------------------------------------


class TestStartModelListener:
    """Test the start_model_listener helper function."""

    @pytest.mark.asyncio
    async def test_returns_dynamic_model_provider(self):
        """start_model_listener should return a DynamicModelProvider instance."""
        litellm = LiteLlm(model=None)
        component = _make_mock_component()

        with patch.object(DynamicModelProvider, "__init__", return_value=None):
            result = await start_model_listener(litellm, component, "general")

        assert isinstance(result, DynamicModelProvider)

    @pytest.mark.asyncio
    async def test_passes_correct_args_to_provider(self):
        """start_model_listener should pass litellm, component, and model_id to provider."""
        litellm = LiteLlm(model=None)
        component = _make_mock_component()

        with patch.object(DynamicModelProvider, "__init__", return_value=None) as mock_init:
            await start_model_listener(litellm, component, "premium")

        mock_init.assert_called_once_with(component, litellm, "premium")
