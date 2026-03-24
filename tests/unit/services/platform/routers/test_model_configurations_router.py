"""Unit tests for model_configurations_router helpers and endpoint event emission.

Tests:
- _emit_model_config_update publishes on both ID and alias topics
- POST /models emits events after create
- PUT /models/{alias} emits events after update
- DELETE /models/{alias} emits events after delete
"""

from unittest.mock import Mock, patch, AsyncMock

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
    """Tests for POST /models endpoint event emission."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_emits_update_after_create(self, mock_emit):
        """Emits config update event after successful create."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            create_model,
        )
        from solace_agent_mesh.services.platform.api.routers.dto.requests import (
            ModelConfigurationCreateRequest,
        )

        request = ModelConfigurationCreateRequest(
            alias="my-model",
            provider="openai",
            model_name="gpt-4",
        )

        mock_service = Mock()
        created_config = Mock()
        created_config.id = "uuid-123"
        created_config.alias = "my-model"
        mock_service.create.return_value = created_config

        raw_config = {"model": "gpt-4", "api_key": "sk-123"}
        mock_service.get_by_alias.return_value = raw_config

        mock_component = Mock()
        mock_user = {"id": "user-1"}

        result = await create_model(
            request=request,
            _=None,
            db=Mock(),
            user=mock_user,
            service=mock_service,
            component=mock_component,
        )

        mock_service.create.assert_called_once()
        mock_service.get_by_alias.assert_called_once_with(
            mock_service.create.call_args[0][0], "my-model", raw=True
        )
        mock_emit.assert_called_once_with(
            mock_component, "uuid-123", "my-model", raw_config
        )


class TestUpdateModelEndpoint:
    """Tests for PUT /models/{alias} endpoint event emission."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_emits_update_after_update(self, mock_emit):
        """Emits config update event after successful update."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            update_model,
        )
        from solace_agent_mesh.services.platform.api.routers.dto.requests import (
            ModelConfigurationUpdateRequest,
        )

        request = ModelConfigurationUpdateRequest(
            model_name="claude-3",
        )

        mock_service = Mock()
        updated_config = Mock()
        updated_config.id = "uuid-456"
        updated_config.alias = "my-alias"
        mock_service.update.return_value = updated_config

        raw_config = {"model": "claude-3", "api_key": "sk-456"}
        mock_service.get_by_alias.return_value = raw_config

        mock_component = Mock()
        mock_user = {"id": "user-1"}

        result = await update_model(
            alias="my-alias",
            request=request,
            _=None,
            db=Mock(),
            user=mock_user,
            service=mock_service,
            component=mock_component,
        )

        mock_service.update.assert_called_once()
        mock_emit.assert_called_once_with(
            mock_component, "uuid-456", "my-alias", raw_config
        )


class TestDeleteModelEndpoint:
    """Tests for DELETE /models/{alias} endpoint event emission."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_emits_update_with_none_after_delete(self, mock_emit):
        """Emits config update with None model_config after delete."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            delete_model,
        )

        mock_service = Mock()
        existing_config = Mock()
        existing_config.id = "uuid-789"
        mock_service.get_by_alias.return_value = existing_config

        mock_component = Mock()
        mock_user = {"id": "user-1"}

        await delete_model(
            alias="my-alias",
            _=None,
            db=Mock(),
            user=mock_user,
            service=mock_service,
            component=mock_component,
        )

        mock_service.get_by_alias.assert_called_once()
        mock_service.delete.assert_called_once()
        mock_emit.assert_called_once_with(
            mock_component, "uuid-789", "my-alias", None
        )
