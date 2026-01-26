"""
Unit tests for conditional expression evaluation in workflows.

Tests the evaluate_condition() function which is a pure function that
evaluates condition expressions against workflow state.
"""

import pytest
from datetime import datetime, timezone

from solace_agent_mesh.workflow.flow_control.conditional import (
    evaluate_condition,
    ConditionalEvaluationError,
    _apply_template_aliases,
)
from solace_agent_mesh.workflow.workflow_execution_context import WorkflowExecutionState


def create_workflow_state(node_outputs: dict) -> WorkflowExecutionState:
    """Create a WorkflowExecutionState with given node outputs."""
    return WorkflowExecutionState(
        workflow_name="test_workflow",
        execution_id="test_exec_001",
        start_time=datetime.now(timezone.utc),
        node_outputs=node_outputs,
    )


class TestStringComparison:
    """Tests for string comparison conditions."""

    def test_string_equality_true(self):
        """String equality returns True when strings match."""
        state = create_workflow_state({
            "step1": {"output": {"status": "success"}}
        })

        result = evaluate_condition("'{{step1.output.status}}' == 'success'", state)
        assert result is True

    def test_string_equality_false(self):
        """String equality returns False when strings don't match."""
        state = create_workflow_state({
            "step1": {"output": {"status": "failure"}}
        })

        result = evaluate_condition("'{{step1.output.status}}' == 'success'", state)
        assert result is False

    def test_string_inequality(self):
        """String inequality comparison works."""
        state = create_workflow_state({
            "step1": {"output": {"status": "pending"}}
        })

        result = evaluate_condition("'{{step1.output.status}}' != 'success'", state)
        assert result is True


class TestNumericComparison:
    """Tests for numeric comparison conditions."""

    def test_greater_than_true(self):
        """Greater than comparison returns True when condition is met."""
        state = create_workflow_state({
            "step1": {"output": {"count": 15}}
        })

        result = evaluate_condition("{{step1.output.count}} > 10", state)
        assert result is True

    def test_greater_than_false(self):
        """Greater than comparison returns False when condition is not met."""
        state = create_workflow_state({
            "step1": {"output": {"count": 5}}
        })

        result = evaluate_condition("{{step1.output.count}} > 10", state)
        assert result is False

    def test_less_than(self):
        """Less than comparison works."""
        state = create_workflow_state({
            "step1": {"output": {"value": 3}}
        })

        result = evaluate_condition("{{step1.output.value}} < 5", state)
        assert result is True

    def test_greater_than_or_equal(self):
        """Greater than or equal comparison works."""
        state = create_workflow_state({
            "step1": {"output": {"count": 10}}
        })

        result = evaluate_condition("{{step1.output.count}} >= 10", state)
        assert result is True

    def test_less_than_or_equal(self):
        """Less than or equal comparison works."""
        state = create_workflow_state({
            "step1": {"output": {"count": 10}}
        })

        result = evaluate_condition("{{step1.output.count}} <= 10", state)
        assert result is True


class TestStringContains:
    """Tests for string contains/in conditions."""

    def test_string_contains_true(self):
        """'in' operator returns True when substring is found."""
        state = create_workflow_state({
            "step1": {"output": {"message": "Error: something went wrong"}}
        })

        result = evaluate_condition("'Error' in '{{step1.output.message}}'", state)
        assert result is True

    def test_string_contains_false(self):
        """'in' operator returns False when substring is not found."""
        state = create_workflow_state({
            "step1": {"output": {"message": "Everything is fine"}}
        })

        result = evaluate_condition("'Error' in '{{step1.output.message}}'", state)
        assert result is False

    def test_string_not_in(self):
        """'not in' operator works correctly."""
        state = create_workflow_state({
            "step1": {"output": {"message": "Everything is fine"}}
        })

        result = evaluate_condition("'Error' not in '{{step1.output.message}}'", state)
        assert result is True


class TestWorkflowInputReference:
    """Tests for referencing workflow input in conditions."""

    def test_workflow_input_comparison(self):
        """Workflow input can be referenced in conditions."""
        state = create_workflow_state({
            "workflow_input": {"output": {"mode": "production"}}
        })

        result = evaluate_condition("'{{workflow.input.mode}}' == 'production'", state)
        assert result is True

    def test_workflow_input_nested(self):
        """Nested workflow input fields can be referenced."""
        state = create_workflow_state({
            "workflow_input": {"output": {"config": {"enabled": "true"}}}
        })

        result = evaluate_condition("'{{workflow.input.config.enabled}}' == 'true'", state)
        assert result is True


class TestArgoAliases:
    """Tests for Argo-compatible template aliases."""

    def test_item_alias_in_condition(self):
        """{{item}} is aliased to {{_map_item}} in conditions.

        Note: Unlike DAGExecutor.resolve_value(), the conditional evaluator
        doesn't auto-unwrap the 'output' key for _map_item, so we need to
        use {{item.output}} or structure the state without the output wrapper.
        """
        state = create_workflow_state({
            "_map_item": {"output": "current_value"}
        })

        # Need to use item.output since conditional evaluator doesn't unwrap
        result = evaluate_condition("'{{item.output}}' == 'current_value'", state)
        assert result is True

    def test_item_field_alias_in_condition(self):
        """{{item.field}} is aliased to {{_map_item.field}}."""
        state = create_workflow_state({
            "_map_item": {"output": {"status": "ready"}}
        })

        # Need to include 'output' in path for conditional evaluator
        result = evaluate_condition("'{{item.output.status}}' == 'ready'", state)
        assert result is True

    def test_workflow_parameters_alias(self):
        """{{workflow.parameters.x}} is aliased to {{workflow.input.x}}."""
        state = create_workflow_state({
            "workflow_input": {"output": {"threshold": 50}}
        })

        result = evaluate_condition("{{workflow.parameters.threshold}} > 25", state)
        assert result is True


