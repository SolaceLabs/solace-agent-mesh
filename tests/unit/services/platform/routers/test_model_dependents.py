"""Unit tests for model dependents endpoint and handler hook.

Tests:
- GET /models/{alias}/dependents returns empty list when enterprise not installed
- GET /models/{alias}/dependents returns dependents when enterprise is available
- DELETE /models/{alias} calls dependents_handler.undeploy_dependents before delete
- ModelDependentsHandler default is a no-op
- set_model_dependents_handler / get_model_dependents_handler registration
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from solace_agent_mesh.services.platform.api.dependencies import (
    ModelDependentsHandler,
    get_model_dependents_handler,
    set_model_dependents_handler,
)


class TestModelDependentsHandler:
    """Tests for the default ModelDependentsHandler (no-op)."""

    @pytest.mark.asyncio
    async def test_default_handler_returns_empty_list(self):
        handler = ModelDependentsHandler()
        result = await handler.undeploy_dependents("general", "uuid-1", Mock())
        assert result == []

    @pytest.mark.asyncio
    async def test_default_handler_accepts_any_args(self):
        handler = ModelDependentsHandler()
        result = await handler.undeploy_dependents("any-alias", "any-id", None)
        assert result == []


class TestHandlerRegistration:
    """Tests for set/get_model_dependents_handler."""

    def test_get_returns_default_handler(self):
        handler = get_model_dependents_handler()
        assert isinstance(handler, ModelDependentsHandler)

    def test_set_replaces_handler(self):
        original = get_model_dependents_handler()
        custom = ModelDependentsHandler()

        try:
            set_model_dependents_handler(custom)
            assert get_model_dependents_handler() is custom
        finally:
            # Restore original
            set_model_dependents_handler(original)


class TestGetModelDependentsEndpoint:
    """Tests for GET /models/{alias}/dependents."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_enterprise_not_installed(self):
        """When enterprise package is not available, returns success with empty list."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            get_model_dependents,
        )

        mock_service = Mock()
        mock_config = Mock()
        mock_config.alias = "general"
        mock_config.id = "uuid-123"
        mock_service.get_by_alias.return_value = mock_config

        mock_db = Mock()

        # Force ImportError on the enterprise import inside the function
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("solace_agent_mesh_enterprise"):
                raise ImportError("No enterprise package")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = await get_model_dependents(
                alias="general",
                _=None,
                db=mock_db,
                service=mock_service,
            )

        assert result.data == []
        mock_service.get_by_alias.assert_called_once_with(mock_db, "general")

    @pytest.mark.asyncio
    async def test_returns_dependents_when_enterprise_available(self):
        """When enterprise is available, returns dependent agents."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            get_model_dependents,
        )

        mock_service = Mock()
        mock_config = Mock()
        mock_config.alias = "general"
        mock_config.id = "uuid-123"
        mock_service.get_by_alias.return_value = mock_config

        mock_agent = Mock()
        mock_agent.id = "agent-1"
        mock_agent.name = "Test Agent"
        mock_agent.type = "standard"
        mock_agent.deployment_status = "deployed"

        mock_dependents_service_instance = Mock()
        mock_dependents_service_instance.get_dependents.return_value = [mock_agent]

        mock_dependents_service_cls = Mock(return_value=mock_dependents_service_instance)
        mock_agent_repo_cls = Mock()
        mock_deployment_repo_cls = Mock()

        with patch.dict(
            "sys.modules",
            {
                "solace_agent_mesh_enterprise": Mock(),
                "solace_agent_mesh_enterprise.platform_service": Mock(),
                "solace_agent_mesh_enterprise.platform_service.services": Mock(),
                "solace_agent_mesh_enterprise.platform_service.services.model_dependents_service": Mock(
                    ModelDependentsService=mock_dependents_service_cls
                ),
                "solace_agent_mesh_enterprise.platform_service.repositories": Mock(),
                "solace_agent_mesh_enterprise.platform_service.repositories.agent_repository": Mock(
                    AgentRepository=mock_agent_repo_cls
                ),
                "solace_agent_mesh_enterprise.platform_service.repositories.deployment_repository": Mock(
                    DeploymentRepository=mock_deployment_repo_cls
                ),
            },
        ):
            result = await get_model_dependents(
                alias="general",
                _=None,
                db=Mock(),
                service=mock_service,
            )

        assert len(result.data) == 1
        assert result.data[0].id == "agent-1"
        assert result.data[0].name == "Test Agent"
        assert result.data[0].type == "standard"
        assert result.data[0].deployment_status == "deployed"

    @pytest.mark.asyncio
    async def test_looks_up_config_by_alias(self):
        """Verifies the alias is resolved to config before querying dependents."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            get_model_dependents,
        )

        mock_service = Mock()
        mock_config = Mock()
        mock_config.alias = "planning"
        mock_config.id = "uuid-456"
        mock_service.get_by_alias.return_value = mock_config

        mock_db = Mock()

        # Force ImportError to take the simple path
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("solace_agent_mesh_enterprise"):
                raise ImportError()
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            await get_model_dependents(
                alias="planning",
                _=None,
                db=mock_db,
                service=mock_service,
            )

        mock_service.get_by_alias.assert_called_once_with(mock_db, "planning")


class TestDeleteModelCallsHandler:
    """Tests for DELETE /models/{alias} handler integration."""

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_calls_undeploy_dependents_before_delete(self, mock_emit):
        """Handler's undeploy_dependents is called before service.delete."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            delete_model,
        )

        mock_service = Mock()
        existing_config = Mock()
        existing_config.id = "uuid-789"
        existing_config.alias = "my-alias"
        mock_service.get_by_alias.return_value = existing_config

        mock_handler = AsyncMock(spec=ModelDependentsHandler)
        mock_handler.undeploy_dependents.return_value = [{"id": "agent-1", "name": "Agent"}]

        call_order = []
        mock_handler.undeploy_dependents.side_effect = lambda *a, **k: call_order.append("undeploy") or []
        mock_service.delete.side_effect = lambda *a, **k: call_order.append("delete")

        mock_component = Mock()

        await delete_model(
            alias="my-alias",
            _=None,
            db=Mock(),
            user={"id": "user-1"},
            service=mock_service,
            component=mock_component,
            dependents_handler=mock_handler,
        )

        mock_handler.undeploy_dependents.assert_called_once_with(
            "my-alias", "uuid-789", mock_component
        )
        mock_service.delete.assert_called_once()
        assert call_order == ["undeploy", "delete"]

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_passes_alias_and_id_to_handler(self, mock_emit):
        """Handler receives both the alias and the model UUID."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            delete_model,
        )

        mock_service = Mock()
        config = Mock()
        config.id = "model-uuid-abc"
        config.alias = "general"
        mock_service.get_by_alias.return_value = config

        mock_handler = AsyncMock(spec=ModelDependentsHandler)
        mock_handler.undeploy_dependents.return_value = []
        mock_component = Mock()

        await delete_model(
            alias="general",
            _=None,
            db=Mock(),
            user={"id": "u1"},
            service=mock_service,
            component=mock_component,
            dependents_handler=mock_handler,
        )

        mock_handler.undeploy_dependents.assert_called_once_with(
            "general", "model-uuid-abc", mock_component
        )

    @pytest.mark.asyncio
    @patch(
        "solace_agent_mesh.services.platform.api.routers.model_configurations_router._emit_model_config_update"
    )
    async def test_default_handler_allows_delete_to_proceed(self, mock_emit):
        """With default no-op handler, delete still succeeds."""
        from solace_agent_mesh.services.platform.api.routers.model_configurations_router import (
            delete_model,
        )

        mock_service = Mock()
        config = Mock()
        config.id = "uuid-1"
        config.alias = "test"
        mock_service.get_by_alias.return_value = config

        mock_db = Mock()

        await delete_model(
            alias="test",
            _=None,
            db=mock_db,
            user={"id": "u1"},
            service=mock_service,
            component=Mock(),
            dependents_handler=ModelDependentsHandler(),
        )

        mock_service.delete.assert_called_once_with(mock_db, "test")
