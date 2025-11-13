# Prescriptive Workflows - Architecture Design Document (Part 2 of 3)

**Document Version:** 1.0
**Last Updated:** 2025-11-13
**Status:** Draft

**Note:** This is Part 2 of a three-part document. See Part 1 for Sections 1-3.1.

---

### 3.2. WorkflowApp

#### 3.2.1. App Responsibilities

WorkflowApp extends the Solace AI Connector's App class to provide workflow-specific initialization and configuration. Its responsibilities include:

**Configuration Validation**
- Parse and validate workflow YAML configuration using Pydantic models
- Ensure workflow DAG structure is valid (no cycles, valid dependencies)
- Validate that referenced persona agents exist in configuration
- Apply default values for optional settings

**Subscription Management**
- Generate Solace topic subscriptions for workflow operation
- Subscribe to discovery topic for persona agent cards
- Subscribe to workflow's own agent request topic
- Subscribe to persona response and status topics

**Component Instantiation**
- Create and configure WorkflowExecutorComponent instance
- Pass validated configuration to component
- Register component with SAC framework

**Agent Card Auto-Population**
- Extract input and output schemas from workflow definition
- Populate agent card with workflow metadata
- Merge user-provided agent card settings with workflow-derived fields

#### 3.2.2. Configuration Validation

WorkflowApp validates configuration using Pydantic models:

```python
class WorkflowApp(App):
    """Custom App class for workflow orchestration."""

    def __init__(self, app_info: Dict[str, Any], **kwargs):
        log.debug("Initializing WorkflowApp...")

        app_config_dict = app_info.get("app_config", {})

        try:
            # Validate configuration
            app_config = WorkflowAppConfig.model_validate_and_clean(
                app_config_dict
            )
        except ValidationError as e:
            log.error(f"Workflow configuration validation failed: {e}")
            raise

        # Extract workflow-specific settings
        namespace = app_config.namespace
        workflow_name = app_config.workflow_name
        workflow_def = app_config.workflow

        # Auto-populate agent card schemas
        if not app_config.agent_card.input_schema and workflow_def.input_schema:
            app_config.agent_card.input_schema = workflow_def.input_schema

        if not app_config.agent_card.output_schema and workflow_def.output_schema:
            app_config.agent_card.output_schema = workflow_def.output_schema

        # Generate subscriptions
        subscriptions = self._generate_subscriptions(namespace, workflow_name)

        # Build component configuration
        component_info = {
            "component_name": workflow_name,
            "component_module": "solace_agent_mesh.agent.workflow.component",
            "component_config": {
                "app_config": app_config.model_dump()
            }
        }

        # Update app_info with validated config
        app_info["app_config"] = app_config.model_dump()
        app_info["subscriptions"] = subscriptions
        app_info["component_list"] = [component_info]

        # Call parent App constructor
        super().__init__(app_info, **kwargs)

    def _generate_subscriptions(
        self,
        namespace: str,
        workflow_name: str
    ) -> List[str]:
        """Generate Solace topic subscriptions for workflow."""
        subscriptions = []

        # Discovery topic for persona agent cards
        subscriptions.append(a2a.get_discovery_topic(namespace))

        # Workflow's agent request topic
        subscriptions.append(
            a2a.get_agent_request_topic(namespace, workflow_name)
        )

        # Persona response topics (wildcard)
        subscriptions.append(
            a2a.get_agent_response_subscription_topic(namespace, workflow_name)
        )

        # Persona status topics (wildcard)
        subscriptions.append(
            a2a.get_agent_status_subscription_topic(namespace, workflow_name)
        )

        return subscriptions
```

**Validation Checks:**

The Pydantic model performs several validation checks:

1. **Required Fields** - Ensures workflow_name, namespace, workflow definition exist
2. **Schema Validity** - Validates JSON schemas are well-formed
3. **Node References** - Ensures node IDs are unique and dependencies reference valid nodes
4. **Flow Control** - Validates conditional expressions and fork/join structure
5. **Service Configuration** - Ensures session and artifact services are properly configured

#### 3.2.3. Subscription Management

WorkflowApp generates four types of subscriptions:

