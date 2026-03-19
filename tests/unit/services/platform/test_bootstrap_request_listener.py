"""Unit tests for BootstrapRequestListenerComponent.

Tests:
- Successful bootstrap request handling (lookup + publish + ack)
- Missing model_id or reply_to fields
- Model not found in DB (publishes None config)
- Exception handling (negative ack)
"""

from unittest.mock import Mock, patch, MagicMock

import pytest


class TestBootstrapRequestListenerInvoke:
    """Tests for BootstrapRequestListenerComponent.invoke."""

    def _make_component(self, platform_component=None):
        """Create a BootstrapRequestListenerComponent with mocked dependencies."""
        if platform_component is None:
            platform_component = Mock()

        with patch(
            "solace_agent_mesh.services.platform.components.dynamic_model_provider_listener.ComponentBase.__init__"
        ):
            from solace_agent_mesh.services.platform.components.dynamic_model_provider_listener import (
                BootstrapRequestListenerComponent,
            )

            comp = BootstrapRequestListenerComponent.__new__(BootstrapRequestListenerComponent)
            comp.platform_component = platform_component
            comp.log_identifier = "[test]"
            return comp

    def test_successful_bootstrap_request(self):
        """Looks up model, publishes response, and acknowledges message."""
        platform_component = Mock()
        comp = self._make_component(platform_component)

        mock_config = {"model": "gpt-4", "api_key": "sk-123"}
        comp._get_model_config = Mock(return_value=mock_config)

        message = Mock()
        data = {
            "topic": "test/topic",
            "payload": {
                "model_id": "my-model",
                "reply_to": "reply/topic/123",
            },
        }

        comp.invoke(message, data)

        comp._get_model_config.assert_called_once_with("my-model")
        platform_component.publish_a2a_message.assert_called_once_with(
            payload={"model_config": mock_config},
            topic="reply/topic/123",
        )
        message.call_acknowledgements.assert_called_once()

    def test_model_not_found_publishes_none(self):
        """When model is not in DB, publishes model_config: None."""
        platform_component = Mock()
        comp = self._make_component(platform_component)
        comp._get_model_config = Mock(return_value=None)

        message = Mock()
        data = {
            "topic": "test/topic",
            "payload": {
                "model_id": "nonexistent",
                "reply_to": "reply/topic/456",
            },
        }

        comp.invoke(message, data)

        platform_component.publish_a2a_message.assert_called_once_with(
            payload={"model_config": None},
            topic="reply/topic/456",
        )
        message.call_acknowledgements.assert_called_once()

    def test_missing_model_id_acks_and_returns(self):
        """Missing model_id: acknowledges message but does not publish."""
        platform_component = Mock()
        comp = self._make_component(platform_component)

        message = Mock()
        data = {
            "topic": "test/topic",
            "payload": {"reply_to": "reply/topic"},
        }

        result = comp.invoke(message, data)

        assert result is None
        platform_component.publish_a2a_message.assert_not_called()
        message.call_acknowledgements.assert_called_once()

    def test_missing_reply_to_acks_and_returns(self):
        """Missing reply_to: acknowledges message but does not publish."""
        platform_component = Mock()
        comp = self._make_component(platform_component)

        message = Mock()
        data = {
            "topic": "test/topic",
            "payload": {"model_id": "some-model"},
        }

        result = comp.invoke(message, data)

        assert result is None
        platform_component.publish_a2a_message.assert_not_called()
        message.call_acknowledgements.assert_called_once()

    def test_empty_payload_acks_and_returns(self):
        """Empty payload: acknowledges and returns without publishing."""
        platform_component = Mock()
        comp = self._make_component(platform_component)

        message = Mock()
        data = {"topic": "test/topic", "payload": {}}

        result = comp.invoke(message, data)

        assert result is None
        platform_component.publish_a2a_message.assert_not_called()
        message.call_acknowledgements.assert_called_once()

    def test_exception_calls_negative_ack(self):
        """On exception, calls negative acknowledgement and re-raises."""
        platform_component = Mock()
        comp = self._make_component(platform_component)
        comp._get_model_config = Mock(side_effect=RuntimeError("DB error"))

        message = Mock()
        data = {
            "topic": "test/topic",
            "payload": {
                "model_id": "my-model",
                "reply_to": "reply/topic",
            },
        }

        with pytest.raises(RuntimeError, match="DB error"):
            comp.invoke(message, data)

        message.call_negative_acknowledgements.assert_called_once()


class TestBootstrapRequestListenerGetModelConfig:
    """Tests for BootstrapRequestListenerComponent._get_model_config."""

    def _make_component(self):
        """Create component with mocked base class."""
        with patch(
            "solace_agent_mesh.services.platform.components.dynamic_model_provider_listener.ComponentBase.__init__"
        ):
            from solace_agent_mesh.services.platform.components.dynamic_model_provider_listener import (
                BootstrapRequestListenerComponent,
            )

            comp = BootstrapRequestListenerComponent.__new__(BootstrapRequestListenerComponent)
            comp.platform_component = Mock()
            comp.log_identifier = "[test]"
            return comp

    @patch("solace_agent_mesh.services.platform.api.dependencies.PlatformSessionLocal")
    @patch("solace_agent_mesh.services.platform.services.ModelConfigService")
    def test_get_model_config_calls_service(self, MockService, MockSessionLocal):
        """_get_model_config creates a DB session, calls service, and closes session."""
        comp = self._make_component()

        mock_db = Mock()
        MockSessionLocal.return_value = mock_db

        expected_config = {"model": "gpt-4"}
        MockService.return_value.get_by_alias_or_id.return_value = expected_config

        result = comp._get_model_config("my-model")

        assert result == expected_config
        MockService.return_value.get_by_alias_or_id.assert_called_once_with(
            mock_db, "my-model", raw=True
        )
        mock_db.close.assert_called_once()

    @patch("solace_agent_mesh.services.platform.api.dependencies.PlatformSessionLocal")
    @patch("solace_agent_mesh.services.platform.services.ModelConfigService")
    def test_get_model_config_closes_session_on_error(self, MockService, MockSessionLocal):
        """DB session is closed even when service raises."""
        comp = self._make_component()

        mock_db = Mock()
        MockSessionLocal.return_value = mock_db

        MockService.return_value.get_by_alias_or_id.side_effect = RuntimeError("DB fail")

        with pytest.raises(RuntimeError):
            comp._get_model_config("my-model")

        mock_db.close.assert_called_once()
