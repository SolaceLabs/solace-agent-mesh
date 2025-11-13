#!/usr/bin/env python3
"""
Unit tests for RBAC scope checking in BaseGatewayComponent.submit_a2a_task.

Verifies that submit_a2a_task always performs agent access scope validation
before submitting tasks to agents from gateway requests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
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
        component.get_config = Mock(side_effect=lambda key, default="": {
            "system_purpose": "",
            "response_format": "",
        }.get(key, default))
        component.identity_service = None
        component.publish_a2a_message = Mock()
        component._extract_initial_claims = AsyncMock(return_value={"id": "user123", "name": "Test User"})

        # Make the actual method available
        component.submit_a2a_task = BaseGatewayComponent.submit_a2a_task.__get__(component)

        return component

    @pytest.fixture
    def sample_user_identity(self):
        """Create a sample user identity for testing."""
        return {
            "id": "user123",
            "name": "Test User",
            "email": "test@example.com"
        }

    @pytest.fixture
    def sample_a2a_parts(self):
        """Create sample A2A content parts."""
        return [TextPart(text="Hello, agent!")]

    @pytest.fixture
    def sample_external_context(self):
        """Create sample external request context."""
        return {
            "a2a_session_id": "session-123",
            "user_id_for_a2a": "user123"
        }

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_calls_validate_agent_access(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that submit_a2a_task calls validate_agent_access with correct parameters."""
        # Setup mock config resolver
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = {
            "_enterprise_capabilities": ["agent:researcher:delegate"]
        }
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Test data
        target_agent_name = "researcher"

        # Call the method
        await mock_gateway_component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=sample_a2a_parts,
            external_request_context=sample_external_context,
            user_identity=sample_user_identity,
            is_streaming=True,
            api_version="v2"
        )

        # Verify validate_agent_access was called
        mock_validate.assert_called_once()

        # Verify the call arguments
        call_args = mock_validate.call_args
        assert call_args.kwargs["target_agent_name"] == target_agent_name
        assert call_args.kwargs["validation_context"]["gateway_id"] == "test-gateway"
        assert call_args.kwargs["validation_context"]["source"] == "gateway_request"
        assert "[TestGateway][SubmitA2ATask]" in call_args.kwargs["log_identifier"]

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_validation_happens_before_task_submission(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that validation occurs before any task submission."""
        # Setup mock config resolver
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = {}
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Test data
        target_agent_name = "worker"

        # Call the method
        await mock_gateway_component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=sample_a2a_parts,
            external_request_context=sample_external_context,
            user_identity=sample_user_identity
        )

        # Verify validate was called
        mock_validate.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_raises_on_validation_failure(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that submit_a2a_task raises PermissionError when validation fails."""
        # Setup mock config resolver
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = {}
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Setup validation to raise PermissionError
        mock_validate.side_effect = PermissionError(
            "Access denied to agent 'researcher'. Required scopes: ['agent:researcher:delegate']"
        )

        # Test data
        target_agent_name = "researcher"

        # Verify that PermissionError is raised
        with pytest.raises(PermissionError) as excinfo:
            await mock_gateway_component.submit_a2a_task(
                target_agent_name=target_agent_name,
                a2a_parts=sample_a2a_parts,
                external_request_context=sample_external_context,
                user_identity=sample_user_identity
            )

        # Verify the error message
        assert "Access denied to agent 'researcher'" in str(excinfo.value)
        assert "agent:researcher:delegate" in str(excinfo.value)

        # Verify that publish was NOT called
        mock_gateway_component.publish_a2a_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_user_config_passed_to_validation(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that resolved user config is passed to validation."""
        # Setup mock config resolver with specific user config
        resolved_user_config = {
            "_enterprise_capabilities": ["agent:analyst:delegate"],
            "user_id": "user123",
            "custom_field": "custom_value"
        }
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = resolved_user_config
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Test data
        target_agent_name = "analyst"

        # Call the method
        await mock_gateway_component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_parts=sample_a2a_parts,
            external_request_context=sample_external_context,
            user_identity=sample_user_identity
        )

        # Verify the user config was passed correctly (including user_profile)
        call_args = mock_validate.call_args
        user_config = call_args.kwargs["user_config"]
        assert user_config["_enterprise_capabilities"] == ["agent:analyst:delegate"]
        assert user_config["user_profile"] == sample_user_identity

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_validation_context_includes_gateway_id(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that validation context includes the gateway ID."""
        # Setup mock config resolver
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = {}
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Setup gateway with specific ID
        mock_gateway_component.gateway_id = "http-sse-gateway"

        # Call the method
        await mock_gateway_component.submit_a2a_task(
            target_agent_name="test-agent",
            a2a_parts=sample_a2a_parts,
            external_request_context=sample_external_context,
            user_identity=sample_user_identity
        )

        # Verify the validation context
        call_args = mock_validate.call_args
        validation_context = call_args.kwargs["validation_context"]
        assert validation_context["gateway_id"] == "http-sse-gateway"
        assert validation_context["source"] == "gateway_request"

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_always_validates_regardless_of_target(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that validation is performed for all target agents."""
        # Setup mock config resolver
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = {}
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Test with multiple different target agents
        target_agents = [
            "researcher",
            "analyst",
            "worker",
            "orchestrator",
            "custom-agent-name"
        ]

        for target_agent in target_agents:
            mock_validate.reset_mock()

            # Call the method
            await mock_gateway_component.submit_a2a_task(
                target_agent_name=target_agent,
                a2a_parts=sample_a2a_parts,
                external_request_context=sample_external_context.copy(),
                user_identity=sample_user_identity
            )

            # Verify validation was called for each target
            mock_validate.assert_called_once()
            call_args = mock_validate.call_args
            assert call_args.kwargs["target_agent_name"] == target_agent

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_rejects_invalid_user_identity(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_a2a_parts, sample_external_context
    ):
        """Test that submit_a2a_task rejects invalid user identities before validation."""
        # Setup mock config resolver
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = {}
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Test with invalid user identities
        invalid_identities = [
            None,
            {},
            {"name": "User without ID"},
            "string_identity",
        ]

        for invalid_identity in invalid_identities:
            mock_validate.reset_mock()

            # Verify that PermissionError is raised for invalid identity
            with pytest.raises(PermissionError) as excinfo:
                await mock_gateway_component.submit_a2a_task(
                    target_agent_name="test-agent",
                    a2a_parts=sample_a2a_parts,
                    external_request_context=sample_external_context.copy(),
                    user_identity=invalid_identity
                )

            # Verify the error message
            assert "User not authenticated or identity is invalid" in str(excinfo.value)

            # Verify that validate_agent_access was NOT called for invalid identity
            mock_validate.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_validation_with_resolved_config(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that validation uses the resolved user config from ConfigResolver."""
        # Setup mock config resolver to return specific config
        expected_resolved_config = {
            "_enterprise_capabilities": ["agent:test:delegate", "admin:full"],
            "organization": "test-org"
        }
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.return_value = expected_resolved_config
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Call the method
        await mock_gateway_component.submit_a2a_task(
            target_agent_name="test-agent",
            a2a_parts=sample_a2a_parts,
            external_request_context=sample_external_context,
            user_identity=sample_user_identity
        )

        # Verify config was resolved with correct parameters
        mock_config_resolver.resolve_user_config.assert_called_once()
        resolve_call_args = mock_config_resolver.resolve_user_config.call_args
        assert resolve_call_args[0][0] == sample_user_identity  # user_identity
        assert resolve_call_args[0][1]["gateway_id"] == "test-gateway"  # gateway_context

        # Verify validation received the resolved config (plus user_profile)
        call_args = mock_validate.call_args
        user_config = call_args.kwargs["user_config"]
        assert "_enterprise_capabilities" in user_config
        assert user_config["_enterprise_capabilities"] == expected_resolved_config["_enterprise_capabilities"]
        assert user_config["organization"] == "test-org"

    @pytest.mark.asyncio
    @patch("src.solace_agent_mesh.gateway.base.component.MiddlewareRegistry")
    @patch("src.solace_agent_mesh.gateway.base.component.validate_agent_access")
    async def test_submit_a2a_task_validation_even_with_config_resolution_error(
        self, mock_validate, mock_registry, mock_gateway_component,
        sample_user_identity, sample_a2a_parts, sample_external_context
    ):
        """Test that validation still occurs even if config resolution fails."""
        # Setup mock config resolver to raise an exception
        mock_config_resolver = AsyncMock()
        mock_config_resolver.resolve_user_config.side_effect = Exception("Config resolution failed")
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        # Call the method - should still call validation with default config
        await mock_gateway_component.submit_a2a_task(
            target_agent_name="test-agent",
            a2a_parts=sample_a2a_parts,
            external_request_context=sample_external_context,
            user_identity=sample_user_identity
        )

        # Verify validation was still called with empty config (plus user_profile)
        mock_validate.assert_called_once()
        call_args = mock_validate.call_args
        user_config = call_args.kwargs["user_config"]
        assert user_config["user_profile"] == sample_user_identity