**Discovery Subscription**
```
{namespace}/a2a/v1/discovery/agentcards
```
Receives agent card announcements from persona agents. The workflow maintains an agent registry to track available personas and their capabilities.

**Request Subscription**
```
{namespace}/a2a/v1/agent/request/{workflow_name}
```
Receives workflow invocation requests from gateways and other clients. Each workflow has a unique agent name and corresponding request topic.

**Response Subscriptions**
```
{namespace}/a2a/v1/agent/response/{workflow_name}/>
```
Receives final responses from persona agents. The workflow name in the topic identifies which workflow delegated the task. The trailing wildcard matches individual sub-task IDs.

**Status Subscriptions**
```
{namespace}/a2a/v1/agent/status/{workflow_name}/>
```
Receives status updates from persona agents during task execution. Used for progress tracking and timeout detection.

#### 3.2.4. Component Instantiation

WorkflowApp creates a single WorkflowExecutorComponent instance:

```python
# Component configuration passed to SAC framework
component_info = {
    "component_name": workflow_name,
    "component_module": "solace_agent_mesh.agent.workflow.component",
    "component_config": {
        "app_config": app_config.model_dump()  # Entire validated config
    }
}

# SAC framework will instantiate:
# from solace_agent_mesh.agent.workflow.component import WorkflowExecutorComponent
# component = WorkflowExecutorComponent(**component_config)
```

The component configuration includes:
- Entire validated WorkflowAppConfig as nested dictionary
- Workflow definition with DAG structure
- Service configurations (session, artifact)
- Agent card settings
- Execution parameters (timeouts, max retries)

### 3.3. WorkflowNodeHandler (Agent Workflow Support)

#### 3.3.1. Integration with SamAgentComponent

WorkflowNodeHandler extends SamAgentComponent to enable agents to participate in workflows. The handler is implemented as a separate module to keep SamAgentComponent maintainable:

```
agent/
├── sac/
│   ├── component.py              # SamAgentComponent (existing)
│   └── workflow_support/         # NEW
│       ├── __init__.py
│       ├── handler.py            # WorkflowNodeHandler
│       └── validator.py          # Schema validation utilities
```

**Integration Points:**

1. **Import in SamAgentComponent**
```python
# In agent/sac/component.py
from .workflow_support.handler import WorkflowNodeHandler

class SamAgentComponent(SamComponentBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        # ... existing initialization ...

        # Initialize workflow support
        self.workflow_handler = WorkflowNodeHandler(self)
```

2. **Task Request Interception**
```python
# In agent/protocol/event_handlers.py
async def handle_task_request(host_component, a2a_request, original_message):
    message = a2a.get_message_from_send_request(a2a_request)

    # Check for workflow mode
    workflow_data = host_component.workflow_handler.extract_workflow_context(
        message
    )

    if workflow_data:
        # Execute as workflow node
        return await host_component.workflow_handler.execute_workflow_node(
            message,
            workflow_data,
            a2a_request,
            original_message
        )
    else:
        # Execute as normal agent task
        return await execute_normal_agent_task(...)
```

3. **Configuration Access**
```python
# WorkflowNodeHandler accesses agent configuration
class WorkflowNodeHandler:
    def __init__(self, host_component: SamAgentComponent):
        self.host = host_component
        self.input_schema = host_component.get_config("input_schema")
        self.output_schema = host_component.get_config("output_schema")
        self.max_validation_retries = host_component.get_config(
            "validation_max_retries",
            2
        )
```

#### 3.3.2. Workflow Mode Detection

WorkflowNodeHandler detects workflow mode by examining message DataParts:

```python
def extract_workflow_context(
    self,
    message: A2AMessage
) -> Optional[WorkflowNodeRequestData]:
    """
    Extract workflow context from message if present.
    Workflow messages contain WorkflowNodeRequestData as first DataPart.
    """
    if not message.parts:
        return None

    # Check first part for workflow data
    first_part = message.parts[0]

    if not hasattr(first_part, 'data') or not first_part.data:
        return None

    # Check for workflow_node_request type
    if first_part.data.get("type") != "workflow_node_request":
        return None

    # Parse workflow request data
    try:
        workflow_data = WorkflowNodeRequestData.model_validate(
            first_part.data
        )
        return workflow_data
    except ValidationError as e:
        log.error(
            f"{self.host.log_identifier} Invalid workflow request data: {e}"
        )
        return None
```

