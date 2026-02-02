"""
Unit tests for workflow agent card JSON configuration.

Tests that the workflow configuration is correctly serialized to JSON
for inclusion in the agent card extension.
"""

import pytest
from typing import Any, Dict

from solace_agent_mesh.workflow.app import (
    WorkflowDefinition,
    AgentNode,
    SwitchNode,
    SwitchCase,
    LoopNode,
    MapNode,
)


def get_workflow_config_json(workflow_definition: WorkflowDefinition) -> Dict[str, Any]:
    """
    Convert a WorkflowDefinition to a JSON-serializable dict.

    This mirrors the logic in WorkflowExecutorComponent._get_workflow_config_json()
    """
    nodes_json = []
    for node in workflow_definition.nodes:
        node_dict = {
            "id": node.id,
            "type": node.type,
        }
        if node.depends_on:
            node_dict["depends_on"] = node.depends_on

        # Add type-specific fields
        if node.type == "agent":
            node_dict["agent_name"] = node.agent_name
            if node.input:
                node_dict["input"] = node.input
        elif node.type == "switch":
            node_dict["cases"] = [
                {"condition": c.condition, "node": c.node}
                for c in node.cases
            ]
            if node.default:
                node_dict["default"] = node.default
        elif node.type == "map":
            node_dict["node"] = node.node
            node_dict["items"] = node.items
        elif node.type == "loop":
            node_dict["node"] = node.node
            if node.condition:
                node_dict["condition"] = node.condition
            if node.max_iterations:
                node_dict["max_iterations"] = node.max_iterations

        nodes_json.append(node_dict)

    config = {
        "nodes": nodes_json,
    }

    if workflow_definition.description:
        config["description"] = workflow_definition.description
    if workflow_definition.input_schema:
        config["input_schema"] = workflow_definition.input_schema
    if workflow_definition.output_schema:
        config["output_schema"] = workflow_definition.output_schema
    if workflow_definition.version:
        config["version"] = workflow_definition.version

    return config


