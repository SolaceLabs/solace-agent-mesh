"""
WorkflowApp class and configuration models for Prescriptive Workflows.

Supports Argo Workflows-compatible syntax with SAM extensions.
"""

import logging
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator

from solace_ai_connector.flow.app import App
from ..common import a2a
from ..agent.sac.app import SamAgentAppConfig, AgentCardConfig, AgentCardPublishingConfig

log = logging.getLogger(__name__)

# --- Retry Strategy Models (Argo-compatible) ---


class BackoffStrategy(BaseModel):
    """Exponential backoff configuration for retries."""

    duration: str = Field(
        default="1s",
        description="Initial backoff duration. Supports: '5s', '1m', '1h'.",
    )
    factor: float = Field(
        default=2.0,
        description="Multiplier for exponential backoff.",
    )
    max_duration: Optional[str] = Field(
        default=None,
        description="Maximum backoff duration cap.",
        alias="maxDuration",
    )

    class Config:
        populate_by_name = True


class RetryStrategy(BaseModel):
    """
    Retry configuration for workflow nodes.
    Argo-compatible with extensions.
    """

    limit: int = Field(
        default=3,
        description="Maximum number of retry attempts.",
    )
    retry_policy: Literal["Always", "OnFailure", "OnError"] = Field(
        default="OnFailure",
        description="When to retry: Always, OnFailure, OnError.",
        alias="retryPolicy",
    )
    backoff: Optional[BackoffStrategy] = Field(
        default=None,
        description="Exponential backoff configuration.",
    )

    class Config:
        populate_by_name = True


# --- Exit Handler Model ---


class ExitHandler(BaseModel):
    """
    Exit handler configuration for cleanup/notification on workflow completion.

    Supports conditional handlers for different outcomes.
    """

    always: Optional[str] = Field(
        default=None,
        description="Node ID to execute regardless of workflow outcome.",
    )
    on_success: Optional[str] = Field(
        default=None,
        description="Node ID to execute only on successful completion.",
        alias="onSuccess",
    )
    on_failure: Optional[str] = Field(
        default=None,
        description="Node ID to execute only on failure.",
        alias="onFailure",
    )
    on_cancel: Optional[str] = Field(
        default=None,
        description="Node ID to execute only on cancellation.",
        alias="onCancel",
    )

    class Config:
        populate_by_name = True


# --- Workflow Node Models ---


class WorkflowNode(BaseModel):
    """
    Base workflow node.

    Supports both SAM and Argo field names:
    - depends_on / dependencies (Argo alias)
    """

    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type")
    depends_on: Optional[List[str]] = Field(
        default=None,
        description="List of node IDs this node depends on.",
        alias="dependencies",
    )

    class Config:
        populate_by_name = True


class AgentNode(WorkflowNode):
    """
    Agent invocation node.

    Argo-aligned features:
    - `when`: Conditional execution clause (Argo-style)
    - `retryStrategy`: Retry configuration
    - `timeout`: Node-specific timeout override
    - `instruction`: Optional guidance text sent to the target agent
    """

    type: Literal["agent"] = "agent"
    agent_name: str = Field(..., description="Name of agent to invoke")
    input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Input mapping. If omitted, inferred from dependencies.",
    )
    instruction: Optional[str] = Field(
        default=None,
        description=(
            "Optional instruction/guidance text sent to the target agent. "
            "Supports template expressions like '{{workflow.input.context}}'. "
            "Provides context for how the agent should process the request."
        ),
    )

    # Optional schema overrides
    input_schema_override: Optional[Dict[str, Any]] = None
    output_schema_override: Optional[Dict[str, Any]] = None

    # Argo-aligned fields
    when: Optional[str] = Field(
        default=None,
        description=(
            "Conditional execution expression (Argo-style). "
            "Node only executes if expression evaluates to true."
        ),
    )
    retry_strategy: Optional[RetryStrategy] = Field(
        default=None,
        description="Retry configuration for this node.",
        alias="retryStrategy",
    )
    timeout: Optional[str] = Field(
        default=None,
        description="Node-specific timeout. Format: '30s', '5m', '1h'.",
    )

    class Config:
        populate_by_name = True


class SwitchCase(BaseModel):
    """A single case in a switch node."""

    condition: str = Field(
        ...,
        description="Expression to evaluate for this case.",
        alias="when",
    )
    node: str = Field(
        ...,
        description="Node ID to execute if condition matches.",
        alias="then",
    )

    class Config:
        populate_by_name = True


class SwitchNode(WorkflowNode):
    """
    Multi-way conditional branching node.

    Cases are evaluated in order; first match wins.
    """

    type: Literal["switch"] = "switch"
    cases: List[SwitchCase] = Field(
        ...,
        description="Ordered list of condition/node pairs. First match wins.",
    )
    default: Optional[str] = Field(
        default=None,
        description="Node ID to execute if no cases match.",
    )


