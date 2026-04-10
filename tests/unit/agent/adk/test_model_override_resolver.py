"""Unit tests for ModelOverrideResolver and ModelOverrideResolverReceiver."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from solace_agent_mesh.agent.adk.model_override_resolver import (
    ModelOverrideResolver,
    ModelOverrideResolverReceiver,
)


def _make_mock_component(namespace="test/ns/", component_id="test_agent"):
    component = MagicMock()
    component.namespace = namespace
    component.get_component_id.return_value = component_id
    component._get_component_type.return_value = "agent"
    component.publish_a2a_message = MagicMock()
    component.log_identifier = "[MockComponent]"
    component.get_app.return_value = None
    return component


def _make_resolver_no_setup(component=None):
    """Create a resolver without running setup (skips internal flow creation)."""
    resolver = ModelOverrideResolver(component or _make_mock_component())
    resolver._setup_complete = True
    return resolver


def _make_receiver(resolver):
    with patch(
        "solace_agent_mesh.agent.adk.model_override_resolver.ComponentBase.__init__"
    ):
        receiver = object.__new__(ModelOverrideResolverReceiver)
        receiver.log_identifier = "[TestReceiver]"
        receiver.resolver = resolver
    return receiver


class TestModelOverrideResolverResolve:
    """Test the resolve() method."""

    @pytest.mark.asyncio
    async def test_publishes_bootstrap_request(self):
        component = _make_mock_component(namespace="myns/", component_id="agent1")
        resolver = _make_resolver_no_setup(component)

        async def complete_after_publish():
            await asyncio.sleep(0.01)
            resolver.complete_pending("my-alias", {"model": "openai/gpt-4o", "api_key": "sk-test"})

        asyncio.get_event_loop().create_task(complete_after_publish())
        result = await resolver.resolve("my-alias", timeout=2.0)

        component.publish_a2a_message.assert_called_once()
        call_kwargs = component.publish_a2a_message.call_args[1]
        assert call_kwargs["payload"]["model_id"] == "my-alias"
        assert call_kwargs["payload"]["component_type"] == "override_resolver"
        assert call_kwargs["topic"] == "myns/configuration/model/bootstrap/my-alias"
        assert "reply_to" in call_kwargs["payload"]

    @pytest.mark.asyncio
    async def test_returns_resolved_config(self):
        resolver = _make_resolver_no_setup()
        config = {"model": "anthropic/claude-3-5-sonnet", "api_key": "sk-test"}

        async def complete():
            await asyncio.sleep(0.01)
            resolver.complete_pending("test-alias", config)

        asyncio.get_event_loop().create_task(complete())
        result = await resolver.resolve("test-alias", timeout=2.0)

        assert result == config
        assert result["model"] == "anthropic/claude-3-5-sonnet"

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        resolver = _make_resolver_no_setup()
        result = await resolver.resolve("nonexistent-alias", timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_platform_returns_none(self):
        resolver = _make_resolver_no_setup()

        async def complete():
            await asyncio.sleep(0.01)
            resolver.complete_pending("unknown-alias", None)

        asyncio.get_event_loop().create_task(complete())
        result = await resolver.resolve("unknown-alias", timeout=2.0)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_setup(self):
        component = _make_mock_component()
        resolver = ModelOverrideResolver(component)
        # _setup_complete is False by default

        result = await resolver.resolve("any-alias", timeout=0.05)
        assert result is None
        component.publish_a2a_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleans_up_pending_after_resolve(self):
        resolver = _make_resolver_no_setup()

        async def complete():
            await asyncio.sleep(0.01)
            resolver.complete_pending("alias", {"model": "test"})

        asyncio.get_event_loop().create_task(complete())
        await resolver.resolve("alias", timeout=2.0)

        assert "alias" not in resolver._pending

    @pytest.mark.asyncio
    async def test_cleans_up_pending_after_timeout(self):
        resolver = _make_resolver_no_setup()
        await resolver.resolve("alias", timeout=0.05)
        assert "alias" not in resolver._pending

    @pytest.mark.asyncio
    async def test_concurrent_resolves_independent(self):
        resolver = _make_resolver_no_setup()

        async def complete_a():
            await asyncio.sleep(0.02)
            resolver.complete_pending("alias-a", {"model": "model-a"})

        async def complete_b():
            await asyncio.sleep(0.01)
            resolver.complete_pending("alias-b", {"model": "model-b"})

        asyncio.get_event_loop().create_task(complete_a())
        asyncio.get_event_loop().create_task(complete_b())

        result_a, result_b = await asyncio.gather(
            resolver.resolve("alias-a", timeout=2.0),
            resolver.resolve("alias-b", timeout=2.0),
        )

        assert result_a["model"] == "model-a"
        assert result_b["model"] == "model-b"


class TestModelOverrideResolverReceiver:
    """Test the receiver component."""

    def test_completes_pending_future(self):
        resolver = _make_resolver_no_setup()
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        resolver._pending["my-alias"] = future
        receiver = _make_receiver(resolver)

        message = MagicMock()
        data = {
            "topic": "test/ns/configuration/model/response/my-alias/override_resolver_agent1",
            "payload": {"model_config": {"model": "gpt-4o", "api_key": "sk-123"}},
        }

        receiver.invoke(message, data)

        assert future.done()
        assert future.result()["model"] == "gpt-4o"
        message.call_acknowledgements.assert_called_once()
        loop.close()

    def test_extracts_alias_from_topic(self):
        resolver = _make_resolver_no_setup()
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        resolver._pending["claude-model"] = future
        receiver = _make_receiver(resolver)

        message = MagicMock()
        data = {
            "topic": "ns/configuration/model/response/claude-model/override_resolver_comp",
            "payload": {"model_config": {"model": "anthropic/claude"}},
        }

        receiver.invoke(message, data)

        assert future.done()
        assert future.result()["model"] == "anthropic/claude"
        loop.close()

    def test_handles_no_pending_future(self):
        resolver = _make_resolver_no_setup()
        receiver = _make_receiver(resolver)

        message = MagicMock()
        data = {
            "topic": "ns/configuration/model/response/unknown/override_resolver_comp",
            "payload": {"model_config": {"model": "test"}},
        }

        receiver.invoke(message, data)
        message.call_acknowledgements.assert_called_once()

    def test_nacks_on_exception(self):
        resolver = _make_resolver_no_setup()
        resolver.complete_pending = MagicMock(side_effect=RuntimeError("boom"))
        loop = asyncio.new_event_loop()
        resolver._pending["alias"] = loop.create_future()
        receiver = _make_receiver(resolver)

        message = MagicMock()
        data = {
            "topic": "ns/configuration/model/response/alias/resolver",
            "payload": {"model_config": {"model": "test"}},
        }

        with pytest.raises(RuntimeError, match="boom"):
            receiver.invoke(message, data)

        message.call_negative_acknowledgements.assert_called_once()
        loop.close()


class TestModelOverrideResolverCreateListenerFlow:
    """Test _create_listener_flow."""

    def test_raises_when_no_app(self):
        component = _make_mock_component()
        component.get_app.return_value = None
        resolver = ModelOverrideResolver(component)

        with pytest.raises(RuntimeError, match="Main app or connector not available"):
            resolver._create_listener_flow()

    def test_raises_when_no_broker_config(self):
        component = _make_mock_component()
        mock_app = MagicMock()
        mock_app.connector = MagicMock()
        mock_app.app_info = {"broker": {}}
        component.get_app.return_value = mock_app
        resolver = ModelOverrideResolver(component)

        with pytest.raises(ValueError, match="Broker configuration not found"):
            resolver._create_listener_flow()

    def test_raises_when_internal_app_creation_fails(self):
        component = _make_mock_component()
        mock_app = MagicMock()
        mock_app.connector = MagicMock()
        mock_app.app_info = {"broker": {"host": "localhost"}}
        mock_app.connector.create_internal_app.return_value = None
        component.get_app.return_value = mock_app
        resolver = ModelOverrideResolver(component)

        with pytest.raises(RuntimeError, match="Failed to create internal app"):
            resolver._create_listener_flow()


class TestModelOverrideResolverCleanup:
    """Test cleanup."""

    def test_cancels_pending_futures(self):
        resolver = _make_resolver_no_setup()
        loop = asyncio.new_event_loop()
        future = loop.create_future()
        resolver._pending["alias"] = future

        resolver.cleanup()

        assert future.cancelled()
        assert len(resolver._pending) == 0
        assert resolver._setup_complete is False
        loop.close()

    def test_cleans_up_internal_app(self):
        resolver = _make_resolver_no_setup()
        mock_app = MagicMock()
        resolver._internal_app = mock_app

        resolver.cleanup()

        mock_app.cleanup.assert_called_once()
        assert resolver._internal_app is None

    def test_cleanup_when_no_internal_app(self):
        resolver = _make_resolver_no_setup()
        resolver.cleanup()
        assert resolver._internal_app is None
