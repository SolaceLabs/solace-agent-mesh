#!/usr/bin/env python3
"""
Unit tests for RBAC scope checking in SamAgentComponent.submit_a2a_task.

Verifies that submit_a2a_task always performs agent access scope validation
before delegating tasks to peer agents.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
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
        component.active_tasks_lock = MagicMock()
        component.active_tasks = {}

        # Make the actual method available
        component.submit_a2a_task = SamAgentComponent.submit_a2a_task.__get__(component)
        component._get_agent_request_topic = Mock(return_value="test/request/topic")
        component._get_agent_response_topic = Mock(return_value="test/response/topic")
        component._get_peer_agent_status_topic = Mock(return_value="test/status/topic")

        return component

    @pytest.fixture
    def sample_a2a_message(self):
        """Create a sample A2A message for testing."""
        message = Mock(spec=A2AMessage)
        message.metadata = {
            "parentTaskId": "parent-task-123"
        }
        message.content = []
        return message

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_calls_validate_agent_access(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that submit_a2a_task calls validate_agent_access with correct parameters."""
        # Test data
        target_agent_name = "researcher"
        user_id = "user123"
        user_config = {
            "_enterprise_capabilities": ["agent:researcher:delegate"]
        }
        sub_task_id = "sub-task-456"

        # Call the method
        result = mock_component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_message=sample_a2a_message,
            user_id=user_id,
            user_config=user_config,
            sub_task_id=sub_task_id
        )

        # Verify validate_agent_access was called
        mock_validate.assert_called_once()

        # Verify the call arguments
        call_args = mock_validate.call_args
        assert call_args.kwargs["user_config"] == user_config
        assert call_args.kwargs["target_agent_name"] == target_agent_name
        assert call_args.kwargs["validation_context"]["delegating_agent"] == "test-agent"
        assert call_args.kwargs["validation_context"]["source"] == "agent_delegation"
        assert "[TestAgent][SubmitA2ATask:researcher]" in call_args.kwargs["log_identifier"]

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_validation_happens_before_publish(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that validation occurs before any message publishing."""
        # Test data
        target_agent_name = "worker"
        user_id = "user123"
        user_config = {}
        sub_task_id = "sub-task-789"

        # Call the method
        mock_component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_message=sample_a2a_message,
            user_id=user_id,
            user_config=user_config,
            sub_task_id=sub_task_id
        )

        # Get the order of calls
        manager = Mock()
        manager.attach_mock(mock_validate, "validate")
        manager.attach_mock(mock_component.publish_a2a_message, "publish")

        # Verify validate was called before publish
        mock_validate.assert_called_once()
        assert mock_validate.call_count == 1

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_raises_on_validation_failure(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that submit_a2a_task raises PermissionError when validation fails."""
        # Setup validation to raise PermissionError
        mock_validate.side_effect = PermissionError(
            "Access denied to agent 'researcher'. Required scopes: ['agent:researcher:delegate']"
        )

        # Test data
        target_agent_name = "researcher"
        user_id = "user123"
        user_config = {
            "_enterprise_capabilities": ["agent:other:delegate"]
        }
        sub_task_id = "sub-task-999"

        # Verify that PermissionError is raised
        with pytest.raises(PermissionError) as excinfo:
            mock_component.submit_a2a_task(
                target_agent_name=target_agent_name,
                a2a_message=sample_a2a_message,
                user_id=user_id,
                user_config=user_config,
                sub_task_id=sub_task_id
            )

        # Verify the error message
        assert "Access denied to agent 'researcher'" in str(excinfo.value)
        assert "agent:researcher:delegate" in str(excinfo.value)

        # Verify that publish was NOT called
        mock_component.publish_a2a_message.assert_not_called()

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_proceeds_after_successful_validation(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that submit_a2a_task proceeds with task submission after successful validation."""
        # Validation passes (no exception raised)
        mock_validate.return_value = None

        # Test data
        target_agent_name = "analyst"
        user_id = "user456"
        user_config = {
            "_enterprise_capabilities": ["agent:analyst:delegate"]
        }
        sub_task_id = "sub-task-111"

        # Call the method
        result = mock_component.submit_a2a_task(
            target_agent_name=target_agent_name,
            a2a_message=sample_a2a_message,
            user_id=user_id,
            user_config=user_config,
            sub_task_id=sub_task_id
        )

        # Verify validation was called
        mock_validate.assert_called_once()

        # Verify task submission proceeded
        mock_component.publish_a2a_message.assert_called_once()

        # Verify the sub_task_id is returned
        assert result == sub_task_id

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_validates_with_different_user_configs(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that different user configs are passed to validation correctly."""
        # Test with various user configs
        test_configs = [
            {},  # Empty config
            {"user_id": "test"},  # Simple config
            {
                "_enterprise_capabilities": ["agent:test:delegate"],
                "user_id": "test123",
                "custom_field": "value"
            },  # Complex config
        ]

        for idx, user_config in enumerate(test_configs):
            mock_validate.reset_mock()

            # Call the method
            mock_component.submit_a2a_task(
                target_agent_name=f"agent-{idx}",
                a2a_message=sample_a2a_message,
                user_id=f"user-{idx}",
                user_config=user_config,
                sub_task_id=f"sub-task-{idx}"
            )

            # Verify the user config was passed correctly
            call_args = mock_validate.call_args
            assert call_args.kwargs["user_config"] == user_config

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_validation_context_includes_delegating_agent(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that validation context includes the delegating agent name."""
        # Setup component to return specific agent name
        mock_component.get_config = Mock(return_value="orchestrator-agent")

        # Call the method
        mock_component.submit_a2a_task(
            target_agent_name="worker-agent",
            a2a_message=sample_a2a_message,
            user_id="user123",
            user_config={},
            sub_task_id="sub-task-222"
        )

        # Verify the validation context
        call_args = mock_validate.call_args
        validation_context = call_args.kwargs["validation_context"]
        assert validation_context["delegating_agent"] == "orchestrator-agent"
        assert validation_context["source"] == "agent_delegation"

    @patch("src.solace_agent_mesh.agent.sac.component.validate_agent_access")
    def test_submit_a2a_task_always_validates_regardless_of_target(
        self, mock_validate, mock_component, sample_a2a_message
    ):
        """Test that validation is performed for all target agents."""
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
            mock_component.submit_a2a_task(
                target_agent_name=target_agent,
                a2a_message=sample_a2a_message,
                user_id="user123",
                user_config={},
                sub_task_id=f"sub-task-{target_agent}"
            )

            # Verify validation was called for each target
            mock_validate.assert_called_once()
            call_args = mock_validate.call_args
            assert call_args.kwargs["target_agent_name"] == target_agent
