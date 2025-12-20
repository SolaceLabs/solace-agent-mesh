"""
Unit tests for DAG (Directed Acyclic Graph) logic in workflow executor.

Tests the DAG traversal logic including initial node detection, dependency
checking, cycle detection, and skip propagation.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from solace_agent_mesh.workflow.dag_executor import DAGExecutor
from solace_agent_mesh.workflow.workflow_execution_context import WorkflowExecutionState
from solace_agent_mesh.workflow.app import (
    WorkflowDefinition,
    AgentNode,
    ConditionalNode,
    MapNode,
)


def create_dag_executor(nodes: list) -> DAGExecutor:
    """Create a DAGExecutor with given nodes."""
    workflow_def = WorkflowDefinition(
        description="Test workflow",
        nodes=nodes,
        output_mapping={"result": "dummy"},
    )
    mock_host = Mock()
    return DAGExecutor(workflow_def, mock_host)


def create_workflow_state(
    completed_nodes: dict = None,
    pending_nodes: list = None,
    skipped_nodes: dict = None,
) -> WorkflowExecutionState:
    """Create a WorkflowExecutionState for testing."""
    return WorkflowExecutionState(
        workflow_name="test_workflow",
        execution_id="test_exec_001",
        start_time=datetime.now(timezone.utc),
        completed_nodes=completed_nodes or {},
        pending_nodes=pending_nodes or [],
        skipped_nodes=skipped_nodes or {},
    )


class TestGetInitialNodes:
    """Tests for get_initial_nodes() - finding nodes with no dependencies."""

    def test_single_node_no_deps_is_initial(self):
        """A single node with no dependencies is returned as initial."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1")
        ])

        initial = executor.get_initial_nodes()
        assert initial == ["step1"]

    def test_multiple_initial_nodes(self):
        """Multiple nodes without dependencies are all returned."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2"),
            AgentNode(id="step3", type="agent", agent_name="Agent3"),
        ])

        initial = executor.get_initial_nodes()
        assert set(initial) == {"step1", "step2", "step3"}

    def test_node_with_deps_not_initial(self):
        """Nodes with dependencies are not returned as initial."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
        ])

        initial = executor.get_initial_nodes()
        assert initial == ["step1"]

    def test_complex_dag_initial_nodes(self):
        """In a complex DAG, only true entry points are initial."""
        # DAG shape:
        #   step1 --> step3
        #   step2 --> step3
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2"),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step1", "step2"]),
        ])

        initial = executor.get_initial_nodes()
        assert set(initial) == {"step1", "step2"}

    def test_map_inner_node_not_initial(self):
        """Inner nodes of MapNode are not returned as initial even if they have no deps."""
        executor = create_dag_executor([
            AgentNode(id="prepare", type="agent", agent_name="Agent1"),
            MapNode(
                id="map_node",
                type="map",
                node="process_item",
                items="{{prepare.output.items}}",
                depends_on=["prepare"],
            ),
            AgentNode(id="process_item", type="agent", agent_name="Agent2"),
        ])

        initial = executor.get_initial_nodes()
        # process_item is an inner node of map_node, so it shouldn't be initial
        assert "process_item" not in initial
        assert "prepare" in initial


