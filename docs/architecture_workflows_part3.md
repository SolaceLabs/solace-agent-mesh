# Prescriptive Workflows - Architecture Design Document (Part 3 of 3)

**Document Version:** 1.0
**Last Updated:** 2025-11-13
**Status:** Draft

**Note:** This is Part 3 of a three-part document. See Parts 1 and 2 for Sections 1-3.4.

---

### 3.5. Persona Caller

#### 3.5.1. A2A Request Construction

PersonaCaller handles communication with persona agents via A2A:

```python
class PersonaCaller:
    """Manages A2A calls to persona agents from workflow."""

    def __init__(self, host_component: WorkflowExecutorComponent):
        self.host = host_component

    async def call_persona(
        self,
        node: WorkflowNode,
        workflow_state: WorkflowExecutionState,
        workflow_context: WorkflowExecutionContext
    ) -> str:
        """
        Invoke a persona agent for a workflow node.
        Returns sub-task ID for correlation.
        """
        log_id = f"{self.host.log_identifier}[CallPersona:{node.agent_persona}]"

        # Generate sub-task ID
        sub_task_id = f"wf_{workflow_state.execution_id}_{node.id}_{uuid.uuid4().hex[:8]}"

        # Resolve input data
        input_data = await self._resolve_node_input(node, workflow_state)

        # Get persona schemas from agent registry
        persona_card = self.host.agent_registry.get_agent(node.agent_persona)
        input_schema = node.input_schema_override or \
            (persona_card.input_schema if persona_card else None)
        output_schema = node.output_schema_override or \
            (persona_card.output_schema if persona_card else None)

        # Construct A2A message
        message = self._construct_persona_message(
            node,
            input_data,
            input_schema,
            output_schema,
            workflow_state,
            sub_task_id
        )

        # Publish request
        await self._publish_persona_request(
            node.agent_persona,
            message,
            sub_task_id,
            workflow_context
        )

        # Track in workflow context
        workflow_context.track_persona_call(node.id, sub_task_id)

        return sub_task_id

    def _construct_persona_message(
        self,
        node: WorkflowNode,
        input_data: Dict[str, Any],
        input_schema: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        workflow_state: WorkflowExecutionState,
        sub_task_id: str
    ) -> A2AMessage:
        """Construct A2A message for persona agent."""

        # Build message parts
        parts = []

        # 1. Workflow context (must be first)
        workflow_data = WorkflowNodeRequestData(
            type="workflow_node_request",
            workflow_name=workflow_state.workflow_name,
            node_id=node.id,
            input_schema=input_schema,
            output_schema=output_schema
        )
        parts.append(a2a.create_data_part(data=workflow_data.model_dump()))

        # 2. User query/text content
        if "query" in input_data:
            parts.append(a2a.create_text_part(text=input_data["query"]))

        # 3. Additional input data
        for key, value in input_data.items():
            if key != "query":
                parts.append(a2a.create_data_part(data={key: value}))

        # Construct message
        message = A2AMessage(
            parts=parts,
            contextId=workflow_state.execution_id,
            metadata={
                "workflow_name": workflow_state.workflow_name,
                "node_id": node.id,
                "sub_task_id": sub_task_id
            }
        )

        return message
```

#### 3.5.2. Response Handling

PersonaCaller coordinates response handling with DAGExecutor:

```python
async def _publish_persona_request(
    self,
    persona_name: str,
    message: A2AMessage,
    sub_task_id: str,
    workflow_context: WorkflowExecutionContext
):
    """Publish A2A request to persona agent."""

    # Get persona request topic
    request_topic = a2a.get_agent_request_topic(
        self.host.namespace,
        persona_name
    )

    # Create SendMessageRequest
    send_params = MessageSendParams(message=message)
    a2a_request = SendMessageRequest(id=sub_task_id, params=send_params)

    # Construct reply-to and status topics
    reply_to_topic = a2a.get_agent_response_topic(
        self.host.namespace,
        self.host.workflow_name,
        sub_task_id
    )
    status_topic = a2a.get_peer_agent_status_topic(
        self.host.namespace,
        self.host.workflow_name,
        sub_task_id
    )

    # User properties
    user_properties = {
        "replyTo": reply_to_topic,
        "a2aStatusTopic": status_topic,
        "userId": workflow_context.a2a_context["user_id"],
        "a2aUserConfig": workflow_context.a2a_context.get("a2a_user_config", {})
    }

    # Publish request
    self.host.publish_a2a_message(
        payload=a2a_request.model_dump(by_alias=True, exclude_none=True),
        topic=request_topic,
        user_properties=user_properties
    )

    # Set timeout tracking
    timeout_seconds = self.host.get_config("default_node_timeout_seconds", 300)
    self.host.cache_service.add_data(
        key=sub_task_id,
        value=workflow_context.workflow_task_id,
        expiry=timeout_seconds,
        component=self.host
    )
```

