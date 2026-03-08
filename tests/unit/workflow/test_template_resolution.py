"""
Unit tests for template resolution in workflow DAG executor.

Tests the resolve_value() and _resolve_template() methods which are pure functions
that transform template strings into resolved values based on workflow state.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from solace_agent_mesh.workflow.dag_executor import DAGExecutor
from solace_agent_mesh.workflow.workflow_execution_context import WorkflowExecutionState
from solace_agent_mesh.workflow.app import WorkflowDefinition, AgentNode


def create_minimal_dag_executor() -> DAGExecutor:
    """Create a minimal DAGExecutor for testing resolve_value."""
    # Minimal workflow definition with one node
    workflow_def = WorkflowDefinition(
        description="Test workflow",
        nodes=[
            AgentNode(id="test_node", type="agent", agent_name="TestAgent")
        ],
        output_mapping={"result": "{{test_node.output}}"},
    )
    # Mock the host component - not used by resolve_value
    mock_host = Mock()
    return DAGExecutor(workflow_def, mock_host)


def create_workflow_state(node_outputs: dict) -> WorkflowExecutionState:
    """Create a WorkflowExecutionState with given node outputs."""
    return WorkflowExecutionState(
        workflow_name="test_workflow",
        execution_id="test_exec_001",
        start_time=datetime.now(timezone.utc),
        node_outputs=node_outputs,
    )


class TestResolveWorkflowInput:
    """Tests for resolving {{workflow.input.*}} templates."""

    def test_resolve_workflow_input_simple(self):
        """{{workflow.input.x}} resolves to the value from workflow input."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {"x": 42}}
        })

        result = executor.resolve_value("{{workflow.input.x}}", state)
        assert result == 42

    def test_resolve_workflow_input_nested(self):
        """{{workflow.input.a.b.c}} resolves nested paths."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {"a": {"b": {"c": "deep_value"}}}}
        })

        result = executor.resolve_value("{{workflow.input.a.b.c}}", state)
        assert result == "deep_value"

    def test_resolve_workflow_input_missing_field_returns_none(self):
        """Missing workflow input field returns None (for coalesce support)."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {"x": 1}}
        })

        result = executor.resolve_value("{{workflow.input.nonexistent}}", state)
        assert result is None

    def test_resolve_workflow_input_not_initialized_raises(self):
        """Referencing workflow input before initialization raises ValueError."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})  # No workflow_input

        with pytest.raises(ValueError, match="Workflow input has not been initialized"):
            executor.resolve_value("{{workflow.input.x}}", state)


class TestResolveNodeOutput:
    """Tests for resolving {{node.output.*}} templates."""

    def test_resolve_node_output_simple(self):
        """{{node.output.field}} resolves to the value from node output."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "step1": {"output": {"result": "success"}}
        })

        result = executor.resolve_value("{{step1.output.result}}", state)
        assert result == "success"

    def test_resolve_node_output_nested(self):
        """{{node.output.a.b}} resolves nested paths in node output."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "process_node": {"output": {"data": {"items": [1, 2, 3]}}}
        })

        result = executor.resolve_value("{{process_node.output.data.items}}", state)
        assert result == [1, 2, 3]

    def test_resolve_node_output_missing_node_returns_none(self):
        """Referencing non-existent node returns None (for skipped nodes)."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "existing_node": {"output": {"x": 1}}
        })

        result = executor.resolve_value("{{nonexistent_node.output.x}}", state)
        assert result is None

    def test_resolve_node_output_missing_field_raises(self):
        """Missing field in existing node output raises ValueError."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "step1": {"output": {"x": 1}}
        })

        with pytest.raises(ValueError, match="Output field 'nonexistent' not found"):
            executor.resolve_value("{{step1.output.nonexistent}}", state)


class TestResolveLiteralValues:
    """Tests for literal value passthrough."""

    def test_literal_string_passthrough(self):
        """Non-template strings are returned unchanged."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        result = executor.resolve_value("hello world", state)
        assert result == "hello world"

    def test_literal_number_passthrough(self):
        """Numbers are returned unchanged."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        assert executor.resolve_value(42, state) == 42
        assert executor.resolve_value(3.14, state) == 3.14

    def test_literal_bool_passthrough(self):
        """Booleans are returned unchanged."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        assert executor.resolve_value(True, state) is True
        assert executor.resolve_value(False, state) is False

    def test_literal_none_passthrough(self):
        """None is returned unchanged."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        result = executor.resolve_value(None, state)
        assert result is None

    def test_literal_dict_passthrough(self):
        """Plain dicts (not operators) are returned unchanged."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        # Dict with multiple keys is not an operator, passed through
        input_dict = {"key1": "value1", "key2": "value2"}
        result = executor.resolve_value(input_dict, state)
        assert result == input_dict