class LoopNode(WorkflowNode):
    """
    While-loop node for iterative execution until condition is met.

    Different from MapNode which is for-each iteration.
    LoopNode repeats a node until a condition becomes false.
    """

    type: Literal["loop"] = "loop"
    node: str = Field(..., description="Node ID to execute repeatedly")
    condition: str = Field(
        ...,
        description="Continue looping while this expression is true.",
    )
    max_iterations: int = Field(
        default=100,
        description="Safety limit on number of iterations.",
        alias="maxIterations",
    )
    delay: Optional[str] = Field(
        default=None,
        description="Delay between loop iterations. Format: '5s', '1m', '1h', '1d'.",
    )

    class Config:
        populate_by_name = True


class MapNode(WorkflowNode):
    """
    Map (parallel iteration) node.

    Supports both SAM syntax and Argo-style withItems/withParam.
    """

    type: Literal["map"] = "map"

    # Primary SAM field
    items: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="Array template reference or expression to iterate over.",
    )

    # Argo aliases
    with_param: Optional[str] = Field(
        default=None,
        description="Argo-style: JSON array from previous step output.",
        alias="withParam",
    )
    with_items: Optional[List[Any]] = Field(
        default=None,
        description="Argo-style: Static list of items to iterate over.",
        alias="withItems",
    )

    node: str = Field(..., description="Node ID to execute for each item")
    max_items: Optional[int] = Field(
        default=100,
        description="Maximum items to process (safety limit).",
        alias="maxItems",
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="Max concurrent executions. None means unlimited.",
        alias="concurrencyLimit",
    )

    class Config:
        populate_by_name = True

    @model_validator(mode="after")
    def validate_items_source(self) -> "MapNode":
        """Ensure exactly one items source is provided."""
        sources = [
            self.items is not None,
            self.with_param is not None,
            self.with_items is not None,
        ]
        if sum(sources) == 0:
            raise ValueError(
                "MapNode requires one of: 'items', 'withParam', or 'withItems'"
            )
        if sum(sources) > 1:
            raise ValueError(
                "MapNode accepts only one of: 'items', 'withParam', or 'withItems'"
            )
        return self

    def get_items_expression(self) -> Union[str, List[Any], Dict[str, Any]]:
        """Return the items source regardless of which field was used."""
        if self.items is not None:
            return self.items
        if self.with_param is not None:
            return self.with_param
        return self.with_items


class WorkflowInvokeNode(WorkflowNode):
    """
    Workflow invocation node.

    Calls another workflow as a sub-workflow.
    Since workflows register as agents, this reuses the agent calling mechanism.

    Argo-aligned features:
    - `when`: Conditional execution clause (Argo-style)
    - `retryStrategy`: Retry configuration
    - `timeout`: Node-specific timeout override
    - `instruction`: Optional guidance text sent to the target workflow
    """

    type: Literal["workflow"] = "workflow"
    workflow_name: str = Field(..., description="Name of workflow to invoke")
    input: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Input mapping. If omitted, inferred from dependencies.",
    )
    instruction: Optional[str] = Field(
        default=None,
        description=(
            "Optional instruction/guidance text sent to the target workflow. "
            "Supports template expressions like '{{workflow.input.context}}'."
        ),
    )

    # Optional schema overrides
    input_schema_override: Optional[Dict[str, Any]] = None
    output_schema_override: Optional[Dict[str, Any]] = None

    # Argo-aligned fields
    when: Optional[str] = Field(
        default=None,
        description=(
            "Conditional execution expression (Argo-style). "
            "Node only executes if expression evaluates to true."
        ),
    )
    retry_strategy: Optional[RetryStrategy] = Field(
        default=None,
        description="Retry configuration for this node.",
        alias="retryStrategy",
    )
    timeout: Optional[str] = Field(
        default=None,
        description="Node-specific timeout. Format: '30s', '5m', '1h'.",
    )

    class Config:
        populate_by_name = True


# Union type for polymorphic node list
WorkflowNodeUnion = Union[
    AgentNode,
    SwitchNode,
    LoopNode,
    MapNode,
    WorkflowInvokeNode,
]


