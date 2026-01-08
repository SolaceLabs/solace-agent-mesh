#!/usr/bin/env python3
"""
Unit tests for RBAC scope checking in BaseGatewayComponent.submit_a2a_task.

Verifies that submit_a2a_task always performs agent access scope validation
by calling config_resolver.validate_operation_config before submitting tasks.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from a2a.types import TextPart

from src.solace_agent_mesh.gateway.base.component import BaseGatewayComponent


class TestGatewaySubmitA2ATaskRBAC:
    """Test cases for RBAC scope checking in gateway submit_a2a_task."""

    @pytest.fixture
    def mock_gateway_component(self):
        """Create a mock BaseGatewayComponent with minimal setup."""
        component = Mock(spec=BaseGatewayComponent)
        component.log_identifier = "[TestGateway]"
        component.gateway_id = "test-gateway"
        component.namespace = "/test/namespace"
        component.get_config = Mock(side_effect=lambda key, default="": {
            "system_purpose": "",
            "response_format": "",
        }.get(key, default))
        component.identity_service = None
        component.publish_a2a_message = Mock()
        component.task_context_manager = Mock()
        component.task_context_manager.store_context = Mock()
        component.submit_a2a_task = BaseGatewayComponent.submit_a2a_task.__get__(component)
        return component

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.common.utils.rbac_utils.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    async def test_submit_a2a_task_calls_validate_operation_config(
        self, mock_gateway_registry, mock_rbac_registry, mock_gateway_component
    ):
        """Test that submit_a2a_task calls config_resolver.validate_operation_config."""
        # Mock for gateway's config resolution
        mock_gateway_config_resolver = AsyncMock()
        resolved_user_config = {"_enterprise_capabilities": ["agent:researcher:delegate"]}
        mock_gateway_config_resolver.resolve_user_config.return_value = resolved_user_config
        mock_gateway_registry.get_config_resolver.return_value = mock_gateway_config_resolver

        # Mock for RBAC validation
        mock_rbac_config_resolver = Mock()
        mock_rbac_config_resolver.validate_operation_config.return_value = {"valid": True}
        mock_rbac_registry.get_config_resolver.return_value = mock_rbac_config_resolver

        await mock_gateway_component.submit_a2a_task(
            target_agent_name="researcher",
            a2a_parts=[TextPart(text="Hello")],
            external_request_context={"a2a_session_id": "session-123"},
            user_identity={"id": "user123", "name": "Test User"}
        )

        mock_rbac_config_resolver.validate_operation_config.assert_called_once()
        call_args = mock_rbac_config_resolver.validate_operation_config.call_args[0]

        # Verify user_config is passed (includes resolved config + user_profile)
        user_config = call_args[0]
        assert user_config["_enterprise_capabilities"] == ["agent:researcher:delegate"]
        assert user_config["user_profile"]["id"] == "user123"

        # Verify operation_spec contains agent_access and target_agent
        operation_spec = call_args[1]
        assert operation_spec["operation_type"] == "agent_access"
        assert operation_spec["target_agent"] == "researcher"

        # Verify validation_context contains gateway_id and source
        validation_context = call_args[2]
        assert validation_context["gateway_id"] == "test-gateway"
        assert validation_context["source"] == "gateway_request"

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.common.utils.rbac_utils.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    async def test_submit_a2a_task_blocks_on_validation_failure(
        self, mock_gateway_registry, mock_rbac_registry, mock_gateway_component
    ):
        """Test that submit_a2a_task raises PermissionError when validation fails."""
        # Mock for gateway's config resolution
        mock_gateway_config_resolver = AsyncMock()
        mock_gateway_config_resolver.resolve_user_config.return_value = {}
        mock_gateway_registry.get_config_resolver.return_value = mock_gateway_config_resolver

        # Mock for RBAC validation (returns invalid)
        mock_rbac_config_resolver = Mock()
        mock_rbac_config_resolver.validate_operation_config.return_value = {
            "valid": False,
            "reason": "Missing required scope",
            "required_scopes": ["agent:researcher:delegate"]
        }
        mock_rbac_registry.get_config_resolver.return_value = mock_rbac_config_resolver

        with pytest.raises(PermissionError) as excinfo:
            await mock_gateway_component.submit_a2a_task(
                target_agent_name="researcher",
                a2a_parts=[TextPart(text="Hello")],
                external_request_context={"a2a_session_id": "session-123"},
                user_identity={"id": "user123", "name": "Test User"}
            )

        assert "Access denied" in str(excinfo.value)
        mock_gateway_component.publish_a2a_message.assert_not_called()