**WorkflowNodeRequestData Structure:**

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
        description="JSON Schema for input (overrides agent card)"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="JSON Schema for output (overrides agent card)"
    )
```

#### 3.3.3. Input Validation

When workflow mode is detected, WorkflowNodeHandler validates input:

```python
async def execute_workflow_node(
    self,
    message: A2AMessage,
    workflow_data: WorkflowNodeRequestData,
    a2a_request: A2ARequest,
    original_message: SolaceMessage
):
    """Execute agent as a workflow node with validation."""
    log_id = f"{self.host.log_identifier}[WorkflowNode:{workflow_data.node_id}]"

    # Determine effective schemas
    input_schema = workflow_data.input_schema or self.input_schema
    output_schema = workflow_data.output_schema or self.output_schema

    # Validate input if schema exists
    if input_schema:
        validation_errors = self._validate_input(message, input_schema)

        if validation_errors:
            log.error(
                f"{log_id} Input validation failed: {validation_errors}"
            )

            # Return validation error immediately
            return await self._return_validation_error(
                workflow_data,
                validation_errors,
                a2a_request,
                original_message
            )

    # Input valid, proceed with execution
    return await self._execute_with_output_validation(
        message,
        workflow_data,
        output_schema,
        a2a_request,
        original_message
    )
```

**Input Validation Logic:**

```python
def _validate_input(
    self,
    message: A2AMessage,
    input_schema: Dict[str, Any]
) -> Optional[List[str]]:
    """
    Validate message content against input schema.
    Returns list of validation errors or None if valid.
    """
    from .validator import validate_against_schema

    # Extract input data from message
    input_data = self._extract_input_data(message)

    # Validate against schema
    errors = validate_against_schema(input_data, input_schema)

    return errors if errors else None

def _extract_input_data(self, message: A2AMessage) -> Dict[str, Any]:
    """
    Extract structured input data from message parts.
    Combines text and data parts into a single dictionary.
    """
    input_data = {}

    for part in message.parts:
        if hasattr(part, 'text') and part.text:
            # Text content goes in 'query' field
            input_data.setdefault('query', '')
            input_data['query'] += part.text

        elif hasattr(part, 'data') and part.data:
            # Skip workflow request data
            if part.data.get('type') == 'workflow_node_request':
                continue

            # Merge other data parts
            input_data.update(part.data)

    return input_data
```

#### 3.3.4. Instruction Injection

For workflow nodes, WorkflowNodeHandler injects special instructions into the system prompt:

```python
def _inject_workflow_instructions(
    self,
    llm_request: LlmRequest,
    workflow_data: WorkflowNodeRequestData,
    output_schema: Optional[Dict[str, Any]]
) -> None:
    """Inject workflow-specific instructions into system prompt."""

    workflow_instructions = f"""

WORKFLOW EXECUTION CONTEXT:
You are executing as node '{workflow_data.node_id}' in workflow '{workflow_data.workflow_name}'.
"""

    # Add output schema requirement if present
    if output_schema:
        workflow_instructions += f"""

REQUIRED OUTPUT FORMAT:
1. Create an artifact containing your result data conforming to this JSON Schema:

{json.dumps(output_schema, indent=2)}

2. End your response with the result embed marking your output artifact:
   «result:artifact=<artifact_name>:v<version> status=success»

   Example: «result:artifact=customer_data.json:v1 status=success»

3. The artifact MUST strictly conform to the provided schema. Your output will be validated.
   If validation fails, you will be asked to retry with error feedback.

IMPORTANT:
- Use tools like save_artifact to create the output artifact
- Or ensure tool responses are saved as artifacts (automatic if size exceeds threshold)
- The artifact format (JSON, YAML, etc.) must be parseable
- Additional fields beyond the schema are allowed, but required fields must be present
"""
    else:
        # No output schema, just mark result
        workflow_instructions += """

REQUIRED OUTPUT FORMAT:
End your response with the result embed to mark your completion:
«result:artifact=<artifact_name>:v<version> status=success»

If you cannot complete the task, use:
«result:artifact=<artifact_name>:v<version> status=failure message="<reason>"»
"""

    # Append to existing system instruction
    if llm_request.config.system_instruction:
        llm_request.config.system_instruction += workflow_instructions
    else:
        llm_request.config.system_instruction = workflow_instructions.strip()