#### 3.5.3. Timeout Management

Persona call timeouts are handled via cache expiry:

```python
# In WorkflowExecutorComponent
async def handle_cache_expiry_event(self, cache_data: Dict[str, Any]):
    """Handle persona call timeout via cache expiry."""
    sub_task_id = cache_data.get("key")
    workflow_task_id = cache_data.get("expired_data")

    if not sub_task_id or not workflow_task_id:
        return

    # Find workflow context
    with self.active_workflows_lock:
        workflow_context = self.active_workflows.get(workflow_task_id)

    if not workflow_context:
        log.warning(
            f"{self.log_identifier} Timeout for unknown workflow: {workflow_task_id}"
        )
        return

    # Get node ID for this sub-task
    node_id = workflow_context.get_node_id_for_sub_task(sub_task_id)

    if not node_id:
        return

    log.error(
        f"{self.log_identifier} Persona call timed out for node '{node_id}' "
        f"(sub-task: {sub_task_id})"
    )

    # Create timeout error
    result_data = WorkflowNodeResultData(
        type="workflow_node_result",
        status="failure",
        error_message=f"Persona agent timed out after {timeout_seconds} seconds"
    )

    # Handle as node failure
    await self.dag_executor.handle_node_completion(
        workflow_context,
        sub_task_id,
        result_data
    )
```

#### 3.5.4. Correlation Tracking

PersonaCaller maintains correlation between sub-tasks and nodes:

```python
class WorkflowExecutionContext:
    """Context for tracking a workflow execution."""

    def __init__(self, workflow_task_id: str, a2a_context: Dict):
        self.workflow_task_id = workflow_task_id
        self.a2a_context = a2a_context
        self.workflow_state: Optional[WorkflowExecutionState] = None

        # Sub-task tracking
        self.sub_task_to_node: Dict[str, str] = {}  # sub_task_id -> node_id
        self.node_to_sub_task: Dict[str, str] = {}  # node_id -> sub_task_id
        self.lock = threading.Lock()

    def track_persona_call(self, node_id: str, sub_task_id: str):
        """Track correlation between node and sub-task."""
        with self.lock:
            self.sub_task_to_node[sub_task_id] = node_id
            self.node_to_sub_task[node_id] = sub_task_id

    def get_node_id_for_sub_task(self, sub_task_id: str) -> Optional[str]:
        """Get node ID for a sub-task."""
        with self.lock:
            return self.sub_task_to_node.get(sub_task_id)

    def get_sub_task_for_node(self, node_id: str) -> Optional[str]:
        """Get sub-task ID for a node."""
        with self.lock:
            return self.node_to_sub_task.get(node_id)
```

---

## 4. Flow Control Implementation

### 4.1. Sequential Execution

#### 4.1.1. Dependency-Based Ordering

Sequential execution is implemented through dependency resolution in DAGExecutor. Nodes execute in dependency order:

```python
# Example workflow with sequential nodes
nodes = [
    {"id": "extract", "depends_on": []},
    {"id": "validate", "depends_on": ["extract"]},
    {"id": "transform", "depends_on": ["validate"]},
    {"id": "store", "depends_on": ["transform"]}
]

# Execution order: extract -> validate -> transform -> store
```

The DAGExecutor ensures:
- Nodes wait for all dependencies to complete
- Dependencies are checked before each execution cycle
- Completed nodes are tracked in workflow state

#### 4.1.2. Input Mapping Resolution

Input mapping resolves references to previous node outputs:

```python
async def _resolve_node_input(
    self,
    node: WorkflowNode,
    workflow_state: WorkflowExecutionState
) -> Dict[str, Any]:
    """Resolve input mapping for a node."""
    resolved_input = {}

    for key, value in node.input.items():
        if isinstance(value, str) and value.startswith("{{"):
            # Template reference
            resolved_value = self._resolve_template(value, workflow_state)
            resolved_input[key] = resolved_value
        else:
            # Literal value
            resolved_input[key] = value

    return resolved_input

def _resolve_template(
    self,
    template: str,
    workflow_state: WorkflowExecutionState
) -> Any:
    """
    Resolve template variable.
    Format: {{node_id.output.field_path}}
    """
    # Extract variable path
    match = re.match(r'\{\{(.+?)\}\}', template)
    if not match:
        return template

    path = match.group(1)
    parts = path.split('.')

    # Navigate path in workflow state
    if parts[0] == "workflow" and parts[1] == "input":
        # Reference to workflow input
        # TODO: implement workflow input storage
        pass
    else:
        # Reference to node output
        node_id = parts[0]
        if node_id not in workflow_state.node_outputs:
            raise ValueError(f"Referenced node '{node_id}' has not completed")

        # Navigate remaining path
        data = workflow_state.node_outputs[node_id]
        for part in parts[1:]:
            data = data[part]

        return data

# Note for MVP: This implementation loads the entire output of a previous node
# into memory for value resolution. For large artifacts, this could be inefficient.
# A future enhancement will support passing large artifacts by reference.
```

### 4.2. Conditional Branching (If/Else, Case/Switch)

#### 4.2.1. Expression Evaluation

Conditional nodes evaluate expressions to determine branch selection:

```python
class ConditionalNode(WorkflowNode):
    """Conditional branching node."""
    type: Literal["conditional"] = "conditional"
    condition: str  # Expression to evaluate
    true_branch: str  # Node ID to execute if true
    false_branch: Optional[str] = None  # Node ID to execute if false

# In DAGExecutor
async def _execute_conditional_node(
    self,
    node: ConditionalNode,
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """Execute conditional node."""
    log_id = f"{self.host.log_identifier}[Conditional:{node.id}]"

    # Evaluate condition
    from .conditional import evaluate_condition
    result = evaluate_condition(node.condition, workflow_state)

    log.info(
        f"{log_id} Condition '{node.condition}' evaluated to: {result}"
    )

    # Select branch
    next_node_id = node.true_branch if result else node.false_branch

    if next_node_id:
        # Mark conditional as complete
        workflow_state.completed_nodes[node.id] = None

        # Add selected branch to dependencies
        # (modify graph to make next_node depend on this conditional)
        self.dependencies[next_node_id] = [node.id]
    else:
        # No branch to execute (false with no false_branch)
        workflow_state.completed_nodes[node.id] = None

    # Nodes on the un-taken branch will be skipped automatically by the
    # DAGExecutor, as their dependencies will never be met.
```

#### 4.2.2. Branch Selection Logic

Expression evaluation uses simpleeval for safety:

```python
# In agent/workflow/flow_control/conditional.py
from simpleeval import simple_eval

def evaluate_condition(
    condition_expr: str,
    workflow_state: WorkflowExecutionState
) -> bool:
    """
    Safely evaluate conditional expression.
    Returns boolean result.
    """
    # Build context from completed nodes
    context = {}
    for node_id, artifact_name in workflow_state.completed_nodes.items():
        if artifact_name:  # Skip flow control nodes
            context[node_id] = {
                "output": workflow_state.node_outputs.get(node_id, {}).get("output", {})
            }

    # Add safe functions
    functions = {
        "true": True,
        "false": False,
        "null": None
    }

    try:
        result = simple_eval(
            condition_expr,
            names=context,
            functions=functions
        )
        return bool(result)
    except Exception as e:
        raise ConditionalEvaluationError(
            f"Failed to evaluate condition '{condition_expr}': {e}"
        ) from e
```

#### 4.2.3. Context Access Patterns

Conditions can access node outputs using dot notation:

```
{{validate.output.is_valid}} == true
{{validate.output.score}} > 0.8
{{routing.output.category}} == "premium"
```

The evaluator resolves these references from workflow_state.node_outputs.

### 4.3. Parallel Execution (Fork/Join)

#### 4.3.1. Concurrent Branch Execution

Fork nodes execute multiple branches in parallel:

```python
class ForkNode(WorkflowNode):
    """Parallel execution node."""
    type: Literal["fork"] = "fork"
    branches: List[ForkBranch]

class ForkBranch(BaseModel):
    """A single branch in a fork."""
    id: str  # Branch node ID
    agent_persona: str
    input: Dict[str, Any]
    output_key: str  # Key for merging branch result

# In DAGExecutor
async def _execute_fork_node(
    self,
    node: ForkNode,
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """Execute fork node with parallel branches."""
    log_id = f"{self.host.log_identifier}[Fork:{node.id}]"

    # Track active branches
    branch_sub_tasks = []

    # Launch all branches concurrently
    for branch in node.branches:
        log.info(f"{log_id} Starting branch '{branch.id}'")

        # Create temporary node for branch
        branch_node = WorkflowNode(
            id=branch.id,
            type="agent",
            agent_persona=branch.agent_persona,
            input=branch.input,
            depends_on=[node.id]  # Depends on fork node
        )

        # Execute branch (returns immediately with sub-task ID)
        sub_task_id = await self.host.persona_caller.call_persona(
            branch_node,
            workflow_state,
            workflow_context
        )

        branch_sub_tasks.append({
            "branch_id": branch.id,
            "output_key": branch.output_key,
            "sub_task_id": sub_task_id
        })

    # Store branch tracking in workflow state
    workflow_state.active_branches[node.id] = branch_sub_tasks

    # Mark fork as pending (not complete until all branches finish)
    workflow_state.pending_nodes.append(node.id)
```

#### 4.3.2. Response Collection

As branch responses arrive, track completion:

```python
async def handle_fork_branch_completion(
    self,
    fork_node_id: str,
    branch_id: str,
    result: WorkflowNodeResultData,
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """Handle completion of a fork branch."""
    log_id = f"{self.host.log_identifier}[Fork:{fork_node_id}]"

    # Get branch tracking
    branches = workflow_state.active_branches.get(fork_node_id, [])

    # Find this branch
    branch_info = None
    for b in branches:
        if b["branch_id"] == branch_id:
            branch_info = b
            break

    if not branch_info:
        log.error(f"{log_id} Unknown branch '{branch_id}'")
        return

    # Check result
    if result.status == "failure":
        log.error(f"{log_id} Branch '{branch_id}' failed: {result.error_message}")
        # Fail entire workflow
        raise WorkflowNodeFailureError(
            f"fork.{fork_node_id}.{branch_id}",
            result.error_message
        )

    # Store branch result
    branch_info["result"] = {
        "artifact_name": result.artifact_name,
        "artifact_version": result.artifact_version
    }

    # Check if all branches complete
    all_complete = all(
        "result" in b for b in branches
    )

    if all_complete:
        log.info(f"{log_id} All branches completed")
        await self._finalize_fork_node(
            fork_node_id,
            branches,
            workflow_state,
            workflow_context
        )
```

#### 4.3.3. Result Merging

When all branches complete, merge results:

```python
async def _finalize_fork_node(
    self,
    fork_node_id: str,
    branches: List[Dict],
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """Merge fork branch results."""
    log_id = f"{self.host.log_identifier}[Fork:{fork_node_id}]"

    # Load all branch artifacts
    merged_output = {}

    for branch in branches:
        output_key = branch["output_key"]
        artifact_name = branch["result"]["artifact_name"]
        artifact_version = branch["result"]["artifact_version"]

        # Load artifact
        artifact_data = await self._load_artifact(
            artifact_name,
            artifact_version,
            workflow_context
        )

        # Add to merged output
        merged_output[output_key] = artifact_data

    # Create merged artifact
    merged_artifact_name = f"fork_{fork_node_id}_merged.json"
    await self.host.artifact_service.save_artifact(
        app_name=self.host.workflow_name,
        user_id=workflow_context.a2a_context["user_id"],
        session_id=workflow_context.a2a_context["session_id"],
        filename=merged_artifact_name,
        data=merged_output
    )

    # Mark fork complete
    workflow_state.completed_nodes[fork_node_id] = merged_artifact_name
    workflow_state.pending_nodes.remove(fork_node_id)
    workflow_state.node_outputs[fork_node_id] = {"output": merged_output}

    # Clear branch tracking
    del workflow_state.active_branches[fork_node_id]

    # Continue workflow
    await self.execute_workflow(workflow_state, workflow_context)
```

#### 4.3.4. Failure Handling in Parallel Branches

Any branch failure causes entire workflow to fail:

```python
# In handle_fork_branch_completion
if result.status == "failure":
    log.error(f"{log_id} Branch '{branch_id}' failed")

    # Cancel other branches (send cancel requests)
    cancellation_tasks = []
    for other_branch in branches:
        if other_branch["branch_id"] != branch_id and "result" not in other_branch:
            cancellation_tasks.append(
                self._cancel_branch(other_branch, workflow_context)
            )
    
    # Wait for cancellations with a timeout
    cancellation_timeout = self.host.get_config("node_cancellation_timeout_seconds", 30)
    await asyncio.wait(cancellation_tasks, timeout=cancellation_timeout)

    # Fail workflow
    raise WorkflowNodeFailureError(
        f"fork.{fork_node_id}.{branch_id}",
        result.error_message
    )
```

### 4.4. Loops

#### 4.4.1. Iteration Logic

Loop nodes repeat a sub-workflow multiple times:

```python
class LoopNode(WorkflowNode):
    """Loop/iteration node."""
    type: Literal["loop"] = "loop"
    loop_over: str  # Template reference to array
    loop_node: str  # Node ID to execute for each item
    max_iterations: int = 100  # Safety limit

# In DAGExecutor
async def _execute_loop_node(
    self,
    node: LoopNode,
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """Execute loop node."""
    log_id = f"{self.host.log_identifier}[Loop:{node.id}]"

    # Resolve loop array
    items = self._resolve_template(node.loop_over, workflow_state)

    if not isinstance(items, list):
        raise ValueError(f"Loop target must be array, got: {type(items)}")

    # Check iteration limit
    if len(items) > node.max_iterations:
        raise ValueError(
            f"Loop has {len(items)} items but max is {node.max_iterations}"
        )

    log.info(f"{log_id} Starting loop with {len(items)} iterations")

    # Execute loop iterations sequentially
    loop_results = []

    for i, item in enumerate(items):
        log.info(f"{log_id} Iteration {i+1}/{len(items)}")

        # Create a lightweight, temporary state for the iteration. This avoids
        # deep-copying the entire workflow state for each loop.
        iteration_state = workflow_state.model_copy(deep=False) # Shallow copy
        iteration_state.node_outputs = {
            **workflow_state.node_outputs,
            "_loop_item": {"output": item},
            "_loop_index": {"output": i},
        }

        # Execute loop body node
        loop_body_node = self.nodes[node.loop_node]
        await self._execute_agent_node(
            loop_body_node,
            iteration_state,
            workflow_context
        )

        # Wait for completion and collect result
        result = await self._wait_for_node_completion(
            node.loop_node,
            workflow_context
        )

        loop_results.append(result)

    # Store loop results
    merged_artifact_name = f"loop_{node.id}_results.json"
    await self.host.artifact_service.save_artifact(
        app_name=self.host.workflow_name,
        user_id=workflow_context.a2a_context["user_id"],
        session_id=workflow_context.a2a_context["session_id"],
        filename=merged_artifact_name,
        data={"results": loop_results}
    )

    # Mark loop complete
    workflow_state.completed_nodes[node.id] = merged_artifact_name
    workflow_state.node_outputs[node.id] = {"output": {"results": loop_results}}
```

#### 4.4.2. Max Iteration Limits

Loops enforce maximum iteration counts to prevent infinite loops:

```python
# Default max_iterations from config
max_iterations = node.max_iterations or \
    self.host.get_config("default_max_loop_iterations", 100)

if len(items) > max_iterations:
    raise WorkflowExecutionError(
        f"Loop '{node.id}' exceeds max iterations: "
        f"{len(items)} > {max_iterations}"
    )
```

#### 4.4.3. Loop Variable Management

Loop iterations have access to special variables:

```python
# Available in loop body node input mappings:
{
    "_loop_item": <current item>,
    "_loop_index": <current index (0-based)>
}

# Example loop body input:
{
    "document": "{{_loop_item.output}}",
    "position": "{{_loop_index.output}}"
}
```

---

## 5. Data Models and Schemas

### 5.1. Agent Schema Extensions

#### 5.1.1. AgentCard Schema Fields

The A2A AgentCard type is extended to include schemas:

```python
# In a2a types (or SAM extension)
class AgentCard(BaseModel):
    # ... existing fields ...

    # NEW: Schema fields
    input_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for agent input validation"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for agent output validation"
    )
```

