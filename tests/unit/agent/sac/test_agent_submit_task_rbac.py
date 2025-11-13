#!/usr/bin/env python3
"""
Unit tests for RBAC scope checking in SamAgentComponent.submit_a2a_task.

Verifies that submit_a2a_task always performs agent access scope validation
by calling config_resolver.validate_operation_config before delegating tasks.
"""

import pytest
from unittest.mock import Mock, patch
from a2a.types import Message as A2AMessage

from src.solace_agent_mesh.agent.sac.component import SamAgentComponent


class TestSubmitA2ATaskRBAC:
    """Test cases for RBAC scope checking in submit_a2a_task."""

    @pytest.fixture
    def mock_component(self):
        """Create a mock SamAgentComponent with minimal setup."""
        component = Mock(spec=SamAgentComponent)
        component.log_identifier = "[TestAgent]"
        component.get_config = Mock(return_value="test-agent")
        component.publish_a2a_message = Mock()
        component.active_tasks = {}
        component.active_tasks_lock = Mock()
        component.active_tasks_lock.__enter__ = Mock(return_value=None)
        component.active_tasks_lock.__exit__ = Mock(return_value=None)
        component.submit_a2a_task = SamAgentComponent.submit_a2a_task.__get__(component)
        component._get_agent_request_topic = Mock(return_value="test/request/topic")
        component._get_agent_response_topic = Mock(return_value="test/response/topic")
        component._get_peer_agent_status_topic = Mock(return_value="test/status/topic")
        return component

    @pytest.fixture
    def sample_a2a_message(self):
        """Create a sample A2A message for testing."""
        message = Mock(spec=A2AMessage)
        message.metadata = {"parentTaskId": "parent-task-123"}
        message.content = []
        return message

    @patch("src.solace_agent_mesh.common.utils.rbac_utils.MiddlewareRegistry")
    def test_submit_a2a_task_calls_validate_operation_config(
        self, mock_registry, mock_component, sample_a2a_message
    ):
        """Test that submit_a2a_task calls config_resolver.validate_operation_config."""
        mock_config_resolver = Mock()
        mock_config_resolver.validate_operation_config.return_value = {"valid": True}
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        user_config = {"_enterprise_capabilities": ["agent:researcher:delegate"]}

        mock_component.submit_a2a_task(
            target_agent_name="researcher",
            a2a_message=sample_a2a_message,
            user_id="user123",
            user_config=user_config,
            sub_task_id="sub-task-456"
        )

        mock_config_resolver.validate_operation_config.assert_called_once()
        call_args = mock_config_resolver.validate_operation_config.call_args[0]

        # Verify user_config is passed
        assert call_args[0] == user_config

        # Verify operation_spec contains agent_access and target_agent
        operation_spec = call_args[1]
        assert operation_spec["operation_type"] == "agent_access"
        assert operation_spec["target_agent"] == "researcher"

        # Verify validation_context contains delegating_agent and source
        validation_context = call_args[2]
        assert validation_context["delegating_agent"] == "test-agent"
        assert validation_context["source"] == "agent_delegation"

    @patch("src.solace_agent_mesh.common.utils.rbac_utils.MiddlewareRegistry")
    def test_submit_a2a_task_blocks_on_validation_failure(
        self, mock_registry, mock_component, sample_a2a_message
    ):
        """Test that submit_a2a_task raises PermissionError when validation fails."""
        mock_config_resolver = Mock()
        mock_config_resolver.validate_operation_config.return_value = {
            "valid": False,
            "reason": "Missing required scope",
            "required_scopes": ["agent:researcher:delegate"]
        }
        mock_registry.get_config_resolver.return_value = mock_config_resolver

        with pytest.raises(PermissionError) as excinfo:
            mock_component.submit_a2a_task(
                target_agent_name="researcher",
                a2a_message=sample_a2a_message,
                user_id="user123",
                user_config={},
                sub_task_id="sub-task-999"
            )

        assert "Access denied" in str(excinfo.value)
        mock_component.publish_a2a_message.assert_not_called()