```

**Injection Point:**

Instructions are injected via an ADK before_model_callback:

```python
# In WorkflowNodeHandler
def _create_workflow_callback(
    self,
    workflow_data: WorkflowNodeRequestData,
    output_schema: Optional[Dict[str, Any]]
) -> Callable:
    """Create callback for workflow instruction injection."""

    def inject_instructions(
        callback_context: CallbackContext,
        llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        self._inject_workflow_instructions(
            llm_request,
            workflow_data,
            output_schema
        )
        return None

    return inject_instructions

# During agent execution
async def _execute_with_output_validation(self, ...):
    # Create callback
    workflow_callback = self._create_workflow_callback(
        workflow_data,
        output_schema
    )

    # Add to agent's callback list
    self.host.adk_agent.register_callback(
        "before_model",
        workflow_callback
    )

    # Execute agent (existing ADK execution path)
    result = await run_adk_async_task_thread_wrapper(...)

    # Cleanup callback
    self.host.adk_agent.unregister_callback(workflow_callback)
```

#### 3.3.5. Output Validation and Retry Logic

After agent execution completes, WorkflowNodeHandler validates the output:

```python
async def _finalize_workflow_node_execution(
    self,
    session,
    last_event: ADKEvent,
    workflow_data: WorkflowNodeRequestData,
    output_schema: Optional[Dict[str, Any]],
    retry_count: int = 0
) -> WorkflowNodeResultData:
    """
    Finalize workflow node execution with output validation.
    Handles retry on validation failure.
    """
    log_id = f"{self.host.log_identifier}[Node:{workflow_data.node_id}]"

    # 1. Parse result embed from agent output
    result_embed = self._parse_result_embed(last_event)

    if not result_embed:
        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message="Agent did not output result embed",
            retry_count=retry_count
        )

    # Handle explicit failure status
    if result_embed.status == "failure":
        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message=result_embed.message or "Agent reported failure",
            artifact_name=result_embed.artifact_name,
            retry_count=retry_count
        )

    # 2. Load artifact from artifact service
    try:
        artifact = await self.host.artifact_service.load_artifact(
            app_name=self.host.agent_name,
            user_id=session.user_id,
            session_id=session.id,
            filename=result_embed.artifact_name,
            version=result_embed.version or 0
        )
    except Exception as e:
        log.error(f"{log_id} Failed to load artifact: {e}")
        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message=f"Failed to load result artifact: {e}",
            retry_count=retry_count
        )

    # 3. Validate artifact against output schema
    if output_schema:
        validation_errors = self._validate_artifact(
            artifact,
            output_schema
        )

        if validation_errors:
            log.warning(
                f"{log_id} Output validation failed: {validation_errors}"
            )

            # Check if we can retry
            if retry_count < self.max_validation_retries:
                log.info(f"{log_id} Retrying with validation feedback")
                return await self._retry_with_validation_error(
                    session,
                    workflow_data,
                    output_schema,
                    validation_errors,
                    retry_count + 1
                )
            else:
                # Max retries exceeded
                return WorkflowNodeResultData(
                    type="workflow_node_result",
                    status="failure",
                    error_message="Output validation failed after max retries",
                    validation_errors=validation_errors,
                    retry_count=retry_count
                )

    # 4. Validation succeeded
    return WorkflowNodeResultData(
        type="workflow_node_result",
        status="success",
        artifact_name=result_embed.artifact_name,
        artifact_version=result_embed.version or 0,
        retry_count=retry_count
    )
