"""
Unit tests for map and loop nodes with workflow targets.

Tests that map and loop nodes correctly handle both agent nodes and workflow nodes
as their target nodes, ensuring proper node type detection and execution.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.workflow.app import (
    WorkflowDefinition,
    AgentNode,
    MapNode,
    LoopNode,
    WorkflowInvokeNode,
)


class TestMapNodeWithAgentTarget:
    """Tests for map nodes with agent targets."""

    def test_map_with_agent_target_valid(self):
        """Map node with agent target should parse correctly."""
        workflow = WorkflowDefinition(
            description="Map with agent target",
            nodes=[
                AgentNode(id="prepare", type="agent", agent_name="PrepareAgent"),
                MapNode(
                    id="process_all",
                    type="map",
                    node="process_item",
                    items="{{prepare.output.items}}",
                    depends_on=["prepare"],
                ),
                AgentNode(id="process_item", type="agent", agent_name="ProcessAgent"),
            ],
            output_mapping={"results": "{{process_all.output}}"},
        )

        assert workflow.nodes[1].node == "process_item"
        assert workflow.nodes[2].agent_name == "ProcessAgent"
        assert len(workflow.nodes) == 3


class TestMapNodeWithWorkflowTarget:
    """Tests for map nodes with workflow targets."""

    def test_map_with_workflow_target_valid(self):
        """Map node with workflow target should parse correctly."""
        workflow = WorkflowDefinition(
            description="Map with workflow target",
            nodes=[
                AgentNode(id="prepare", type="agent", agent_name="PrepareAgent"),
                MapNode(
                    id="process_all",
                    type="map",
                    node="process_workflow",
                    items="{{prepare.output.items}}",
                    depends_on=["prepare"],
                ),
                WorkflowInvokeNode(
                    id="process_workflow",
                    type="workflow",
                    workflow_name="ProcessWorkflow",
                ),
            ],
            output_mapping={"results": "{{process_all.output}}"},
        )

        assert workflow.nodes[1].node == "process_workflow"
        assert workflow.nodes[2].workflow_name == "ProcessWorkflow"
        assert len(workflow.nodes) == 3

    def test_map_with_workflow_target_has_correct_type(self):
        """Map node target can be identified as workflow type."""
        workflow = WorkflowDefinition(
            description="Map with workflow target",
            nodes=[
                MapNode(
                    id="map_workflows",
                    type="map",
                    node="sub_workflow",
                    items="{{workflow.input.items}}",
                ),
                WorkflowInvokeNode(
                    id="sub_workflow",
                    type="workflow",
                    workflow_name="SubWorkflow",
                ),
            ],
            output_mapping={"results": "{{map_workflows.output}}"},
        )

        target_node = workflow.nodes[1]
        assert target_node.type == "workflow"
        assert isinstance(target_node, WorkflowInvokeNode)


class TestLoopNodeWithAgentTarget:
    """Tests for loop nodes with agent targets."""

    def test_loop_with_agent_target_valid(self):
        """Loop node with agent target should parse correctly."""
        workflow = WorkflowDefinition(
            description="Loop with agent target",
            nodes=[
                LoopNode(
                    id="retry_agent",
                    type="loop",
                    node="attempt",
                    condition="{{retry_agent.output.retry}} == true",
                ),
                AgentNode(id="attempt", type="agent", agent_name="AttemptAgent"),
            ],
            output_mapping={"result": "{{attempt.output}}"},
        )

        assert workflow.nodes[0].node == "attempt"
        assert workflow.nodes[1].agent_name == "AttemptAgent"


class TestLoopNodeWithWorkflowTarget:
    """Tests for loop nodes with workflow targets."""

    def test_loop_with_workflow_target_valid(self):
        """Loop node with workflow target should parse correctly."""
        workflow = WorkflowDefinition(
            description="Loop with workflow target",
            nodes=[
                LoopNode(
                    id="retry_workflow",
                    type="loop",
                    node="retry_sub",
                    condition="{{retry_workflow.output.should_retry}} == true",
                ),
                WorkflowInvokeNode(
                    id="retry_sub",
                    type="workflow",
                    workflow_name="RetryWorkflow",
                ),
            ],
            output_mapping={"result": "{{retry_sub.output}}"},
        )

        assert workflow.nodes[0].node == "retry_sub"
        assert workflow.nodes[1].workflow_name == "RetryWorkflow"

    def test_loop_with_workflow_target_has_correct_type(self):
        """Loop node target can be identified as workflow type."""
        workflow = WorkflowDefinition(
            description="Loop with workflow target",
            nodes=[
                LoopNode(
                    id="loop_workflows",
                    type="loop",
                    node="sub_workflow",
                    condition="{{loop_workflows.output.continue}} == true",
                ),
                WorkflowInvokeNode(
                    id="sub_workflow",
                    type="workflow",
                    workflow_name="SubWorkflow",
                ),
            ],
            output_mapping={"result": "{{sub_workflow.output}}"},
        )

        target_node = workflow.nodes[1]
        assert target_node.type == "workflow"
        assert isinstance(target_node, WorkflowInvokeNode)


class TestMixedNodeTypesInMapLoop:
    """Tests for workflows mixing map/loop nodes with both agent and workflow targets."""

    def test_workflow_with_map_agent_and_loop_workflow(self):
        """Workflow can have both map with agent target and loop with workflow target."""
        workflow = WorkflowDefinition(
            description="Mixed map and loop with different targets",
            nodes=[
                AgentNode(id="start", type="agent", agent_name="StartAgent"),
                MapNode(
                    id="process_items",
                    type="map",
                    node="process_agent",
                    items="{{start.output.items}}",
                    depends_on=["start"],
                ),
                AgentNode(id="process_agent", type="agent", agent_name="ProcessAgent"),
                LoopNode(
                    id="retry_workflow",
                    type="loop",
                    node="retry_wf",
                    condition="{{process_items.output.needs_retry}} == true",
                    depends_on=["process_items"],
                ),
                WorkflowInvokeNode(
                    id="retry_wf",
                    type="workflow",
                    workflow_name="RetryWorkflow",
                ),
            ],
            output_mapping={"final": "{{retry_wf.output}}"},
        )

        # Verify map target is agent
        map_node = workflow.nodes[1]
        map_target = workflow.nodes[2]
        assert map_node.type == "map"
        assert map_target.type == "agent"
        assert map_target.agent_name == "ProcessAgent"

        # Verify loop target is workflow
        loop_node = workflow.nodes[3]
        loop_target = workflow.nodes[4]
        assert loop_node.type == "loop"
        assert loop_target.type == "workflow"
        assert loop_target.workflow_name == "RetryWorkflow"


class TestNodeTypeDetection:
    """Tests for correctly detecting node types in map/loop contexts."""

    def test_workflow_node_lacks_agent_name(self):
        """WorkflowInvokeNode should not have agent_name attribute."""
        workflow_node = WorkflowInvokeNode(
            id="invoke_wf",
            type="workflow",
            workflow_name="MyWorkflow",
        )

        # WorkflowInvokeNode should not have agent_name
        assert not hasattr(workflow_node, "agent_name") or workflow_node.agent_name is None
        assert workflow_node.workflow_name == "MyWorkflow"

    def test_agent_node_has_agent_name(self):
        """AgentNode should have agent_name attribute."""
        agent_node = AgentNode(
            id="invoke_agent",
            type="agent",
            agent_name="MyAgent",
        )

        assert agent_node.agent_name == "MyAgent"
        assert hasattr(agent_node, "agent_name")

    def test_target_node_type_can_be_determined(self):
        """Target node type can be determined from node.type."""
        workflow = WorkflowDefinition(
            description="Test node type determination",
            nodes=[
                MapNode(
                    id="map1",
                    type="map",
                    node="target1",
                    items="{{workflow.input.items}}",
                ),
                AgentNode(id="target1", type="agent", agent_name="Agent1"),
                MapNode(
                    id="map2",
                    type="map",
                    node="target2",
                    items="{{workflow.input.items}}",
                ),
                WorkflowInvokeNode(
                    id="target2",
                    type="workflow",
                    workflow_name="Workflow1",
                ),
            ],
            output_mapping={"r1": "{{target1.output}}", "r2": "{{target2.output}}"},
        )

        # Get nodes by their IDs
        node_map = {node.id: node for node in workflow.nodes}

        # Verify we can determine types
        assert node_map["target1"].type == "agent"
        assert node_map["target2"].type == "workflow"


class TestWorkflowTargetInMapValidation:
    """Tests for validation of workflow targets in map nodes."""

    def test_map_with_valid_workflow_reference(self):
        """Map can reference an existing workflow node."""
        workflow = WorkflowDefinition(
            description="Map with valid workflow reference",
            nodes=[
                MapNode(
                    id="map_workflows",
                    type="map",
                    node="target_workflow",
                    items="{{workflow.input.items}}",
                ),
                WorkflowInvokeNode(
                    id="target_workflow",
                    type="workflow",
                    workflow_name="TargetWorkflow",
                    input={"item": "{{_map_item.output}}"},
                ),
            ],
            output_mapping={"results": "{{map_workflows.output}}"},
        )

        assert workflow.nodes[0].node == "target_workflow"
        assert len(workflow.nodes) == 2

    def test_workflow_with_input_mapping_in_map(self):
        """Workflow target in map can have input mapping using _map_item."""
        workflow = WorkflowDefinition(
            description="Workflow in map with input mapping",
            nodes=[
                MapNode(
                    id="map_wf",
                    type="map",
                    node="sub_wf",
                    items="{{workflow.input.items}}",
                ),
                WorkflowInvokeNode(
                    id="sub_wf",
                    type="workflow",
                    workflow_name="SubWorkflow",
                    input={
                        "current_item": "{{_map_item.output}}",
                        "index": "{{_map_index.output}}",
                    },
                ),
            ],
            output_mapping={"mapped_results": "{{map_wf.output}}"},
        )

        target_node = workflow.nodes[1]
        assert target_node.input is not None
        assert "current_item" in target_node.input
        assert target_node.input["index"] == "{{_map_index.output}}"
