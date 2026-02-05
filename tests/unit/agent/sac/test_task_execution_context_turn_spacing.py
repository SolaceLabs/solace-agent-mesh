#!/usr/bin/env python3
"""
Unit tests for turn detection and spacing in TaskExecutionContext.

These tests verify that the turn tracking logic correctly:
1. Detects new turns based on invocation_id changes
2. Tracks first text in a turn
3. Manages spacing flags to add proper spacing between turns
"""

import pytest
from src.solace_agent_mesh.agent.sac.task_execution_context import TaskExecutionContext


class TestTurnDetectionAndSpacing:
    """Test cases for turn detection and spacing logic in TaskExecutionContext."""

    def test_check_and_update_invocation_first_invocation(self):
        """Test that the first invocation doesn't trigger spacing."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # First invocation - should not be considered a new turn
        is_new_turn = context.check_and_update_invocation("invocation-1")

        assert is_new_turn is False, "First invocation should not be considered a new turn"
        assert context._current_invocation_id == "invocation-1"
        assert context._need_spacing_before_next_text is False

    def test_check_and_update_invocation_same_invocation(self):
        """Test that repeated calls with the same invocation_id don't trigger new turns."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # First invocation
        context.check_and_update_invocation("invocation-1")

        # Same invocation again - should not be a new turn
        is_new_turn = context.check_and_update_invocation("invocation-1")

        assert is_new_turn is False, "Same invocation should not trigger new turn"
        assert context._need_spacing_before_next_text is False

    def test_check_and_update_invocation_new_turn(self):
        """Test that a new invocation_id correctly triggers new turn detection."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # First invocation
        context.check_and_update_invocation("invocation-1")

        # New invocation - should trigger new turn
        is_new_turn = context.check_and_update_invocation("invocation-2")

        assert is_new_turn is True, "Different invocation should trigger new turn"
        assert context._current_invocation_id == "invocation-2"
        assert context._need_spacing_before_next_text is True

    def test_is_first_text_in_turn_initial(self):
        """Test that first call to is_first_text_in_turn returns True."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        context.check_and_update_invocation("invocation-1")

        # First text in turn
        is_first = context.is_first_text_in_turn()

        assert is_first is True, "First text should be detected"
        assert context._first_text_seen_in_turn is True

    def test_is_first_text_in_turn_subsequent(self):
        """Test that subsequent calls to is_first_text_in_turn return False."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        context.check_and_update_invocation("invocation-1")

        # First text
        context.is_first_text_in_turn()

        # Second text - should not be first
        is_first = context.is_first_text_in_turn()

        assert is_first is False, "Subsequent text should not be marked as first"

    def test_is_first_text_resets_on_new_turn(self):
        """Test that first text tracking resets when a new turn begins."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # First turn
        context.check_and_update_invocation("invocation-1")
        context.is_first_text_in_turn()  # Mark first text seen
        context.is_first_text_in_turn()  # This should be False

        # Start new turn
        context.check_and_update_invocation("invocation-2")

        # First text in new turn should be True again
        is_first = context.is_first_text_in_turn()

        assert is_first is True, "First text should be detected in new turn"

    def test_should_add_turn_spacing_no_new_turn(self):
        """Test that spacing is not added when there's no new turn."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        context.check_and_update_invocation("invocation-1")

        # Should not need spacing for first turn
        should_add = context.should_add_turn_spacing()

        assert should_add is False, "First turn should not trigger spacing"

    def test_should_add_turn_spacing_new_turn(self):
        """Test that spacing flag is set and cleared correctly for new turns."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # First turn
        context.check_and_update_invocation("invocation-1")

        # Start new turn (this sets _need_spacing_before_next_text = True)
        context.check_and_update_invocation("invocation-2")

        # Should need spacing
        should_add = context.should_add_turn_spacing()

        assert should_add is True, "New turn should trigger spacing"
        assert context._need_spacing_before_next_text is False, "Flag should be cleared after check"

    def test_should_add_turn_spacing_only_once(self):
        """Test that spacing is only added once per turn transition."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # First turn
        context.check_and_update_invocation("invocation-1")

        # Start new turn
        context.check_and_update_invocation("invocation-2")

        # First check - should return True
        should_add_first = context.should_add_turn_spacing()
        assert should_add_first is True

        # Second check - should return False (flag was cleared)
        should_add_second = context.should_add_turn_spacing()
        assert should_add_second is False, "Spacing should only be added once"

    def test_complete_turn_transition_sequence(self):
        """Test a complete sequence of turn transitions with all checks."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # === Turn 1 ===
        is_new = context.check_and_update_invocation("invocation-1")
        assert is_new is False, "First turn should not be new"

        should_space = context.should_add_turn_spacing()
        assert should_space is False, "No spacing before first turn"

        is_first = context.is_first_text_in_turn()
        assert is_first is True, "First text in turn 1"

        is_first_again = context.is_first_text_in_turn()
        assert is_first_again is False, "Subsequent text in turn 1"

        # === Turn 2 ===
        is_new = context.check_and_update_invocation("invocation-2")
        assert is_new is True, "Turn 2 should be new"

        should_space = context.should_add_turn_spacing()
        assert should_space is True, "Should add spacing before turn 2"

        is_first = context.is_first_text_in_turn()
        assert is_first is True, "First text in turn 2"

        should_space_again = context.should_add_turn_spacing()
        assert should_space_again is False, "Spacing already added for turn 2"

        # === Turn 3 ===
        is_new = context.check_and_update_invocation("invocation-3")
        assert is_new is True, "Turn 3 should be new"

        should_space = context.should_add_turn_spacing()
        assert should_space is True, "Should add spacing before turn 3"

        is_first = context.is_first_text_in_turn()
        assert is_first is True, "First text in turn 3"

    def test_thread_safety_with_lock(self):
        """Test that turn tracking operations use the lock properly."""
        context = TaskExecutionContext(
            task_id="test-task-1",
            a2a_context={},
        )

        # All these operations should work without raising exceptions
        # and should be thread-safe (using the context's lock)
        context.check_and_update_invocation("invocation-1")
        context.is_first_text_in_turn()
        context.should_add_turn_spacing()

        # Verify internal state is consistent
        assert context._current_invocation_id == "invocation-1"
        assert context._first_text_seen_in_turn is True
        assert context._need_spacing_before_next_text is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