```

**Result Embed Parsing:**

```python
def _parse_result_embed(
    self,
    adk_event: ADKEvent
) -> Optional[ResultEmbed]:
    """
    Parse result embed from agent's final output.
    Format: «result:artifact=<name>:v<version> status=<success|failure> message="<text>"»
    """
    from ...common.utils.embeds.parser import parse_embeds

    if not adk_event.content or not adk_event.content.parts:
        return None

    # Extract text from last event
    text_content = ""
    for part in adk_event.content.parts:
        if part.text:
            text_content += part.text

    # Parse embeds
    embeds = parse_embeds(text_content, types=["result"])

    if not embeds:
        return None

    # Take last result embed
    result_embed = embeds[-1]

    # Parse embed parameters
    return ResultEmbed(
        artifact_name=result_embed.get("artifact"),
        version=result_embed.get("version"),
        status=result_embed.get("status", "success"),
        message=result_embed.get("message")
    )
```

**Retry Implementation:**

```python
async def _retry_with_validation_error(
    self,
    session,
    workflow_data: WorkflowNodeRequestData,
    output_schema: Dict[str, Any],
    validation_errors: List[str],
    retry_count: int
) -> WorkflowNodeResultData:
    """
    Retry agent execution with validation error feedback.
    Appends validation errors to session history.
    """
    log_id = f"{self.host.log_identifier}[Node:{workflow_data.node_id}]"
    log.info(f"{log_id} Retry {retry_count}/{self.max_validation_retries}")

    # Create feedback message
    error_text = "\n".join([f"- {err}" for err in validation_errors])
    feedback_content = adk_types.Content(
        role="user",
        parts=[adk_types.Part.from_text(f"""
Your previous output artifact failed schema validation with the following errors:

{error_text}

Please review the required schema and create a corrected artifact that addresses these errors:

{json.dumps(output_schema, indent=2)}

Remember to end your response with the result embed:
«result:artifact=<corrected_artifact_name>:v<version> status=success»
""")]
    )

    # Append feedback to session
    feedback_event = ADKEvent(
        invocation_id=session.events[-1].invocation_id if session.events else None,
        author="system",
        content=feedback_content
    )
    await self.host.session_service.append_event(session, feedback_event)

    # Re-run agent with updated session
    run_config = RunConfig(
        streaming_mode=StreamingMode.SSE,
        max_llm_calls=self.host.get_config("max_llm_calls_per_task", 20)
    )

    # Execute agent again
    try:
        await run_adk_async_task_thread_wrapper(
            self.host,
            session,
            None,  # No new user message
            run_config,
            {}  # Empty task context for retry
        )

        # Get updated session
        session = await self.host.session_service.get_session(
            app_name=self.host.agent_name,
            user_id=session.user_id,
            session_id=session.id
        )

        # Validate again
        return await self._finalize_workflow_node_execution(
            session,
            session.events[-1],
            workflow_data,
            output_schema,
            retry_count
        )

    except Exception as e:
        log.error(f"{log_id} Retry execution failed: {e}")
        return WorkflowNodeResultData(
            type="workflow_node_result",
            status="failure",
            error_message=f"Retry execution failed: {e}",
            retry_count=retry_count
        )
```

#### 3.3.6. Response Format Changes

WorkflowNodeHandler returns a structured response to the workflow:

```python
async def _return_workflow_result(
    self,
    workflow_data: WorkflowNodeRequestData,
    result_data: WorkflowNodeResultData,
    a2a_request: A2ARequest,
    original_message: SolaceMessage,
    a2a_context: Dict
):
    """Return workflow node result to workflow executor."""

    # Create message with result data part
    result_message = a2a.create_agent_parts_message(
        parts=[a2a.create_data_part(data=result_data.model_dump())],
        task_id=a2a_context["logical_task_id"],
        context_id=a2a_context["session_id"]
    )

    # Create task status
    task_state = TaskState.completed if result_data.status == "success" else TaskState.failed
    task_status = a2a.create_task_status(
        state=task_state,
        message=result_message
    )

    # Create final task
    final_task = a2a.create_final_task(
        task_id=a2a_context["logical_task_id"],
        context_id=a2a_context["session_id"],
        final_status=task_status,
        metadata={
            "agent_name": self.host.agent_name,
            "workflow_node_id": workflow_data.node_id,
            "workflow_name": workflow_data.workflow_name
        }
    )

    # Create JSON-RPC response
    response = a2a.create_success_response(
        result=final_task,
        request_id=a2a.get_request_id(a2a_request)
    )

    # Publish to workflow's response topic
    response_topic = a2a_context.get("replyToTopic")
    self.host.publish_a2a_message(
        payload=response.model_dump(exclude_none=True),
        topic=response_topic,
        user_properties={"a2aUserConfig": a2a_context.get("a2a_user_config")}
    )

    # ACK original message
    original_message.call_acknowledgements()
