"""Unit tests for model_configurations_router new endpoints and helpers.

Tests:
- _emit_model_config_update publishes on both ID and alias topics
- POST /models emits events and returns 501
- PUT /models/{alias} emits events and returns 501
"""

from unittest.mock import Mock, patch, call

import pytest

from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
    _emit_model_config_update,
)


class TestEmitModelConfigUpdate:
    """Tests for the _emit_model_config_update helper."""

    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router.get_model_config_update_topic"
    )
    def test_publishes_on_id_and_alias_topics(self, mock_get_topic):
        """Emits two messages: one by model ID, one by alias."""
        mock_get_topic.side_effect = lambda ns, identifier: f"{ns}/config/{identifier}"
        component = Mock()
        component.namespace = "test-ns"

        model_config = {"model": "gpt-4", "api_key": "sk-123"}

        _emit_model_config_update(component, "uuid-123", "my-alias", model_config)

        assert mock_get_topic.call_count == 2
        mock_get_topic.assert_any_call("test-ns", "uuid-123")
        mock_get_topic.assert_any_call("test-ns", "my-alias")

        assert component.publish_a2a_message.call_count == 2
        component.publish_a2a_message.assert_any_call(
            payload={"model_config": model_config},
            topic="test-ns/config/uuid-123",
        )
        component.publish_a2a_message.assert_any_call(
            payload={"model_config": model_config},
            topic="test-ns/config/my-alias",
        )

    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router.get_model_config_update_topic"
    )
    def test_publishes_none_config(self, mock_get_topic):
        """Can emit None as model_config (unconfigure signal)."""
        mock_get_topic.side_effect = lambda ns, identifier: f"{ns}/config/{identifier}"
        component = Mock()
        component.namespace = "ns"

        _emit_model_config_update(component, "id-1", "alias-1", None)

        component.publish_a2a_message.assert_any_call(
            payload={"model_config": None},
            topic="ns/config/id-1",
        )
        component.publish_a2a_message.assert_any_call(
            payload={"model_config": None},
            topic="ns/config/alias-1",
        )


class TestCreateModelEndpoint:
    """Tests for POST /models endpoint."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_emits_update_then_raises_501(self, mock_emit):
        """Emits config update when all fields present, then raises 501."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            create_model,
        )
        from fastapi import HTTPException

        body = {
            "id": "uuid-123",
            "alias": "my-model",
            "model_config": {"model": "gpt-4"},
        }
        mock_component = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await create_model(
                body=body,
                _=None,
                db=Mock(),
                service=Mock(),
                component=mock_component,
            )

        assert exc_info.value.status_code == 501
        mock_emit.assert_called_once_with(
            mock_component, "uuid-123", "my-model", {"model": "gpt-4"}
        )

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_skips_emit_when_fields_missing(self, mock_emit):
        """Does not emit when model_config, id, or alias is missing."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            create_model,
        )
        from fastapi import HTTPException

        # Missing model_config
        body = {"id": "uuid-123", "alias": "my-model"}

        with pytest.raises(HTTPException) as exc_info:
            await create_model(
                body=body, _=None, db=Mock(), service=Mock(), component=Mock()
            )

        assert exc_info.value.status_code == 501
        mock_emit.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_skips_emit_when_id_empty(self, mock_emit):
        """Does not emit when id is empty string."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            create_model,
        )
        from fastapi import HTTPException

        body = {"id": "", "alias": "my-model", "model_config": {"model": "gpt-4"}}

        with pytest.raises(HTTPException):
            await create_model(
                body=body, _=None, db=Mock(), service=Mock(), component=Mock()
            )

        mock_emit.assert_not_called()


class TestUpdateModelEndpoint:
    """Tests for PUT /models/{alias} endpoint."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_emits_update_then_raises_501(self, mock_emit):
        """Emits config update with alias from path, then raises 501."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            update_model,
        )
        from fastapi import HTTPException

        body = {"id": "uuid-456", "model_config": {"model": "claude-3"}}
        mock_component = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await update_model(
                alias="my-alias",
                body=body,
                _=None,
                service=Mock(),
                db=Mock(),
                component=mock_component,
            )

        assert exc_info.value.status_code == 501
        mock_emit.assert_called_once_with(
            mock_component, "uuid-456", "my-alias", {"model": "claude-3"}
        )

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_skips_emit_when_model_config_missing(self, mock_emit):
        """Does not emit when model_config is missing from body."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            update_model,
        )
        from fastapi import HTTPException

        body = {"id": "uuid-456"}

        with pytest.raises(HTTPException):
            await update_model(
                alias="my-alias",
                body=body,
                _=None,
                service=Mock(),
                db=Mock(),
                component=Mock(),
            )

        mock_emit.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_skips_emit_when_id_missing(self, mock_emit):
        """Does not emit when id is missing (defaults to empty string)."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            update_model,
        )
        from fastapi import HTTPException

        body = {"model_config": {"model": "gpt-4"}}

        with pytest.raises(HTTPException):
            await update_model(
                alias="my-alias",
                body=body,
                _=None,
                service=Mock(),
                db=Mock(),
                component=Mock(),
            )

        mock_emit.assert_not_called()