#### 5.1.2. SamAgentAppConfig Extensions

Agent configuration supports schema definition:

```python
class SamAgentAppConfig(SamConfigBase):
    # ... existing fields ...

    # NEW: Schema fields
    input_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for validating agent input"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for validating agent output"
    )

    # NEW: Validation configuration
    validation_max_retries: int = Field(
        default=2,
        description="Max retries for output validation failures"
    )
```

#### 5.1.3. Schema Auto-Population in Agent Cards

Schemas are automatically added to agent cards:

```python
# In SamAgentApp or publish_agent_card()
agent_card = AgentCard(
    name=self.agent_name,
    description=self.agent_card_config.description,
    # ... other fields ...

    # Auto-populate schemas from config
    input_schema=self.get_config("input_schema"),
    output_schema=self.get_config("output_schema")
)
```

### 5.2. Workflow Configuration Models

#### 5.2.1. WorkflowAppConfig

```python
class WorkflowAppConfig(SamAgentAppConfig):
    """Workflow app configuration extends agent config."""

    # Override type indicator
    agent_type: Literal["workflow"] = "workflow"

    # Workflow definition
    workflow: WorkflowDefinition = Field(
        ...,
        description="The workflow DAG definition"
    )

    # Workflow execution settings
    max_workflow_execution_time_seconds: int = Field(
        default=1800,  # 30 minutes
        description="Maximum time for entire workflow execution"
    )
    default_node_timeout_seconds: int = Field(
        default=300,  # 5 minutes
        description="Default timeout for individual nodes"
    )
    node_cancellation_timeout_seconds: int = Field(
        default=30,
        description="Time to wait for a node to confirm cancellation before force-failing."
    )
    default_max_loop_iterations: int = Field(
        default=100,
        description="Default max iterations for loop nodes"
    )

    # Override optional fields
    model: Optional[Union[str, Dict[str, Any]]] = None
    instruction: Optional[Any] = None
```

#### 5.2.2. WorkflowDefinition

```python
class WorkflowDefinition(BaseModel):
    """Complete workflow definition."""

    description: str = Field(
        ...,
        description="Human-readable workflow description"
    )

    input_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for workflow input"
    )

    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for workflow output"
    )

    nodes: List[WorkflowNode] = Field(
        ...,
        description="Workflow nodes (DAG vertices)"
    )

    output_mapping: Dict[str, Any] = Field(
        ...,
        description="Mapping from node outputs to final workflow output"
    )

    skills: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Workflow skills for agent card"
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
```

#### 5.2.3. WorkflowNode Types

```python
class WorkflowNode(BaseModel):
    """Base workflow node."""
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type")
    depends_on: Optional[List[str]] = Field(
        None,
        description="List of node IDs this node depends on"
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
```

#### 5.2.4. FlowControlNode Definitions

```python
class ForkBranch(BaseModel):
    """A single branch in a fork node."""
    id: str = Field(..., description="Branch identifier")
    agent_persona: str = Field(..., description="Agent for this branch")
    input: Dict[str, Any] = Field(..., description="Input mapping")
    output_key: str = Field(..., description="Key for merging result")
```

#### 5.2.5. Input/Output Mapping Specifications

```python
# Input mapping format
{
    "field_name": "{{node_id.output.field_path}}",  # Template reference
    "other_field": "literal value",  # Literal value
    "nested": {
        "data": "{{other_node.output.data}}"
    }
}

# Output mapping format
{
    "account_id": "{{create_account.output.account_id}}",
    "status": "{{validate.output.status}}",
    "metadata": {
        "workflow": "CustomerOnboarding",
        "timestamp": "{{workflow.start_time}}"
    }
}
```

### 5.3. A2A DataPart Extensions

#### 5.3.1. WorkflowNodeRequestData

```python
class WorkflowNodeRequestData(BaseModel):
    """Data part sent by workflow to agent for node execution."""
    type: Literal["workflow_node_request"] = "workflow_node_request"

    # Workflow context
    workflow_name: str = Field(..., description="Name of the workflow")
    node_id: str = Field(..., description="ID of the workflow node")

    # Optional schema overrides
    input_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for input validation"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for expected output"
    )
```

#### 5.3.2. WorkflowNodeResultData