```

### 3.4. DAG Executor

#### 3.4.1. DAG Traversal Algorithm

The DAGExecutor manages the execution order of workflow nodes based on their dependencies:

```python
class DAGExecutor:
    """Executes workflow DAG by coordinating node execution."""

    def __init__(
        self,
        workflow_definition: WorkflowDefinition,
        host_component: WorkflowExecutorComponent
    ):
        self.workflow_def = workflow_definition
        self.host = host_component

        # Build dependency graph
        self.nodes: Dict[str, WorkflowNode] = {
            node.id: node for node in workflow_definition.nodes
        }
        self.dependencies = self._build_dependency_graph()
        self.reverse_dependencies = self._build_reverse_dependencies()

    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build mapping of node_id -> list of node IDs it depends on."""
        dependencies = {}

        for node in self.workflow_def.nodes:
            deps = node.depends_on or []
            dependencies[node.id] = deps

        return dependencies

    def _build_reverse_dependencies(self) -> Dict[str, List[str]]:
        """Build mapping of node_id -> list of nodes that depend on it."""
        reverse_deps = {node_id: [] for node_id in self.nodes}

        for node_id, deps in self.dependencies.items():
            for dep in deps:
                reverse_deps[dep].append(node_id)

        return reverse_deps

    def get_initial_nodes(self) -> List[str]:
        """Get nodes with no dependencies (entry points)."""
        return [
            node_id
            for node_id, deps in self.dependencies.items()
            if not deps
        ]

    def get_next_nodes(
        self,
        workflow_state: WorkflowExecutionState
    ) -> List[str]:
        """
        Determine which nodes can execute next.
        Returns nodes whose dependencies are all complete.
        """
        completed = set(workflow_state.completed_nodes.keys())
        next_nodes = []

        for node_id, deps in self.dependencies.items():
            # Skip if already completed
            if node_id in completed:
                continue

            # Skip if already pending
            if node_id in workflow_state.pending_nodes:
                continue

            # Check if all dependencies are satisfied
            if all(dep in completed for dep in deps):
                next_nodes.append(node_id)

        return next_nodes
```

**Execution Loop:**

```python
async def execute_workflow(
    self,
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """
    Execute workflow DAG until completion or failure.
    Main execution loop.
    """
    log_id = f"{self.host.log_identifier}[Workflow:{workflow_state.execution_id}]"

    while True:
        # Get next nodes to execute
        next_nodes = self.get_next_nodes(workflow_state)

        if not next_nodes:
            # Check if workflow is complete
            if len(workflow_state.completed_nodes) == len(self.nodes):
                log.info(f"{log_id} Workflow completed successfully")
                return

            # Check if workflow is stuck
            if not workflow_state.pending_nodes and not workflow_state.active_branches:
                log.error(f"{log_id} Workflow stuck - no nodes can execute")
                raise WorkflowExecutionError("Workflow deadlock detected")

            # Wait for pending nodes to complete
            log.debug(f"{log_id} Waiting for {len(workflow_state.pending_nodes)} pending nodes")
            return  # Execution will resume on node completion

        # Execute next nodes
        for node_id in next_nodes:
            await self.execute_node(node_id, workflow_state, workflow_context)

            # Update pending nodes
            workflow_state.pending_nodes.append(node_id)

        # Persist state
        await self.host._update_workflow_state(workflow_context, workflow_state)
```

#### 3.4.2. Node Dependency Resolution

The DAGExecutor validates dependencies during initialization:

```python
def validate_dag(self) -> List[str]:
    """
    Validate DAG structure.
    Returns list of validation errors or empty list if valid.
    """
    errors = []

    # Check for cycles
    if self._has_cycles():
        errors.append("Workflow DAG contains cycles")

    # Check for invalid dependencies
    for node_id, deps in self.dependencies.items():
        for dep in deps:
            if dep not in self.nodes:
                errors.append(
                    f"Node '{node_id}' depends on non-existent node '{dep}'"
                )

    # Check for unreachable nodes
    reachable = self._get_reachable_nodes()
    for node_id in self.nodes:
        if node_id not in reachable:
            errors.append(f"Node '{node_id}' is unreachable")

    return errors

def _has_cycles(self) -> bool:
    """Detect cycles using depth-first search."""
    visited = set()
    rec_stack = set()

    def dfs(node_id: str) -> bool:
        visited.add(node_id)
        rec_stack.add(node_id)

        for dependent in self.reverse_dependencies.get(node_id, []):
            if dependent not in visited:
                if dfs(dependent):
                    return True
            elif dependent in rec_stack:
                return True

        rec_stack.remove(node_id)
        return False

    for node_id in self.nodes:
        if node_id not in visited:
            if dfs(node_id):
                return True

    return False
```

#### 3.4.3. Execution State Tracking

The DAGExecutor updates workflow state as nodes complete:

```python
async def handle_node_completion(
    self,
    workflow_context: WorkflowExecutionContext,
    sub_task_id: str,
    result: WorkflowNodeResultData
):
    """Handle completion of a workflow node."""
    log_id = f"{self.host.log_identifier}[Workflow:{workflow_context.workflow_task_id}]"

    # Find which node this sub-task corresponds to
    node_id = workflow_context.get_node_id_for_sub_task(sub_task_id)

    if not node_id:
        log.error(f"{log_id} Received result for unknown sub-task: {sub_task_id}")
        return

    workflow_state = workflow_context.workflow_state

    # Check result status
    if result.status == "failure":
        log.error(f"{log_id} Node '{node_id}' failed: {result.error_message}")

        # Set error state
        workflow_state.error_state = {
            "failed_node_id": node_id,
            "failure_reason": "node_execution_failed",
            "error_message": result.error_message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Fail entire workflow
        await self.host.finalize_workflow_failure(
            workflow_context.a2a_context,
            WorkflowNodeFailureError(node_id, result.error_message)
        )
        return

    # Node succeeded
    log.info(f"{log_id} Node '{node_id}' completed successfully")

    # Update state
    workflow_state.completed_nodes[node_id] = result.artifact_name
    workflow_state.pending_nodes.remove(node_id)

    # Cache node output for value references
    artifact_data = await self._load_node_output(
        result.artifact_name,
        result.artifact_version,
        workflow_context
    )
    workflow_state.node_outputs[node_id] = {"output": artifact_data}

    # Continue workflow execution
    await self.execute_workflow(workflow_state, workflow_context)
```

#### 3.4.4. Error Propagation

Errors are propagated immediately to fail the workflow:

```python
class WorkflowNodeFailureError(Exception):
    """Raised when a workflow node fails."""
    def __init__(self, node_id: str, error_message: str):
        self.node_id = node_id
        self.error_message = error_message
        super().__init__(f"Node '{node_id}' failed: {error_message}")

# In DAGExecutor
async def execute_node(
    self,
    node_id: str,
    workflow_state: WorkflowExecutionState,
    workflow_context: WorkflowExecutionContext
):
    """Execute a single workflow node."""
    log_id = f"{self.host.log_identifier}[Node:{node_id}]"

    try:
        node = self.nodes[node_id]

        # Handle different node types
        if node.type == "agent":
            await self._execute_agent_node(node, workflow_state, workflow_context)
        elif node.type == "conditional":
            await self._execute_conditional_node(node, workflow_state, workflow_context)
        elif node.type == "fork":
            await self._execute_fork_node(node, workflow_state, workflow_context)
        elif node.type == "loop":
            await self._execute_loop_node(node, workflow_state, workflow_context)
        else:
            raise ValueError(f"Unknown node type: {node.type}")

    except Exception as e:
        log.error(f"{log_id} Node execution failed: {e}")

        # Set error state
        workflow_state.error_state = {
            "failed_node_id": node_id,
            "failure_reason": "execution_error",
            "error_message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Propagate error
        raise WorkflowNodeFailureError(node_id, str(e)) from e
```

