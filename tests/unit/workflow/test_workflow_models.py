"""
Unit tests for workflow definition Pydantic model validation.

Tests that WorkflowDefinition and node types validate correctly,
catching invalid configurations at construction time.
"""

import pytest
from pydantic import ValidationError

from solace_agent_mesh.workflow.app import (
    WorkflowDefinition,
    AgentNode,
    SwitchNode,
    SwitchCase,
    LoopNode,
    MapNode,
    WorkflowInvokeNode,
)


class TestValidWorkflowParsing:
    """Tests for valid workflow definitions."""

    def test_simple_linear_workflow(self):
        """A simple linear workflow parses correctly."""
        workflow = WorkflowDefinition(
            description="Simple workflow",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
                AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
            ],
            output_mapping={"result": "{{step2.output}}"},
        )

        assert workflow.description == "Simple workflow"
        assert len(workflow.nodes) == 2
        assert workflow.nodes[0].id == "step1"
        assert workflow.nodes[1].depends_on == ["step1"]

    def test_workflow_with_schemas(self):
        """Workflow with input/output schemas parses correctly."""
        workflow = WorkflowDefinition(
            description="Workflow with schemas",
            nodes=[
                AgentNode(id="process", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{process.output}}"},
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            output_schema={
                "type": "object",
                "properties": {"processed": {"type": "boolean"}},
            },
        )

        assert workflow.input_schema is not None
        assert workflow.output_schema is not None

    def test_workflow_with_map_node(self):
        """Workflow with map node parses correctly."""
        workflow = WorkflowDefinition(
            description="Map workflow",
            nodes=[
                AgentNode(id="prepare", type="agent", agent_name="Agent1"),
                MapNode(
                    id="process_all",
                    type="map",
                    node="process_item",
                    items="{{prepare.output.items}}",
                    depends_on=["prepare"],
                ),
                AgentNode(id="process_item", type="agent", agent_name="Agent2"),
            ],
            output_mapping={"results": "{{process_all.output}}"},
        )

        assert workflow.nodes[1].type == "map"
        assert workflow.nodes[1].items == "{{prepare.output.items}}"


class TestInvalidDependencyReference:
    """Tests for invalid dependency references."""

    def test_depends_on_nonexistent_node_rejected(self):
        """Depending on a non-existent node raises ValidationError."""
        with pytest.raises(ValidationError, match="non-existent node"):
            WorkflowDefinition(
                description="Invalid workflow",
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                    AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["missing"]),
                ],
                output_mapping={"result": "{{step2.output}}"},
            )