```python
class WorkflowNodeResultData(BaseModel):
    """Data part returned by agent to workflow with execution result."""
    type: Literal["workflow_node_result"] = "workflow_node_result"

    # Result status
    status: Literal["success", "failure"] = Field(
        ...,
        description="Execution result status"
    )

    # Success fields
    artifact_name: Optional[str] = Field(
        None,
        description="Name of result artifact if success"
    )
    artifact_version: Optional[int] = Field(
        None,
        description="Version of result artifact"
    )

    # Failure fields
    error_message: Optional[str] = Field(
        None,
        description="Error message if failure"
    )
    validation_errors: Optional[List[str]] = Field(
        None,
        description="Schema validation errors if any"
    )

    # Metadata
    retry_count: int = Field(
        0,
        description="Number of retries attempted"
    )
```

#### 5.3.3. Usage in Message Construction

```python
# Workflow to agent (request)
message = A2AMessage(
    parts=[
        # First part: workflow context
        DataPart(
            data=WorkflowNodeRequestData(
                workflow_name="CustomerOnboarding",
                node_id="extract_info",
                output_schema={...}
            ).model_dump()
        ),
        # Second part: user query
        TextPart(text="Extract customer info from this document..."),
        # Additional parts as needed
    ],
    contextId=execution_id
)

# Agent to workflow (response)
result_message = A2AMessage(
    parts=[
        DataPart(
            data=WorkflowNodeResultData(
                status="success",
                artifact_name="customer_data.json",
                artifact_version=1,
                retry_count=0
            ).model_dump()
        )
    ],
    contextId=execution_id
)
```

### 5.4. Workflow Execution State

#### 5.4.1. WorkflowExecutionState Model

```python
class WorkflowExecutionState(BaseModel):
    """State stored in ADK session for workflow execution."""

    # Identification
    workflow_name: str
    execution_id: str
    start_time: datetime

    # Current execution status
    current_node_id: Optional[str] = None
    completed_nodes: Dict[str, str] = {}  # node_id → artifact_name
    pending_nodes: List[str] = []

    # Fork/join tracking
    active_branches: Dict[str, List[Dict]] = {}  # fork_id → branch info

    # Error tracking
    error_state: Optional[Dict[str, Any]] = None

    # Cached node outputs for value resolution
    node_outputs: Dict[str, Dict[str, Any]] = {}  # node_id → {"output": data}

    # Metadata
    metadata: Dict[str, Any] = {}

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

#### 5.4.2. State Serialization

State is serialized to JSON for session storage:

```python
# Serialize
state_dict = workflow_state.model_dump()
session.state["workflow_execution"] = state_dict

# Deserialize
state_dict = session.state.get("workflow_execution")
workflow_state = WorkflowExecutionState.model_validate(state_dict)
```

#### 5.4.3. Session Storage Integration

State is stored in the ADK session service:

```python
# Create session for workflow
session = await self.session_service.create_session(
    app_name=self.workflow_name,
    user_id=user_id,
    session_id=session_id
)

# Store state
session.state["workflow_execution"] = workflow_state.model_dump()
await self.session_service.update_session(session)

# Retrieve state
session = await self.session_service.get_session(
    app_name=self.workflow_name,
    user_id=user_id,
    session_id=session_id
)
workflow_state = WorkflowExecutionState.model_validate(
    session.state.get("workflow_execution", {})
)
```

#### 5.4.4. TTL and Cleanup

TTL is configured at the session service level:

```yaml
session_service:
  type: sql
  database_url: "postgresql://..."
  session_ttl_seconds: 3600  # 1 hour after completion
```

Workflow marks completion in metadata:

```python
# On workflow completion
workflow_state.metadata["completion_time"] = datetime.now(timezone.utc).isoformat()
workflow_state.metadata["status"] = "completed"
session.state["workflow_execution"] = workflow_state.model_dump()
await self.session_service.update_session(session)

# Session service handles TTL-based cleanup
```

---

**End of Part 3**

**Note:** This completes the three-part architecture design document. The remaining sections (6-16 and Appendices) would continue in additional parts if needed. The current three parts cover the core architecture, components, data models, and implementation details for the Prescriptive Workflows feature.

For the complete document structure including sections 6-16 (Schema Validation, Value References, Execution Algorithms, Integration, Error Handling, Security, Observability, Module Organization, Configuration, Key Decisions, and Extension Points), please refer to the Table of Contents provided earlier.