class TestCoalesceOperator:
    """Tests for the coalesce operator."""

    def test_coalesce_returns_first_non_null(self):
        """Coalesce returns first non-null value."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {}}
        })

        result = executor.resolve_value(
            {"coalesce": [None, "fallback", "ignored"]},
            state
        )
        assert result == "fallback"

    def test_coalesce_with_template_resolution(self):
        """Coalesce resolves templates before checking null."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {"optional": None, "default": "default_val"}}
        })

        result = executor.resolve_value(
            {"coalesce": ["{{workflow.input.optional}}", "{{workflow.input.default}}"]},
            state
        )
        assert result == "default_val"

    def test_coalesce_all_null_returns_none(self):
        """Coalesce returns None if all values are null."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {}}
        })

        result = executor.resolve_value(
            {"coalesce": [None, None]},
            state
        )
        assert result is None

    def test_coalesce_requires_list(self):
        """Coalesce operator requires a list argument."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        with pytest.raises(ValueError, match="'coalesce' operator requires a list"):
            executor.resolve_value({"coalesce": "not_a_list"}, state)


class TestConcatOperator:
    """Tests for the concat operator."""

    def test_concat_joins_strings(self):
        """Concat joins string values."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        result = executor.resolve_value(
            {"concat": ["hello", " ", "world"]},
            state
        )
        assert result == "hello world"

    def test_concat_with_template_resolution(self):
        """Concat resolves templates before joining."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {"name": "Alice"}}
        })

        result = executor.resolve_value(
            {"concat": ["Hello, ", "{{workflow.input.name}}", "!"]},
            state
        )
        assert result == "Hello, Alice!"

    def test_concat_converts_numbers_to_string(self):
        """Concat converts non-string values to strings."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        result = executor.resolve_value(
            {"concat": ["Value: ", 42]},
            state
        )
        assert result == "Value: 42"

    def test_concat_skips_none_values(self):
        """Concat skips None values in the list."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        result = executor.resolve_value(
            {"concat": ["a", None, "b"]},
            state
        )
        assert result == "ab"

    def test_concat_requires_list(self):
        """Concat operator requires a list argument."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({})

        with pytest.raises(ValueError, match="'concat' operator requires a list"):
            executor.resolve_value({"concat": "not_a_list"}, state)


class TestMapLoopVariables:
    """Tests for map/loop special variables."""

    def test_resolve_map_item(self):
        """{{_map_item}} resolves to the current map iteration item."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "_map_item": {"output": {"id": "item_123", "value": 100}}
        })

        result = executor.resolve_value("{{_map_item.id}}", state)
        assert result == "item_123"

    def test_resolve_map_index(self):
        """{{_map_index}} resolves to the current map iteration index."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "_map_index": {"output": 5}
        })

        result = executor.resolve_value("{{_map_index}}", state)
        assert result == 5

    def test_argo_item_alias(self):
        """{{item}} is aliased to {{_map_item}} for Argo compatibility."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "_map_item": {"output": "current_item_value"}
        })

        result = executor.resolve_value("{{item}}", state)
        assert result == "current_item_value"

    def test_argo_item_field_alias(self):
        """{{item.field}} is aliased to {{_map_item.field}}."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "_map_item": {"output": {"name": "test_name"}}
        })

        result = executor.resolve_value("{{item.name}}", state)
        assert result == "test_name"


class TestArgoParametersAlias:
    """Tests for Argo workflow.parameters alias."""

    def test_workflow_parameters_alias(self):
        """{{workflow.parameters.x}} is aliased to {{workflow.input.x}}."""
        executor = create_minimal_dag_executor()
        state = create_workflow_state({
            "workflow_input": {"output": {"x": "argo_style_value"}}
        })

        result = executor.resolve_value("{{workflow.parameters.x}}", state)
        assert result == "argo_style_value"
