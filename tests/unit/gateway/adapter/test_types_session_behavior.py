"""
Unit tests for session_behavior field in SamTask.
Tests the new session_behavior field added to adapter types.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.gateway.adapter.types import SamTask, SamTextPart


class TestSamTaskSessionBehavior:
    """Test the session_behavior field in SamTask."""

    def test_sam_task_without_session_behavior(self):
        """Test creating SamTask without session_behavior (should default to None)."""
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={}
        )

        assert task.session_behavior is None

    def test_sam_task_with_persistent_session_behavior(self):
        """Test creating SamTask with PERSISTENT session_behavior."""
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={},
            session_behavior="PERSISTENT"
        )

        assert task.session_behavior == "PERSISTENT"

    def test_sam_task_with_run_based_session_behavior(self):
        """Test creating SamTask with RUN_BASED session_behavior."""
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={},
            session_behavior="RUN_BASED"
        )

        assert task.session_behavior == "RUN_BASED"

    def test_sam_task_session_behavior_is_optional(self):
        """Test that session_behavior field is optional."""
        # Should work without the field
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={}
        )

        assert hasattr(task, 'session_behavior')
        assert task.session_behavior is None

    def test_sam_task_session_behavior_case_sensitivity(self):
        """Test that session_behavior accepts different casing."""
        # Should accept any string value
        task1 = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test message")],
            
            platform_context={},
            session_behavior="persistent"
        )
        assert task1.session_behavior == "persistent"

        task2 = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test message")],
            
            platform_context={},
            session_behavior="Persistent"
        )
        assert task2.session_behavior == "Persistent"

    def test_sam_task_serialization_with_session_behavior(self):
        """Test serialization of SamTask with session_behavior."""
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={},
            session_behavior="PERSISTENT"
        )

        # Convert to dict
        task_dict = task.model_dump()

        assert "session_behavior" in task_dict
        assert task_dict["session_behavior"] == "PERSISTENT"

    def test_sam_task_serialization_without_session_behavior(self):
        """Test serialization of SamTask without session_behavior."""
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={}
        )

        # Convert to dict
        task_dict = task.model_dump()

        assert "session_behavior" in task_dict
        assert task_dict["session_behavior"] is None

    def test_sam_task_deserialization_with_session_behavior(self):
        """Test deserialization of SamTask with session_behavior."""
        task_data = {
            "target_agent": "test-agent",
            "parts": [SamTextPart(text="Test message").model_dump()],
            "platform_context": {},
            "session_behavior": "RUN_BASED"
        }

        task = SamTask(**task_data)

        assert task.session_behavior == "RUN_BASED"

    def test_sam_task_deserialization_without_session_behavior(self):
        """Test deserialization of SamTask without session_behavior field."""
        task_data = {
            "target_agent": "test-agent",
            "parts": [SamTextPart(text="Test message").model_dump()],
            "platform_context": {}
        }

        task = SamTask(**task_data)

        assert task.session_behavior is None

    def test_sam_task_update_session_behavior(self):
        """Test updating session_behavior after creation."""
        task = SamTask(
            parts=[SamTextPart(text="Test message")],
            target_agent="test-agent",
            platform_context={}
        )

        # Initially None
        assert task.session_behavior is None

        # Create a copy with updated session_behavior
        updated_task = task.model_copy(update={"session_behavior": "PERSISTENT"})

        assert updated_task.session_behavior == "PERSISTENT"
        # Original should remain unchanged
        assert task.session_behavior is None

    def test_sam_task_with_all_fields_including_session_behavior(self):
        """Test SamTask with all fields populated including session_behavior."""
        task = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test message")],
            
            platform_context={"user_id": "user-123"},
            session_behavior="PERSISTENT"
        )

        assert task.target_agent == "test-agent"
        assert task.parts[0].text == "Test message"
        assert task.platform_context == {"user_id": "user-123"}
        assert task.session_behavior == "PERSISTENT"


class TestSessionBehaviorUseCases:
    """Test real-world use cases for session_behavior."""

    def test_persistent_session_for_chatbot(self):
        """Test PERSISTENT session behavior for long-running chatbot conversations."""
        task = SamTask(
            target_agent="chatbot-agent",
            parts=[SamTextPart(text="Hello, remember our previous conversation?")],
            
            platform_context={"channel": "slack"},
            session_behavior="PERSISTENT"
        )

        # Verify the task is configured for persistent sessions
        assert task.session_behavior == "PERSISTENT"

    def test_run_based_session_for_one_off_query(self):
        """Test RUN_BASED session behavior for one-off queries."""
        task = SamTask(
            target_agent="search-agent",
            parts=[SamTextPart(text="What is the weather today?")],
            
            platform_context={"source": "api"},
            session_behavior="RUN_BASED"
        )

        # Verify the task is configured for run-based sessions
        assert task.session_behavior == "RUN_BASED"

    def test_default_behavior_when_not_specified(self):
        """Test that default behavior applies when session_behavior is not specified."""
        task = SamTask(
            target_agent="default-agent",
            parts=[SamTextPart(text="Process this request")],
            
            platform_context={}
        )

        # When not specified, agent should use its default behavior
        assert task.session_behavior is None

    def test_adapter_can_override_default_session_behavior(self):
        """Test that adapter can override agent's default session behavior."""
        # Scenario: Agent defaults to PERSISTENT, but adapter wants RUN_BASED
        task = SamTask(
            target_agent="flexible-agent",
            parts=[SamTextPart(text="One-time task")],
            
            platform_context={},
            session_behavior="RUN_BASED"  # Override agent default
        )

        assert task.session_behavior == "RUN_BASED"

    def test_session_behavior_with_invoked_artifacts(self):
        """Test session_behavior works alongside invoked_with_artifacts."""
        task = SamTask(
            target_agent="document-processor",
            parts=[SamTextPart(text="Process these documents")],
            
            platform_context={"invoked_with_artifacts": ["artifact-1", "artifact-2"]},
            session_behavior="RUN_BASED"
        )

        assert task.session_behavior == "RUN_BASED"
        assert "invoked_with_artifacts" in task.platform_context


class TestSessionBehaviorValidation:
    """Test validation of session_behavior values."""

    def test_session_behavior_accepts_any_string(self):
        """Test that session_behavior accepts any string value."""
        # The field is optional string, so any string should work
        task = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test")],
            
            platform_context={},
            session_behavior="CUSTOM_BEHAVIOR"
        )

        assert task.session_behavior == "CUSTOM_BEHAVIOR"

    def test_session_behavior_none_is_valid(self):
        """Test that None is a valid value for session_behavior."""
        task = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test")],
            
            platform_context={},
            session_behavior=None
        )

        assert task.session_behavior is None

    def test_session_behavior_empty_string(self):
        """Test that empty string is accepted for session_behavior."""
        task = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test")],
            
            platform_context={},
            session_behavior=""
        )

        assert task.session_behavior == ""

    def test_session_behavior_with_spaces(self):
        """Test that session_behavior accepts strings with spaces."""
        task = SamTask(
            target_agent="test-agent",
            parts=[SamTextPart(text="Test")],
            
            platform_context={},
            session_behavior="CUSTOM BEHAVIOR"
        )

        assert task.session_behavior == "CUSTOM BEHAVIOR"