class WorkflowDefinition(BaseModel):
    """
    Complete workflow definition.

    Argo-aligned features:
    - onExit: Exit handler for cleanup/notification
    - failFast: Control behavior on node failure
    - retryStrategy: Default retry strategy for all nodes
    """

    description: str = Field(..., description="Human-readable workflow description")

    version: str = Field(
        default="1.0.0",
        description="User-defined version of the workflow (semantic versioning recommended)",
    )

    input_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for workflow input.",
        alias="inputSchema",
    )

    output_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for workflow output.",
        alias="outputSchema",
    )

    nodes: List[WorkflowNodeUnion] = Field(
        ...,
        description="Workflow nodes (DAG vertices).",
    )

    output_mapping: Dict[str, Any] = Field(
        ...,
        description="Mapping from node outputs to final workflow output.",
        alias="outputMapping",
    )

    skills: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Workflow skills for agent card.",
    )

    # Argo-aligned fields
    on_exit: Optional[Union[str, ExitHandler]] = Field(
        default=None,
        description=(
            "Exit handler configuration. Can be a node ID (string) or "
            "ExitHandler object with on_success/on_failure/on_cancel/always."
        ),
        alias="onExit",
    )

    fail_fast: bool = Field(
        default=True,
        description=(
            "If true, stop scheduling new nodes when one fails. "
            "Running nodes continue to completion."
        ),
        alias="failFast",
    )

    max_call_depth: int = Field(
        default=10,
        ge=1,
        description=(
            "Maximum allowed call depth for sub-workflow/agent invocations. "
            "Prevents infinite recursion."
        ),
        alias="maxCallDepth",
    )

    retry_strategy: Optional[RetryStrategy] = Field(
        default=None,
        description="Default retry strategy for all nodes (can be overridden per-node).",
        alias="retryStrategy",
    )

    class Config:
        populate_by_name = True

    @model_validator(mode="after")
    def validate_dag_structure(self) -> "WorkflowDefinition":
        """Validate DAG has valid references and consistent control flow."""
        node_map = {node.id: node for node in self.nodes}

        for node in self.nodes:
            # Check dependencies reference valid nodes
            if node.depends_on:
                for dep in node.depends_on:
                    if dep not in node_map:
                        raise ValueError(
                            f"Node '{node.id}' depends on non-existent node '{dep}'"
                        )

            # Validate Switch Node Consistency
            if node.type == "switch":
                for i, case in enumerate(node.cases):
                    self._validate_branch_dependency(
                        node, case.node, f"cases[{i}].node", node_map
                    )
                if node.default:
                    self._validate_branch_dependency(
                        node, node.default, "default", node_map
                    )

            # Validate LoopNode target reference
            if node.type == "loop":
                if node.node not in node_map:
                    raise ValueError(
                        f"LoopNode '{node.id}' references non-existent node '{node.node}'"
                    )

            # Validate MapNode target reference
            if node.type == "map":
                if node.node not in node_map:
                    raise ValueError(
                        f"MapNode '{node.id}' references non-existent node '{node.node}'"
                    )

        # Validate exit handler references
        if self.on_exit:
            if isinstance(self.on_exit, str):
                if self.on_exit not in node_map:
                    raise ValueError(
                        f"onExit references non-existent node '{self.on_exit}'"
                    )
            else:
                for field, node_id in [
                    ("always", self.on_exit.always),
                    ("on_success", self.on_exit.on_success),
                    ("on_failure", self.on_exit.on_failure),
                    ("on_cancel", self.on_exit.on_cancel),
                ]:
                    if node_id and node_id not in node_map:
                        raise ValueError(
                            f"onExit.{field} references non-existent node '{node_id}'"
                        )

        return self

    def _validate_branch_dependency(
        self,
        parent: WorkflowNode,
        target_id: str,
        branch_name: str,
        node_map: Dict[str, WorkflowNode],
    ):
        """Ensure target node depends on parent node."""
        target = node_map.get(target_id)
        if not target:
            raise ValueError(
                f"Node '{parent.id}' references non-existent {branch_name} '{target_id}'"
            )

        if not target.depends_on or parent.id not in target.depends_on:
            raise ValueError(
                f"Logic Error: Node '{parent.id}' routes to '{target.id}' ({branch_name}), "
                f"but '{target.id}' does not list '{parent.id}' in its 'depends_on' field. "
                f"This would cause '{target.id}' to run immediately. "
                f"Fix: Add 'depends_on: [{parent.id}]' to node '{target.id}'."
            )


class WorkflowAppConfig(SamAgentAppConfig):
    """Workflow app configuration extends agent config."""

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
    default_max_map_items: int = Field(
        default=100, description="Default max items for map nodes"
    )

    # Override optional fields from SamAgentAppConfig that might not be needed or have different defaults
    model: Optional[Union[str, Dict[str, Any]]] = None
    instruction: Optional[Any] = None

    # Make agent_card optional as it is auto-generated from workflow definition
    agent_card: Optional[AgentCardConfig] = Field(
        default_factory=lambda: AgentCardConfig(),
        description="Static definition of this agent's capabilities for discovery."
    )
    
    # Make agent_card_publishing optional with defaults
    agent_card_publishing: Optional[AgentCardPublishingConfig] = Field(
        default_factory=lambda: AgentCardPublishingConfig(interval_seconds=10),
        description="Settings for publishing the agent card."
    )


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

        # Discovery topic for agent cards
        subscriptions.append({"topic": a2a.get_discovery_subscription_topic(namespace)})

        # Workflow's agent request topic
        subscriptions.append(
            {"topic": a2a.get_agent_request_topic(namespace, workflow_name)}
        )

        # Agent response topics (wildcard)
        subscriptions.append(
            {
                "topic": a2a.get_agent_response_subscription_topic(
                    namespace, workflow_name
                )
            }
        )

        # Agent status topics (wildcard)
        subscriptions.append(
            {
                "topic": a2a.get_agent_status_subscription_topic(
                    namespace, workflow_name
                )
            }
        )

        return subscriptions