class TestMapNodeValidation:
    """Tests for MapNode validation."""

    def test_map_node_requires_items_source(self):
        """MapNode without any items source raises ValidationError."""
        with pytest.raises(ValidationError, match="requires one of"):
            MapNode(
                id="map1",
                type="map",
                node="inner",
                # Missing items, with_param, or with_items
            )

    def test_map_node_rejects_multiple_items_sources(self):
        """MapNode with multiple items sources raises ValidationError."""
        with pytest.raises(ValidationError, match="only one of"):
            MapNode(
                id="map1",
                type="map",
                node="inner",
                items="{{step1.output.list1}}",
                with_items=["a", "b", "c"],  # Can't have both!
            )

    def test_map_node_nonexistent_target_rejected(self):
        """MapNode referencing non-existent target node is rejected."""
        with pytest.raises(ValidationError, match="non-existent node"):
            WorkflowDefinition(
                description="Invalid map",
                nodes=[
                    AgentNode(id="prepare", type="agent", agent_name="Agent1"),
                    MapNode(
                        id="map_node",
                        type="map",
                        node="nonexistent_inner",  # This node doesn't exist
                        items="{{prepare.output.items}}",
                        depends_on=["prepare"],
                    ),
                ],
                output_mapping={"result": "{{map_node.output}}"},
            )

    def test_map_node_with_items_literal(self):
        """MapNode with literal withItems array parses correctly."""
        workflow = WorkflowDefinition(
            description="Map with literal items",
            nodes=[
                MapNode(
                    id="map_node",
                    type="map",
                    node="process",
                    with_items=["item1", "item2", "item3"],
                ),
                AgentNode(id="process", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{map_node.output}}"},
        )

        assert workflow.nodes[0].with_items == ["item1", "item2", "item3"]


class TestLoopNodeValidation:
    """Tests for LoopNode validation."""

    def test_loop_node_requires_target(self):
        """LoopNode without target node raises ValidationError."""
        with pytest.raises(ValidationError, match="node"):
            LoopNode(
                id="loop1",
                type="loop",
                condition="true",
                # Missing node
            )

    def test_loop_node_requires_condition(self):
        """LoopNode without condition raises ValidationError."""
        with pytest.raises(ValidationError, match="condition"):
            LoopNode(
                id="loop1",
                type="loop",
                node="inner",
                # Missing condition
            )

    def test_loop_node_nonexistent_target_rejected(self):
        """LoopNode referencing non-existent target node is rejected."""
        with pytest.raises(ValidationError, match="non-existent node"):
            WorkflowDefinition(
                description="Invalid loop",
                nodes=[
                    LoopNode(
                        id="loop_node",
                        type="loop",
                        node="nonexistent_inner",
                        condition="{{loop_inner.output.continue}}",
                    ),
                ],
                output_mapping={"result": "done"},
            )


class TestSwitchNodeValidation:
    """Tests for SwitchNode validation."""

    def test_switch_node_requires_cases(self):
        """SwitchNode without cases raises ValidationError."""
        with pytest.raises(ValidationError, match="cases"):
            SwitchNode(
                id="switch1",
                type="switch",
                # Missing cases
            )

    def test_switch_node_case_requires_condition_and_node(self):
        """SwitchCase requires both condition and node."""
        with pytest.raises(ValidationError):
            SwitchCase(
                condition="true",
                # Missing node
            )

    def test_switch_case_target_must_depend_on_switch(self):
        """Switch case target must depend on the switch node."""
        with pytest.raises(ValidationError, match="does not list.*depends_on"):
            WorkflowDefinition(
                description="Invalid switch",
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                    SwitchNode(
                        id="router",
                        type="switch",
                        cases=[
                            SwitchCase(condition="true", node="path_a"),
                        ],
                        depends_on=["step1"],
                    ),
                    # path_a doesn't depend on router - error
                    AgentNode(id="path_a", type="agent", agent_name="Agent2", depends_on=["step1"]),
                ],
                output_mapping={"result": "done"},
            )


class TestArgoAliases:
    """Tests for Argo-compatible field aliases."""

    def test_dependencies_alias(self):
        """'dependencies' alias for 'depends_on' works."""
        node = AgentNode(
            id="step1",
            type="agent",
            agent_name="Agent1",
            dependencies=["prev"],  # Argo-style
        )
        assert node.depends_on == ["prev"]

    def test_camel_case_aliases(self):
        """CamelCase aliases work for various fields."""
        workflow = WorkflowDefinition(
            description="Test",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            outputMapping={"result": "{{step1.output}}"},  # CamelCase
            inputSchema={"type": "object"},  # CamelCase
            failFast=False,  # CamelCase
        )

        assert workflow.output_mapping == {"result": "{{step1.output}}"}
        assert workflow.input_schema == {"type": "object"}
        assert workflow.fail_fast is False


