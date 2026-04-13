"""Tests for DynamicModelProvider.resolve() — one-shot model alias resolution."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch


def _make_provider():
    """Create a DynamicModelProvider with mocked dependencies."""
    from solace_agent_mesh.agent.adk.models.dynamic_model_provider import (
        DynamicModelProvider,
    )

    component = MagicMock()
    component.log_identifier = "[TestComponent]"
    component.namespace = "test/"
    component.get_component_id.return_value = "agent_1"
    component._get_component_type.return_value = "agent"
    component._async_loop = asyncio.get_event_loop()

    litellm = MagicMock()

    with patch.object(DynamicModelProvider, "initialize", return_value=asyncio.sleep(0)):
        provider = DynamicModelProvider(component, litellm, "default-model")
        provider._internal_app = MagicMock()

    return provider, component


class TestResolve:
    @pytest.mark.asyncio
    async def test_returns_resolved_config(self):
        provider, component = _make_provider()
        config = {"model": "openai/gpt-4o", "api_key": "sk-test"}

        async def complete_after_publish(*args, **kwargs):
            await asyncio.sleep(0.01)
            provider.complete_pending_resolve("my-alias", config)

        component.publish_a2a_message.side_effect = lambda **kw: asyncio.ensure_future(
            complete_after_publish()
        )

        result = await provider.resolve("my-alias", timeout=2.0)
        assert result == config
        component.publish_a2a_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        provider, _ = _make_provider()
        result = await provider.resolve("unknown", timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_platform_returns_none(self):
        provider, component = _make_provider()

        async def complete_with_none(*args, **kwargs):
            await asyncio.sleep(0.01)
            provider.complete_pending_resolve("my-alias", None)

        component.publish_a2a_message.side_effect = lambda **kw: asyncio.ensure_future(
            complete_with_none()
        )

        result = await provider.resolve("my-alias", timeout=2.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_listener_not_running(self):
        provider, _ = _make_provider()
        provider._internal_app = None
        result = await provider.resolve("my-alias", timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_cleans_up_pending_after_resolve(self):
        provider, component = _make_provider()

        async def complete(*args, **kwargs):
            await asyncio.sleep(0.01)
            provider.complete_pending_resolve("alias", {"model": "x"})

        component.publish_a2a_message.side_effect = lambda **kw: asyncio.ensure_future(
            complete()
        )

        await provider.resolve("alias", timeout=2.0)
        assert "alias" not in provider._pending_resolves

    @pytest.mark.asyncio
    async def test_cleans_up_pending_after_timeout(self):
        provider, _ = _make_provider()
        await provider.resolve("alias", timeout=0.05)
        assert "alias" not in provider._pending_resolves

    @pytest.mark.asyncio
    async def test_concurrent_resolves_deduped(self):
        """Two concurrent resolves for the same alias should only publish once."""
        provider, component = _make_provider()
        config = {"model": "openai/gpt-4o"}

        async def complete_delayed():
            await asyncio.sleep(0.05)
            provider.complete_pending_resolve("alias", config)

        component.publish_a2a_message.side_effect = lambda **kw: asyncio.ensure_future(
            complete_delayed()
        )

        r1, r2 = await asyncio.gather(
            provider.resolve("alias", timeout=2.0),
            provider.resolve("alias", timeout=2.0),
        )

        assert r1 == config
        assert r2 == config
        assert component.publish_a2a_message.call_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_resolves_different_aliases_independent(self):
        provider, component = _make_provider()

        async def complete_both():
            await asyncio.sleep(0.01)
            provider.complete_pending_resolve("a", {"model": "model-a"})
            provider.complete_pending_resolve("b", {"model": "model-b"})

        component.publish_a2a_message.side_effect = lambda **kw: asyncio.ensure_future(
            complete_both()
        )

        r1, r2 = await asyncio.gather(
            provider.resolve("a", timeout=2.0),
            provider.resolve("b", timeout=2.0),
        )

        assert r1 == {"model": "model-a"}
        assert r2 == {"model": "model-b"}
        assert component.publish_a2a_message.call_count == 2


class TestCompletePendingResolve:
    @pytest.mark.asyncio
    async def test_completes_future_via_call_soon_threadsafe(self):
        provider, component = _make_provider()
        loop = asyncio.get_running_loop()
        component._async_loop = loop
        future = loop.create_future()

        with provider._resolve_lock:
            provider._pending_resolves["alias"] = [future]

        provider.complete_pending_resolve("alias", {"model": "x"})

        # call_soon_threadsafe schedules on the event loop; yield to let it run
        await asyncio.sleep(0.01)
        assert future.result() == {"model": "x"}
        assert "alias" not in provider._pending_resolves

    @pytest.mark.asyncio
    async def test_no_pending_is_noop(self):
        provider, _ = _make_provider()
        provider.complete_pending_resolve("nonexistent", {"model": "x"})


class TestReceiverRouting:
    def test_own_model_updates_litellm(self):
        from solace_agent_mesh.agent.adk.models.dynamic_model_provider import (
            ModelConfigReceiverComponent,
        )

        provider = MagicMock()
        provider._model_id = "my-model"

        receiver = ModelConfigReceiverComponent.__new__(ModelConfigReceiverComponent)
        receiver.model_provider = provider
        receiver.log_identifier = "[TestReceiver]"

        message = MagicMock()
        data = {
            "topic": "test/configuration/model/response/my-model/agent_1",
            "payload": {"model_config": {"model": "openai/gpt-4o"}},
        }

        receiver.invoke(message, data)

        provider.mark_initialized.assert_called_once()
        provider.update_litellm_model.assert_called_once_with({"model": "openai/gpt-4o"})
        provider.complete_pending_resolve.assert_not_called()
        message.call_acknowledgements.assert_called_once()

    def test_different_model_routes_to_resolve(self):
        from solace_agent_mesh.agent.adk.models.dynamic_model_provider import (
            ModelConfigReceiverComponent,
        )

        provider = MagicMock()
        provider._model_id = "my-model"

        receiver = ModelConfigReceiverComponent.__new__(ModelConfigReceiverComponent)
        receiver.model_provider = provider
        receiver.log_identifier = "[TestReceiver]"

        message = MagicMock()
        data = {
            "topic": "test/configuration/model/response/other-alias/agent_1",
            "payload": {"model_config": {"model": "anthropic/claude-3-5-sonnet"}},
        }

        receiver.invoke(message, data)

        provider.update_litellm_model.assert_not_called()
        provider.complete_pending_resolve.assert_called_once_with(
            "other-alias", {"model": "anthropic/claude-3-5-sonnet"}
        )
        message.call_acknowledgements.assert_called_once()


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cancels_pending_futures(self):
        provider, _ = _make_provider()
        loop = asyncio.get_running_loop()
        f1 = loop.create_future()
        f2 = loop.create_future()
        provider._pending_resolves = {"a": [f1], "b": [f2]}

        provider.cleanup()

        assert f1.cancelled()
        assert f2.cancelled()
        assert provider._pending_resolves == {}