class TestApplyTemplateAliases:
    """Tests for the _apply_template_aliases helper function."""

    def test_item_alias(self):
        """{{item}} is replaced with {{_map_item}}."""
        result = _apply_template_aliases("{{item}}")
        assert result == "{{_map_item}}"

    def test_item_field_alias(self):
        """{{item.field}} is replaced with {{_map_item.field}}."""
        result = _apply_template_aliases("{{item.name}}")
        assert result == "{{_map_item.name}}"

    def test_workflow_parameters_alias(self):
        """workflow.parameters is replaced with workflow.input."""
        result = _apply_template_aliases("{{workflow.parameters.x}}")
        assert result == "{{workflow.input.x}}"

    def test_no_change_for_non_aliases(self):
        """Non-alias templates are unchanged."""
        result = _apply_template_aliases("{{step1.output.value}}")
        assert result == "{{step1.output.value}}"


class TestErrorHandling:
    """Tests for error handling in condition evaluation."""

    def test_missing_node_raises_error(self):
        """Referencing a non-existent node raises ConditionalEvaluationError."""
        state = create_workflow_state({
            "existing_node": {"output": {"x": 1}}
        })

        with pytest.raises(ConditionalEvaluationError, match="has not completed"):
            evaluate_condition("{{nonexistent.output.x}} > 0", state)

    def test_missing_workflow_input_raises_error(self):
        """Referencing workflow input before initialization raises error."""
        state = create_workflow_state({})  # No workflow_input

        with pytest.raises(ConditionalEvaluationError, match="has not been initialized"):
            evaluate_condition("'{{workflow.input.x}}' == 'y'", state)

    def test_invalid_expression_raises_error(self):
        """Invalid expression syntax raises ConditionalEvaluationError."""
        state = create_workflow_state({
            "step1": {"output": {"value": 1}}
        })

        with pytest.raises(ConditionalEvaluationError):
            evaluate_condition("{{step1.output.value}} >>> 5", state)


class TestBooleanLogic:
    """Tests for boolean logic in conditions."""

    def test_and_condition(self):
        """AND logic works in conditions."""
        state = create_workflow_state({
            "step1": {"output": {"a": 5, "b": 10}}
        })

        result = evaluate_condition(
            "{{step1.output.a}} > 0 and {{step1.output.b}} > 0",
            state
        )
        assert result is True

    def test_or_condition(self):
        """OR logic works in conditions."""
        state = create_workflow_state({
            "step1": {"output": {"status": "error"}}
        })

        result = evaluate_condition(
            "'{{step1.output.status}}' == 'success' or '{{step1.output.status}}' == 'error'",
            state
        )
        assert result is True

    def test_not_condition(self):
        """NOT logic works in conditions."""
        state = create_workflow_state({
            "step1": {"output": {"enabled": False}}
        })

        # When comparing to Python's False, use lowercase
        result = evaluate_condition(
            "not {{step1.output.enabled}}",
            state
        )
        assert result is True


class TestNullHandling:
    """Tests for handling None/null values."""

    def test_none_value_in_path(self):
        """None values in path are handled gracefully."""
        state = create_workflow_state({
            "step1": {"output": {"value": None}}
        })

        # None is converted to string "None" for comparison
        result = evaluate_condition("'{{step1.output.value}}' == 'None'", state)
        assert result is True

    def test_none_value_nested_access(self):
        """Accessing nested fields through None returns 'None'."""
        state = create_workflow_state({
            "step1": {"output": {"parent": None}}
        })

        # Trying to access a field through None returns "None"
        result = evaluate_condition("'{{step1.output.parent.child}}' == 'None'", state)
        assert result is True


class TestWorkflowStatusReference:
    """Tests for referencing workflow status in conditions (for exit handlers)."""

    def test_workflow_status_success(self):
        """Workflow status can be referenced in conditions."""
        state = create_workflow_state({
            "workflow": {"status": "success", "error": None}
        })

        result = evaluate_condition("'{{workflow.status}}' == 'success'", state)
        assert result is True

    def test_workflow_status_failure(self):
        """Workflow failure status can be checked."""
        state = create_workflow_state({
            "workflow": {"status": "failed", "error": "Something went wrong"}
        })

        result = evaluate_condition("'{{workflow.status}}' == 'failed'", state)
        assert result is True

    def test_workflow_error_not_none(self):
        """Workflow error can be checked for non-None value."""
        state = create_workflow_state({
            "workflow": {"status": "failed", "error": "Error message"}
        })

        result = evaluate_condition("'{{workflow.error}}' != 'None'", state)
        assert result is True

    def test_workflow_status_not_initialized(self):
        """Referencing workflow status before initialization raises error."""
        state = create_workflow_state({})  # No workflow status

        with pytest.raises(ConditionalEvaluationError, match="has not been initialized"):
            evaluate_condition("'{{workflow.status}}' == 'success'", state)


class TestFieldNotFoundError:
    """Tests for handling missing fields in paths."""

    def test_missing_field_in_output(self):
        """Missing field in output raises error."""
        state = create_workflow_state({
            "step1": {"output": {"existing_field": "value"}}
        })

        with pytest.raises(ConditionalEvaluationError, match="Field 'nonexistent' not found"):
            evaluate_condition("'{{step1.output.nonexistent}}' == 'value'", state)