class TestGetNextNodes:
    """Tests for get_next_nodes() - finding nodes ready to execute."""

    def test_node_ready_when_all_deps_complete(self):
        """Node becomes ready when all its dependencies are complete."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
        ])

        state = create_workflow_state(
            completed_nodes={"step1": "artifact1"}
        )

        next_nodes = executor.get_next_nodes(state)
        assert next_nodes == ["step2"]

    def test_node_not_ready_when_dep_incomplete(self):
        """Node is not ready if any dependency is incomplete."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2"),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step1", "step2"]),
        ])

        # Only step1 is complete
        state = create_workflow_state(
            completed_nodes={"step1": "artifact1"}
        )

        next_nodes = executor.get_next_nodes(state)
        # step2 should be ready (no deps), step3 should not (missing step2)
        assert "step2" in next_nodes
        assert "step3" not in next_nodes

    def test_node_ready_when_all_multiple_deps_complete(self):
        """Node with multiple dependencies is ready when all are complete."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2"),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step1", "step2"]),
        ])

        state = create_workflow_state(
            completed_nodes={"step1": "artifact1", "step2": "artifact2"}
        )

        next_nodes = executor.get_next_nodes(state)
        assert "step3" in next_nodes

    def test_completed_node_not_returned(self):
        """Already completed nodes are not returned as next."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
        ])

        state = create_workflow_state(
            completed_nodes={"step1": "artifact1", "step2": "artifact2"}
        )

        next_nodes = executor.get_next_nodes(state)
        assert next_nodes == []

    def test_pending_node_not_returned(self):
        """Nodes already pending execution are not returned again."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
        ])

        state = create_workflow_state(
            completed_nodes={"step1": "artifact1"},
            pending_nodes=["step2"],
        )

        next_nodes = executor.get_next_nodes(state)
        assert "step2" not in next_nodes

    def test_map_inner_node_not_returned(self):
        """Inner nodes of MapNode are not returned by get_next_nodes."""
        executor = create_dag_executor([
            AgentNode(id="prepare", type="agent", agent_name="Agent1"),
            MapNode(
                id="map_node",
                type="map",
                node="process_item",
                items="{{prepare.output.items}}",
                depends_on=["prepare"],
            ),
            AgentNode(id="process_item", type="agent", agent_name="Agent2"),
        ])

        state = create_workflow_state(
            completed_nodes={"prepare": "artifact1"}
        )

        next_nodes = executor.get_next_nodes(state)
        # map_node should be ready, but process_item should not be returned directly
        assert "map_node" in next_nodes
        assert "process_item" not in next_nodes


class TestValidateDAG:
    """Tests for validate_dag() - DAG structure validation."""

    def test_valid_linear_dag(self):
        """A valid linear DAG passes validation."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step2"]),
        ])

        errors = executor.validate_dag()
        assert errors == []

    def test_valid_diamond_dag(self):
        """A valid diamond-shaped DAG passes validation."""
        # DAG shape:
        #       step1
        #      /     \
        #   step2   step3
        #      \     /
        #       step4
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step1"]),
            AgentNode(id="step4", type="agent", agent_name="Agent4", depends_on=["step2", "step3"]),
        ])

        errors = executor.validate_dag()
        assert errors == []

    def test_invalid_dependency_reference_rejected_at_model_level(self):
        """Invalid dependency reference is rejected at WorkflowDefinition level.

        Note: This validation happens in Pydantic model validation, not in
        DAGExecutor.validate_dag(). This is correct behavior - fail fast.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="non-existent node"):
            create_dag_executor([
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
                AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["nonexistent"]),
            ])


class TestDependencyGraph:
    """Tests for dependency graph building."""

    def test_dependency_graph_structure(self):
        """Dependency graph is correctly built."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step1", "step2"]),
        ])

        assert executor.dependencies["step1"] == []
        assert executor.dependencies["step2"] == ["step1"]
        assert set(executor.dependencies["step3"]) == {"step1", "step2"}

    def test_reverse_dependency_graph(self):
        """Reverse dependency graph is correctly built."""
        executor = create_dag_executor([
            AgentNode(id="step1", type="agent", agent_name="Agent1"),
            AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
            AgentNode(id="step3", type="agent", agent_name="Agent3", depends_on=["step1"]),
        ])

        # step1 has step2 and step3 depending on it
        assert set(executor.reverse_dependencies["step1"]) == {"step2", "step3"}
        assert executor.reverse_dependencies["step2"] == []
        assert executor.reverse_dependencies["step3"] == []


class TestInnerNodeTracking:
    """Tests for inner node (map/loop target) tracking."""

    def test_map_node_target_tracked_as_inner(self):
        """MapNode's target node is tracked as an inner node."""
        executor = create_dag_executor([
            AgentNode(id="prepare", type="agent", agent_name="Agent1"),
            MapNode(
                id="map_node",
                type="map",
                node="process_item",
                items="{{prepare.output.items}}",
                depends_on=["prepare"],
            ),
            AgentNode(id="process_item", type="agent", agent_name="Agent2"),
        ])

        assert "process_item" in executor.inner_nodes
        assert "map_node" not in executor.inner_nodes
        assert "prepare" not in executor.inner_nodes