class TestWorkflowInvokeNodeValidation:
    """Tests for WorkflowInvokeNode validation."""

    def test_workflow_node_requires_workflow_name(self):
        """WorkflowInvokeNode without workflow_name raises ValidationError."""
        with pytest.raises(ValidationError, match="workflow_name"):
            WorkflowInvokeNode(
                id="wf1",
                type="workflow",
                # Missing workflow_name
            )

    def test_workflow_node_valid_minimal(self):
        """WorkflowInvokeNode with minimal fields parses correctly."""
        node = WorkflowInvokeNode(
            id="invoke_analysis",
            type="workflow",
            workflow_name="analysis_workflow",
        )
        assert node.workflow_name == "analysis_workflow"
        assert node.type == "workflow"
        assert node.id == "invoke_analysis"

    def test_workflow_node_with_input_mapping(self):
        """WorkflowInvokeNode with input mapping parses correctly."""
        node = WorkflowInvokeNode(
            id="invoke_analysis",
            type="workflow",
            workflow_name="analysis_workflow",
            input={"data": "{{prepare_data.output}}"},
            depends_on=["prepare_data"],
        )
        assert node.input == {"data": "{{prepare_data.output}}"}
        assert node.depends_on == ["prepare_data"]

    def test_workflow_node_with_when_clause(self):
        """WorkflowInvokeNode with when clause parses correctly."""
        node = WorkflowInvokeNode(
            id="guarded_wf",
            type="workflow",
            workflow_name="optional_workflow",
            when="{{check.output.should_run}} == true",
        )
        assert node.when == "{{check.output.should_run}} == true"

    def test_workflow_node_with_instruction(self):
        """WorkflowInvokeNode with instruction parses correctly."""
        node = WorkflowInvokeNode(
            id="invoke_wf",
            type="workflow",
            workflow_name="analysis_workflow",
            instruction="Analyze using context: {{workflow.input.context}}",
        )
        assert node.instruction == "Analyze using context: {{workflow.input.context}}"

    def test_workflow_node_with_schema_overrides(self):
        """WorkflowInvokeNode with schema overrides parses correctly."""
        node = WorkflowInvokeNode(
            id="invoke_wf",
            type="workflow",
            workflow_name="analysis_workflow",
            input_schema_override={"type": "object", "properties": {"data": {"type": "string"}}},
            output_schema_override={"type": "object", "properties": {"result": {"type": "string"}}},
        )
        assert node.input_schema_override is not None
        assert node.output_schema_override is not None

    def test_workflow_in_workflow_definition(self):
        """WorkflowInvokeNode can be used in WorkflowDefinition."""
        workflow = WorkflowDefinition(
            description="Parent workflow with sub-workflow",
            nodes=[
                AgentNode(id="prepare", type="agent", agent_name="DataPrep"),
                WorkflowInvokeNode(
                    id="run_analysis",
                    type="workflow",
                    workflow_name="analysis_workflow",
                    input={"data": "{{prepare.output}}"},
                    depends_on=["prepare"],
                ),
            ],
            output_mapping={"result": "{{run_analysis.output}}"},
        )
        assert len(workflow.nodes) == 2
        assert workflow.nodes[1].type == "workflow"
        assert workflow.nodes[1].workflow_name == "analysis_workflow"

    def test_workflow_node_in_chain(self):
        """WorkflowInvokeNode can be chained with other nodes."""
        workflow = WorkflowDefinition(
            description="Workflow with sub-workflow in chain",
            nodes=[
                AgentNode(id="prepare", type="agent", agent_name="DataPrep"),
                WorkflowInvokeNode(
                    id="analyze",
                    type="workflow",
                    workflow_name="analysis_workflow",
                    depends_on=["prepare"],
                ),
                AgentNode(
                    id="summarize",
                    type="agent",
                    agent_name="Summarizer",
                    depends_on=["analyze"],
                ),
            ],
            output_mapping={"result": "{{summarize.output}}"},
        )
        assert len(workflow.nodes) == 3
        assert workflow.nodes[0].type == "agent"
        assert workflow.nodes[1].type == "workflow"
        assert workflow.nodes[2].type == "agent"
        assert workflow.nodes[2].depends_on == ["analyze"]


class TestMaxCallDepthValidation:
    """Tests for max_call_depth configuration validation."""

    def test_max_call_depth_default_value(self):
        """max_call_depth defaults to 10."""
        workflow = WorkflowDefinition(
            description="Workflow with default depth",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )
        assert workflow.max_call_depth == 10

    def test_max_call_depth_custom_value(self):
        """max_call_depth can be set to a custom value."""
        workflow = WorkflowDefinition(
            description="Workflow with custom depth",
            max_call_depth=5,
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )
        assert workflow.max_call_depth == 5

    def test_max_call_depth_camel_case_alias(self):
        """maxCallDepth alias works for max_call_depth."""
        workflow = WorkflowDefinition(
            description="Workflow with camelCase alias",
            maxCallDepth=15,
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )
        assert workflow.max_call_depth == 15

    def test_max_call_depth_minimum_value(self):
        """max_call_depth must be at least 1."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            WorkflowDefinition(
                description="Invalid depth",
                max_call_depth=0,
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                ],
                output_mapping={"result": "{{step1.output}}"},
            )

    def test_max_call_depth_rejects_negative(self):
        """max_call_depth rejects negative values."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            WorkflowDefinition(
                description="Invalid depth",
                max_call_depth=-5,
                nodes=[
                    AgentNode(id="step1", type="agent", agent_name="Agent1"),
                ],
                output_mapping={"result": "{{step1.output}}"},
            )