class TestWorkflowConfigJson:
    """Tests for workflow configuration JSON serialization."""

    def test_simple_agent_workflow(self):
        """Simple workflow with agent nodes serializes correctly."""
        workflow = WorkflowDefinition(
            description="Simple workflow",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
                AgentNode(id="step2", type="agent", agent_name="Agent2", depends_on=["step1"]),
            ],
            output_mapping={"result": "{{step2.output}}"},
        )

        config = get_workflow_config_json(workflow)

        assert config["description"] == "Simple workflow"
        assert len(config["nodes"]) == 2

        # Check first node
        assert config["nodes"][0]["id"] == "step1"
        assert config["nodes"][0]["type"] == "agent"
        assert config["nodes"][0]["agent_name"] == "Agent1"
        assert "depends_on" not in config["nodes"][0]

        # Check second node
        assert config["nodes"][1]["id"] == "step2"
        assert config["nodes"][1]["type"] == "agent"
        assert config["nodes"][1]["agent_name"] == "Agent2"
        assert config["nodes"][1]["depends_on"] == ["step1"]

    def test_workflow_with_schemas(self):
        """Workflow with input/output schemas includes them in config."""
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

        config = get_workflow_config_json(workflow)

        assert "input_schema" in config
        assert config["input_schema"]["type"] == "object"
        assert "name" in config["input_schema"]["properties"]

        assert "output_schema" in config
        assert config["output_schema"]["type"] == "object"

    def test_workflow_with_switch_node(self):
        """Workflow with switch node serializes cases correctly."""
        workflow = WorkflowDefinition(
            description="Switch workflow",
            nodes=[
                AgentNode(id="start", type="agent", agent_name="Agent1"),
                SwitchNode(
                    id="router",
                    type="switch",
                    cases=[
                        SwitchCase(condition="{{start.output.value}} > 10", node="path_high"),
                        SwitchCase(condition="{{start.output.value}} > 5", node="path_medium"),
                    ],
                    default="path_low",
                    depends_on=["start"],
                ),
                AgentNode(id="path_high", type="agent", agent_name="HighAgent", depends_on=["router"]),
                AgentNode(id="path_medium", type="agent", agent_name="MediumAgent", depends_on=["router"]),
                AgentNode(id="path_low", type="agent", agent_name="LowAgent", depends_on=["router"]),
            ],
            output_mapping={"result": "done"},
        )

        config = get_workflow_config_json(workflow)

        # Find the switch node
        switch_node = next(n for n in config["nodes"] if n["type"] == "switch")

        assert switch_node["id"] == "router"
        assert len(switch_node["cases"]) == 2
        assert switch_node["cases"][0]["condition"] == "{{start.output.value}} > 10"
        assert switch_node["cases"][0]["node"] == "path_high"
        assert switch_node["cases"][1]["condition"] == "{{start.output.value}} > 5"
        assert switch_node["cases"][1]["node"] == "path_medium"
        assert switch_node["default"] == "path_low"

    def test_workflow_with_map_node(self):
        """Workflow with map node serializes items correctly."""
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

        config = get_workflow_config_json(workflow)

        # Find the map node
        map_node = next(n for n in config["nodes"] if n["type"] == "map")

        assert map_node["id"] == "process_all"
        assert map_node["node"] == "process_item"
        assert map_node["items"] == "{{prepare.output.items}}"
        assert map_node["depends_on"] == ["prepare"]

    def test_workflow_with_loop_node(self):
        """Workflow with loop node serializes condition and max_iterations."""
        workflow = WorkflowDefinition(
            description="Loop workflow",
            nodes=[
                LoopNode(
                    id="retry_loop",
                    type="loop",
                    node="attempt",
                    condition="{{attempt.output.success}} == false",
                    max_iterations=5,
                ),
                AgentNode(id="attempt", type="agent", agent_name="RetryAgent"),
            ],
            output_mapping={"result": "{{retry_loop.output}}"},
        )

        config = get_workflow_config_json(workflow)

        # Find the loop node
        loop_node = next(n for n in config["nodes"] if n["type"] == "loop")

        assert loop_node["id"] == "retry_loop"
        assert loop_node["node"] == "attempt"
        assert loop_node["condition"] == "{{attempt.output.success}} == false"
        assert loop_node["max_iterations"] == 5

    def test_agent_node_with_explicit_input(self):
        """Agent node with explicit input mapping includes it in config."""
        workflow = WorkflowDefinition(
            description="Workflow with explicit input",
            nodes=[
                AgentNode(
                    id="step1",
                    type="agent",
                    agent_name="Agent1",
                    input={"query": "{{workflow.input.user_query}}", "context": "additional context"},
                ),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )

        config = get_workflow_config_json(workflow)

        assert config["nodes"][0]["input"] == {
            "query": "{{workflow.input.user_query}}",
            "context": "additional context",
        }

    def test_workflow_without_schemas(self):
        """Workflow without schemas omits them from config."""
        workflow = WorkflowDefinition(
            description="Simple workflow",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
            # No input_schema or output_schema
        )

        config = get_workflow_config_json(workflow)

        assert "description" in config
        assert "nodes" in config
        assert "input_schema" not in config
        assert "output_schema" not in config

    def test_config_is_json_serializable(self):
        """Config can be serialized to JSON without errors."""
        import json

        workflow = WorkflowDefinition(
            description="Complex workflow",
            nodes=[
                AgentNode(id="start", type="agent", agent_name="Agent1"),
                SwitchNode(
                    id="router",
                    type="switch",
                    cases=[SwitchCase(condition="true", node="path_a")],
                    default="path_b",
                    depends_on=["start"],
                ),
                AgentNode(id="path_a", type="agent", agent_name="AgentA", depends_on=["router"]),
                AgentNode(id="path_b", type="agent", agent_name="AgentB", depends_on=["router"]),
            ],
            output_mapping={"result": "done"},
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

        config = get_workflow_config_json(workflow)

        # This should not raise
        json_str = json.dumps(config)
        assert isinstance(json_str, str)

        # Round-trip should preserve structure
        parsed = json.loads(json_str)
        assert parsed == config

    def test_node_count_matches(self):
        """Number of nodes in config matches workflow definition."""
        workflow = WorkflowDefinition(
            description="Multi-node workflow",
            nodes=[
                AgentNode(id="a", type="agent", agent_name="Agent1"),
                AgentNode(id="b", type="agent", agent_name="Agent2", depends_on=["a"]),
                AgentNode(id="c", type="agent", agent_name="Agent3", depends_on=["a"]),
                AgentNode(id="d", type="agent", agent_name="Agent4", depends_on=["b", "c"]),
            ],
            output_mapping={"result": "{{d.output}}"},
        )

        config = get_workflow_config_json(workflow)

        assert len(config["nodes"]) == 4
        assert len(config["nodes"]) == len(workflow.nodes)


class TestAgentNodeInstruction:
    """Tests for AgentNode instruction field."""

    def test_agent_node_with_instruction(self):
        """AgentNode accepts instruction field."""
        node = AgentNode(
            id="analyze",
            type="agent",
            agent_name="DataAnalyzer",
            instruction="Analyze this data using statistical methods.",
        )
        assert node.instruction == "Analyze this data using statistical methods."

    def test_agent_node_instruction_optional(self):
        """AgentNode works without instruction field."""
        node = AgentNode(
            id="analyze",
            type="agent",
            agent_name="DataAnalyzer",
        )
        assert node.instruction is None

    def test_agent_node_with_template_instruction(self):
        """AgentNode accepts template expressions in instruction."""
        node = AgentNode(
            id="process",
            type="agent",
            agent_name="Processor",
            instruction="Process using context: {{workflow.input.context}}",
        )
        assert "{{workflow.input.context}}" in node.instruction

    def test_workflow_with_instruction_parses(self):
        """Workflow with instruction in agent node parses correctly."""
        workflow = WorkflowDefinition(
            description="Test workflow",
            nodes=[
                AgentNode(
                    id="step1",
                    type="agent",
                    agent_name="Agent1",
                    instruction="{{workflow.input.context}}",
                ),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )
        assert workflow.nodes[0].instruction == "{{workflow.input.context}}"

    def test_agent_node_with_multiline_instruction(self):
        """AgentNode accepts multiline instruction."""
        instruction = """You are being invoked as part of a workflow.
Please follow these guidelines:
1. Be thorough
2. Be concise
3. Be accurate"""
        node = AgentNode(
            id="analyze",
            type="agent",
            agent_name="Analyzer",
            instruction=instruction,
        )
        assert node.instruction == instruction
        assert "Be thorough" in node.instruction


class TestWorkflowVersion:
    """Tests for workflow version field."""

    def test_workflow_default_version(self):
        """Workflow has default version of 1.0.0 when not specified."""
        workflow = WorkflowDefinition(
            description="Test workflow",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )
        assert workflow.version == "1.0.0"

    def test_workflow_custom_version(self):
        """Workflow accepts custom version."""
        workflow = WorkflowDefinition(
            description="Test workflow",
            version="2.5.0",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )
        assert workflow.version == "2.5.0"

    def test_version_in_workflow_config_json(self):
        """Version is included in workflow config JSON."""
        workflow = WorkflowDefinition(
            description="Test workflow",
            version="3.0.0",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )

        config = get_workflow_config_json(workflow)

        assert "version" in config
        assert config["version"] == "3.0.0"

    def test_default_version_in_workflow_config_json(self):
        """Default version is included in workflow config JSON."""
        workflow = WorkflowDefinition(
            description="Test workflow",
            nodes=[
                AgentNode(id="step1", type="agent", agent_name="Agent1"),
            ],
            output_mapping={"result": "{{step1.output}}"},
        )

        config = get_workflow_config_json(workflow)

        assert "version" in config
        assert config["version"] == "1.0.0"

    def test_version_accepts_any_string(self):
        """Version field accepts any string format."""
        # Semantic versioning
        workflow1 = WorkflowDefinition(
            description="Test",
            version="1.2.3",
            nodes=[AgentNode(id="a", type="agent", agent_name="A")],
            output_mapping={"r": "v"},
        )
        assert workflow1.version == "1.2.3"

        # Pre-release version
        workflow2 = WorkflowDefinition(
            description="Test",
            version="2.0.0-alpha.1",
            nodes=[AgentNode(id="a", type="agent", agent_name="A")],
            output_mapping={"r": "v"},
        )
        assert workflow2.version == "2.0.0-alpha.1"

        # Simple version
        workflow3 = WorkflowDefinition(
            description="Test",
            version="v1",
            nodes=[AgentNode(id="a", type="agent", agent_name="A")],
            output_mapping={"r": "v"},
        )
        assert workflow3.version == "v1"
