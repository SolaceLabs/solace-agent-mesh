"""
WorkflowApp class and configuration models for Prescriptive Workflows.
"""

import logging
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator

from solace_ai_connector.flow.app import App
from ..common import a2a
from ..agent.sac.app import SamAgentAppConfig

log = logging.getLogger(__name__)

# --- Workflow Configuration Models ---


class ForkBranch(BaseModel):
    """A single branch in a fork node."""

    id: str = Field(..., description="Branch identifier")
    agent_persona: str = Field(..., description="Agent for this branch")
    input: Dict[str, Any] = Field(..., description="Input mapping")
    output_key: str = Field(..., description="Key for merging result")


class WorkflowNode(BaseModel):
    """Base workflow node."""

    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type")
    depends_on: Optional[List[str]] = Field(
        None, description="List of node IDs this node depends on"
    )


class AgentNode(WorkflowNode):
    """Agent invocation node."""

    type: Literal["agent"] = "agent"
    agent_persona: str = Field(..., description="Name of agent to invoke")
    input: Dict[str, Any] = Field(..., description="Input mapping")

    # Optional schema overrides
    input_schema_override: Optional[Dict[str, Any]] = None
    output_schema_override: Optional[Dict[str, Any]] = None


class ConditionalNode(WorkflowNode):
    """Conditional branching node."""

    type: Literal["conditional"] = "conditional"
    condition: str = Field(..., description="Expression to evaluate")
    true_branch: str = Field(..., description="Node ID if true")
    false_branch: Optional[str] = Field(None, description="Node ID if false")


class ForkNode(WorkflowNode):
    """Parallel execution node."""

    type: Literal["fork"] = "fork"
    branches: List[ForkBranch] = Field(..., description="Parallel branches")


class LoopNode(WorkflowNode):
    """Loop iteration node."""

    type: Literal["loop"] = "loop"
    loop_over: str = Field(..., description="Array template reference")
    loop_node: str = Field(..., description="Node ID to execute per iteration")
    max_iterations: Optional[int] = Field(100, description="Max iterations")


# Union type for polymorphic node list
WorkflowNodeUnion = Union[AgentNode, ConditionalNode, ForkNode, LoopNode]


class WorkflowDefinition(BaseModel):
    """Complete workflow definition."""

    description: str = Field(..., description="Human-readable workflow description")

    input_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for workflow input"
    )

    output_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for workflow output"
    )

    nodes: List[WorkflowNodeUnion] = Field(
        ..., description="Workflow nodes (DAG vertices)"
    )

    output_mapping: Dict[str, Any] = Field(
        ..., description="Mapping from node outputs to final workflow output"
    )

    skills: Optional[List[Dict[str, Any]]] = Field(
        None, description="Workflow skills for agent card"
    )

    @model_validator(mode="after")
    def validate_dag_structure(self) -> "WorkflowDefinition":
        """Validate DAG has no cycles and valid references."""
        node_ids = {node.id for node in self.nodes}

        for node in self.nodes:
            # Check dependencies reference valid nodes
            if node.depends_on:
                for dep in node.depends_on:
                    if dep not in node_ids:
                        raise ValueError(
                            f"Node '{node.id}' depends on non-existent node '{dep}'"
                        )

        # Check for cycles (implemented in DAGExecutor)
        # For now, basic check passes

        return self


class WorkflowAppConfig(SamAgentAppConfig):
    """Workflow app configuration extends agent config."""

    # Override type indicator (optional, but good for clarity)
    # agent_type: Literal["workflow"] = "workflow"

    # Workflow definition
    workflow: WorkflowDefinition = Field(..., description="The workflow DAG definition")

    # Workflow execution settings
    max_workflow_execution_time_seconds: int = Field(
        default=1800,  # 30 minutes
        description="Maximum time for entire workflow execution",
    )
    default_node_timeout_seconds: int = Field(
        default=300,  # 5 minutes
        description="Default timeout for individual nodes",
    )
    node_cancellation_timeout_seconds: int = Field(
        default=30,
        description="Time to wait for a node to confirm cancellation before force-failing.",
    )
    default_max_loop_iterations: int = Field(
        default=100, description="Default max iterations for loop nodes"
    )

    # Override optional fields from SamAgentAppConfig that might not be needed or have different defaults
    model: Optional[Union[str, Dict[str, Any]]] = None
    instruction: Optional[Any] = None


class WorkflowApp(App):
    """Custom App class for workflow orchestration."""

    # Define app schema for validation (empty for now, could be extended)
    app_schema: Dict[str, Any] = {"config_parameters": []}

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log.debug("Initializing WorkflowApp...")

        app_config_dict = app_info.get("app_config", {})

        try:
            # Validate configuration
            app_config = WorkflowAppConfig.model_validate_and_clean(app_config_dict)
        except Exception as e:
            log.error(f"Workflow configuration validation failed: {e}")
            raise

        # Extract workflow-specific settings
        namespace = app_config.namespace
        workflow_name = app_config.agent_name
        # workflow_def = app_config.workflow  # Available if needed for future enhancements

        # Auto-populate agent card with workflow schemas in skills
        # Note: AgentCardConfig doesn't have input_schema/output_schema directly
        # These should be specified in the agent_card.skills in the YAML config
        # or they can be added to the workflow definition's skills field

        # Generate subscriptions
        subscriptions = self._generate_subscriptions(namespace, workflow_name)

        # Build component configuration
        component_info = {
            "component_name": workflow_name,
            "component_module": "solace_agent_mesh.workflow.component",
            "component_config": {"app_config": app_config.model_dump()},
            "subscriptions": subscriptions,  # Include subscriptions in component
        }

        # Update app_info with validated config
        app_info["app_config"] = app_config.model_dump()
        app_info["components"] = [component_info]  # Use 'components' not 'component_list'

        # Configure broker for workflow messaging
        broker_config = app_info.setdefault("broker", {})
        broker_config["input_enabled"] = True
        broker_config["output_enabled"] = True
        log.debug("Injected broker.input_enabled=True and broker.output_enabled=True")

        generated_queue_name = f"{namespace.strip('/')}/q/a2a/{workflow_name}"
        broker_config["queue_name"] = generated_queue_name
        log.debug("Injected generated broker.queue_name: %s", generated_queue_name)

        broker_config["temporary_queue"] = app_info.get("broker", {}).get(
            "temporary_queue", True
        )
        log.debug(
            "Set broker_config.temporary_queue = %s", broker_config["temporary_queue"]
        )

        # Call parent App constructor
        super().__init__(app_info, **kwargs)

    def _generate_subscriptions(
        self, namespace: str, workflow_name: str
    ) -> List[Dict[str, str]]:
        """Generate Solace topic subscriptions for workflow."""
        subscriptions = []

        # Discovery topic for persona agent cards
        subscriptions.append({"topic": a2a.get_discovery_topic(namespace)})

        # Workflow's agent request topic
        subscriptions.append(
            {"topic": a2a.get_agent_request_topic(namespace, workflow_name)}
        )

        # Persona response topics (wildcard)
        subscriptions.append(
            {
                "topic": a2a.get_agent_response_subscription_topic(
                    namespace, workflow_name
                )
            }
        )

        # Persona status topics (wildcard)
        subscriptions.append(
            {
                "topic": a2a.get_agent_status_subscription_topic(
                    namespace, workflow_name
                )
            }
        )

        return subscriptions
