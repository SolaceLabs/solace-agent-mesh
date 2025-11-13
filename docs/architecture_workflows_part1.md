# Prescriptive Workflows - Architecture Design Document (Part 1 of 3)

**Document Version:** 1.0
**Last Updated:** 2025-11-13
**Status:** Draft

---

## 1. Introduction

### 1.1. Purpose

This document describes the architecture and design for the Prescriptive Workflows feature in Solace Agent Mesh (SAM). Prescriptive Workflows enable users to create deterministic, multi-step agent orchestrations using directed acyclic graphs (DAGs). This feature extends SAM's agent-to-agent (A2A) protocol to support complex, reproducible workflows while maintaining the "workflows as agents" abstraction.

### 1.2. Scope

This document covers:

- Core component architecture (WorkflowExecutorComponent, WorkflowApp)
- Agent workflow support extensions (WorkflowNodeHandler)
- DAG execution engine and flow control implementation
- Schema validation system
- Value reference resolution mechanisms
- A2A protocol extensions
- Integration with existing SAM components

This document does not cover:

- Testing strategies or test plans
- Rollout or migration procedures
- Performance benchmarks or optimization strategies
- Visual workflow designer implementation
- Workflow versioning or upgrade paths
- Crash recovery for the Workflow Executor (workflows will fail if the executor restarts)

### 1.3. Terminology

**Agent Persona** - An individual agent that performs a specific function within a workflow. Agent personas are implemented as standard SAM agents (SamAgentComponent instances) with defined input and output schemas.

**DAG (Directed Acyclic Graph)** - A graph structure where nodes represent workflow steps and edges represent data flow and dependencies. The graph contains no cycles, ensuring workflows terminate.

**Flow Control Node** - A special workflow node that implements control structures (conditional branching, parallel execution, loops) rather than agent invocation.

**Node** - A single step in a workflow DAG. Nodes can be agent invocations or flow control operations.

**Result Artifact** - An artifact created by an agent persona that represents the output of a workflow node. Result artifacts are marked using the result embed syntax.

**Schema** - A JSON Schema definition that describes the expected structure of input or output data for an agent or workflow.

**Value Reference** - A reference to data stored in artifacts, using either template syntax (`{{...}}`) or embed syntax (`«value:...»`).

**Workflow Executor** - The WorkflowExecutorComponent instance that orchestrates the execution of a workflow DAG.

**Workflow Instance** - A single execution of a workflow, identified by a unique task ID and associated with a specific user session.

### 1.4. Design Principles

The following principles guide the architecture:

**Workflows as Agents** - Workflows are exposed as standard A2A agents. External clients interact with workflows identically to how they interact with individual agents, using the same A2A protocol messages.

**Agent Self-Validation** - Agent personas validate their own inputs and outputs against schemas. This keeps validation logic close to the agent implementation and enables intelligent retry with LLM feedback.

**Runtime Flexibility** - Schema validation and workflow execution occur at runtime rather than at startup. This enables dynamic agent discovery and supports evolving agent capabilities.

**A2A Communication** - All communication between the workflow executor and agent personas occurs via A2A messages over the Solace broker. This enables distributed deployment and independent scaling.

**Fail-Fast Error Handling** - Workflows fail immediately when a node fails. Individual agents retry validation failures, but workflows do not automatically retry failed nodes.

**Schema-Based Contracts** - Schemas define clear contracts between workflow nodes and agent personas, enabling type safety and automatic validation.

**Reuse Existing Infrastructure** - The implementation maximizes reuse of existing SAM components (SamComponentBase, ADK services, A2A protocol helpers) rather than creating parallel systems.

**Schema Versioning** - Breaking changes to a persona agent's input or output schema require the deployment of a new agent persona with a unique name. Workflows must then be updated to call the new persona. Non-breaking, backward-compatible changes do not require a new persona.

---

## 2. System Architecture Overview

### 2.1. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Solace Event Broker                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  A2A Topics                                                     │ │
│  │  • {namespace}/a2a/v1/discovery/agentcards                     │ │
│  │  • {namespace}/a2a/v1/agent/request/{agent_name}               │ │
│  │  • {namespace}/a2a/v1/agent/response/{delegating_agent}/{id}   │ │
│  │  • {namespace}/a2a/v1/agent/status/{delegating_agent}/{id}     │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
           ▲                    ▲                    ▲
           │                    │                    │
           │                    │                    │
    ┌──────┴──────┐      ┌──────┴──────┐     ┌──────┴──────┐
    │  Gateway    │      │  Workflow   │     │   Persona   │
    │ Component   │      │  Executor   │     │   Agents    │
    │             │      │  Component  │     │             │
    │ • Receives  │      │             │     │ • Agent A   │
    │   user req  │      │ • Executes  │     │ • Agent B   │
    │ • Routes to │      │   DAG       │     │ • Agent C   │
    │   workflow  │      │ • Calls     │     │             │
    │             │      │   personas  │     │ Each agent: │
    │             │      │ • Validates │     │ • Has schema│
    │             │      │   flow      │     │ • Validates │
    │             │      │ • Manages   │     │   own I/O   │
    │             │      │   state     │     │ • Retries   │
    └─────────────┘      └──────┬──────┘     └─────────────┘
                                │
                                │
                    ┌───────────┴───────────┐
                    │   ADK Services        │
                    │                       │
                    │ • Session Service     │
                    │   (workflow state)    │
                    │ • Artifact Service    │
                    │   (node outputs)      │
                    └───────────────────────┘
```

### 2.2. Component Relationships

The Prescriptive Workflows feature introduces three primary components:

**WorkflowExecutorComponent** - Orchestrates workflow execution by:
- Publishing a workflow agent card to the A2A discovery topic
- Receiving A2A task requests on the workflow's agent request topic
- Executing the workflow DAG by invoking agent personas
- Managing workflow execution state in the session service
- Publishing status updates and final results via A2A

**WorkflowApp** - Provides the application-level configuration and initialization:
- Validates workflow YAML configuration using Pydantic models
- Generates Solace topic subscriptions for the workflow
- Instantiates the WorkflowExecutorComponent
- Extends SamAgentAppConfig to support workflow-specific settings

**WorkflowNodeHandler** - Extends SamAgentComponent to support workflow mode:
- Detects when an agent is being invoked as a workflow node
- Validates input against the agent's input schema
- Injects workflow-specific instructions into the agent's system prompt
- Validates output artifacts against the agent's output schema
- Retries LLM invocation on validation failures
- Returns structured result data to the workflow executor

These components integrate with existing SAM infrastructure:

**SamComponentBase** - Provides the base class for both WorkflowExecutorComponent and SamAgentComponent, including:
- Dedicated asyncio event loop management
- A2A message publishing with size validation
- Namespace and configuration management

**ADK Services** - Session, artifact, and memory services are used by:
- WorkflowExecutorComponent: stores workflow execution state and intermediate results
- SamAgentComponent: stores agent context and generated artifacts

**A2A Protocol** - All inter-component communication uses the existing A2A protocol messages, extended with new DataPart types for workflow-specific data.

### 2.3. Communication Flow

A typical workflow execution follows this sequence:

1. **User Request** - A user sends a request to the workflow via a gateway component
   - Gateway publishes A2A SendMessageRequest to workflow's agent request topic
   - Request includes user query, session ID, and user configuration

2. **Workflow Initialization** - WorkflowExecutorComponent receives the request
   - Creates or retrieves workflow execution state from session service
   - Validates workflow input against input schema
   - Initializes DAG execution with the first node

3. **Node Execution Loop** - For each node in the workflow:
   - Workflow executor constructs A2A request for the persona agent
   - Request includes WorkflowNodeRequestData with schemas
   - Workflow publishes request to persona's agent request topic
   - Workflow subscribes to persona's response and status topics

4. **Persona Execution** - Agent persona processes the workflow node:
   - SamAgentComponent detects workflow mode from DataPart
   - Validates input against schema (from DataPart or agent config)
   - Injects workflow instructions into system prompt
   - Executes ADK agent (LLM and tools)
   - Validates output artifact against schema
   - Retries on validation failure (up to configured max)
   - Returns WorkflowNodeResultData to workflow

5. **Result Processing** - Workflow executor handles persona response:
   - Updates workflow state with node completion
   - Stores reference to result artifact
   - Determines next nodes to execute based on dependencies
   - Continues execution loop or finalizes workflow

6. **Workflow Finalization** - When all nodes complete:
   - Workflow constructs final output by applying output mapping
   - Creates final result artifact
   - Publishes A2A Task response with final status
   - Cleans up workflow execution state (with TTL)

7. **Status Updates** - Throughout execution:
   - Workflow publishes TaskStatusUpdateEvent messages
   - Status includes current node, progress, and errors
   - Gateway forwards status to user

### 2.4. "Workflows as Agents" Abstraction

The "workflows as agents" design principle means workflows are indistinguishable from regular agents at the A2A protocol level:

**Discovery** - Workflows publish agent cards to the discovery topic, just like agents:
- Agent card includes workflow name, description, capabilities
- Input and output schemas define workflow interface
- Skills section can advertise workflow capabilities

**Invocation** - Clients invoke workflows using standard A2A messages:
- SendMessageRequest with user query and context
- Same message format as invoking a single agent
- No special workflow-specific protocol required

**Response** - Workflows respond with standard A2A Task responses:
- Final Task message with completed/failed status
- Same response format as a single agent
- Result artifacts attached per A2A protocol

**Status Updates** - Workflows publish status updates during execution:
- TaskStatusUpdateEvent messages during node execution
- Same format as agent status updates
- Gateway can display progress to user

This abstraction provides several benefits:

**Composability** - Workflows can invoke other workflows as personas, enabling nested orchestration without special handling.

**Client Simplicity** - Gateways and other clients use the same code paths for workflows and agents, reducing complexity.

**Protocol Stability** - The A2A protocol does not require workflow-specific extensions, maintaining backward compatibility.

**Migration Path** - Existing single agents can be replaced with workflows transparently, enabling gradual migration to orchestrated approaches.

The abstraction is maintained through careful design:
- Workflow configuration extends agent configuration
- WorkflowExecutorComponent extends SamComponentBase like SamAgentComponent
- Workflow state is stored in session service like agent conversation history
- Result artifacts use the same artifact service as agent outputs

---

## 3. Core Components

### 3.1. WorkflowExecutorComponent

#### 3.1.1. Component Responsibilities

WorkflowExecutorComponent serves as the orchestration engine for workflow execution. Its responsibilities include:

**DAG Execution Management**
- Parse workflow definition into executable DAG structure
- Determine node execution order based on dependencies
- Track completed, active, and pending nodes
- Handle flow control nodes (conditional, fork/join, loop)

**Persona Coordination**
- Construct A2A requests for persona agents with workflow context
- Publish requests to persona agent request topics
- Subscribe to and correlate persona responses
- Handle persona timeouts and failures

**State Management**
- Create and maintain workflow execution state in session service
- Store node outputs and intermediate results as artifacts
- Cache node output data for value reference resolution
- Clean up state on workflow completion

**Schema Validation**
- Validate workflow input against workflow input schema
- Retrieve persona schemas from agent registry
- Apply schema overrides from workflow configuration
- Validate final workflow output against output schema

**A2A Protocol Integration**
- Publish workflow agent card on startup
- Handle incoming SendMessageRequest messages
- Publish TaskStatusUpdateEvent messages during execution
- Return final Task response with success/failure status

**Error Handling**
- Detect and handle node execution failures
- Track error state in workflow execution state
- Fail entire workflow on any node failure
- Report errors via A2A error responses

#### 3.1.2. Class Structure and Base Classes

```python
class WorkflowExecutorComponent(SamComponentBase):
    """
    Orchestrates workflow execution by coordinating persona agents.

    Extends SamComponentBase to leverage:
    - Dedicated asyncio event loop
    - A2A message publishing infrastructure
    - Component lifecycle management
    """

    def __init__(self, **kwargs):
        """
        Initialize workflow executor component.

        Configuration loaded from WorkflowAppConfig via get_config():
        - workflow_name: Unique identifier for this workflow
        - workflow: WorkflowDefinition with DAG structure
        - namespace: A2A topic namespace
        - session_service, artifact_service: ADK service configs
        - agent_card: Workflow discovery information
        """
        super().__init__(info, **kwargs)

        # Configuration
        self.workflow_name: str
        self.namespace: str
        self.workflow_definition: WorkflowDefinition

        # Services
        self.session_service: BaseSessionService
        self.artifact_service: BaseArtifactService
        self.agent_registry: AgentRegistry

        # Execution tracking
        self.active_workflows: Dict[str, WorkflowExecutionContext]
        self.active_workflows_lock: threading.Lock

        # DAG executor and components
        self.dag_executor: DAGExecutor
        self.persona_caller: PersonaCaller

    def invoke(self, message: SolaceMessage, data: dict) -> dict:
        """Placeholder invoke method. Logic in process_event."""
        pass

    def process_event(self, event: Event):
        """
        Process incoming events (messages, timers, cache expiry).
        Delegates to async event handlers on component's event loop.
        """
        pass

    async def handle_task_request(
        self,
        a2a_request: A2ARequest,
        original_message: SolaceMessage
    ):
        """
        Handle incoming A2A SendMessageRequest for workflow execution.
        Entry point for workflow execution.
        """
        pass

    async def execute_workflow(
        self,
        workflow_input: Dict[str, Any],
        a2a_context: Dict[str, Any]
    ) -> WorkflowExecutionResult:
        """
        Execute the workflow DAG from start to finish.
        Coordinates with DAGExecutor for node execution.
        """
        pass

    async def finalize_workflow_success(self, workflow_context: Dict):
        """Finalize successful workflow execution and publish result."""
        pass

    async def finalize_workflow_failure(
        self,
        workflow_context: Dict,
        error: Exception
    ):
        """Finalize failed workflow execution and publish error."""
        pass

    async def _async_setup_and_run(self) -> None:
        """
        Async initialization called by SamComponentBase.
        Sets up services and publishes workflow agent card.
        """
        pass

    def _pre_async_cleanup(self) -> None:
        """Pre-cleanup before async loop stops."""
        pass

    def cleanup(self):
        """Clean up resources on component shutdown."""
        pass
```

**Key Design Decisions:**

- Extends `SamComponentBase` rather than `SamAgentComponent` because workflows don't host LLM agents
- Uses dedicated asyncio event loop from base class for async operations
- Maintains `active_workflows` dictionary similar to `active_tasks` in SamAgentComponent
- Delegates DAG execution to `DAGExecutor` for separation of concerns
- Uses `PersonaCaller` for A2A communication with persona agents

#### 3.1.3. Lifecycle and Initialization

WorkflowExecutorComponent follows this initialization sequence:

**1. Synchronous Initialization (`__init__`)**
```python
def __init__(self, **kwargs):
    super().__init__(info, **kwargs)

    # Retrieve configuration
    self.workflow_name = self.get_config("workflow_name")
    self.namespace = self.get_config("namespace")
    workflow_config = self.get_config("workflow")

    # Parse workflow definition
    self.workflow_definition = WorkflowDefinition.model_validate(
        workflow_config
    )

    # Initialize synchronous services
    self.session_service = initialize_session_service(self)
    self.artifact_service = initialize_artifact_service(self)

    # Initialize execution tracking
    self.active_workflows = {}
    self.active_workflows_lock = threading.Lock()

    # Initialize executor components
    self.dag_executor = DAGExecutor(self.workflow_definition, self)
    self.persona_caller = PersonaCaller(self)

    # Create agent registry for persona discovery
    self.agent_registry = AgentRegistry()
```

**2. Asynchronous Initialization (`_async_setup_and_run`)**
```python
async def _async_setup_and_run(self):
    # Subscribe to discovery topic for persona agent cards
    discovery_topic = a2a.get_discovery_topic(self.namespace)
    self.subscribe_to_topic(discovery_topic)

    # Publish workflow agent card
    await self._publish_workflow_agent_card()

    # Component is now ready to receive requests
    log.info(f"{self.log_identifier} Workflow ready: {self.workflow_name}")
```

**3. Agent Card Publishing**
```python
async def _publish_workflow_agent_card(self):
    """Publish workflow as an agent card for discovery."""
    agent_card = AgentCard(
        name=self.workflow_name,
        display_name=self.get_config("display_name"),
        description=self.workflow_definition.description,
        input_schema=self.workflow_definition.input_schema,
        output_schema=self.workflow_definition.output_schema,
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=self.workflow_definition.skills or [],
        # ... other agent card fields
    )

    discovery_topic = a2a.get_discovery_topic(self.namespace)
    self.publish_a2a_message(
        payload=agent_card.model_dump(exclude_none=True),
        topic=discovery_topic
    )
```

**4. Runtime Operation**

The component then enters its main operation loop:
- Event loop processes incoming A2A messages
- `process_event` delegates to async handlers
- `handle_task_request` initiates workflow execution
- Multiple workflows can execute concurrently

**5. Cleanup (`cleanup`)**
```python
def cleanup(self):
    log.info(f"{self.log_identifier} Cleaning up workflow executor")

    # Cancel active workflows
    with self.active_workflows_lock:
        for workflow_context in self.active_workflows.values():
            workflow_context.cancel()
        self.active_workflows.clear()

    # Call base class cleanup (stops async loop)
    super().cleanup()
```

#### 3.1.4. State Management

WorkflowExecutorComponent manages two levels of state:

**Component-Level State** - Tracks all active workflow instances:
```python
# In-memory tracking of active workflows
self.active_workflows: Dict[str, WorkflowExecutionContext] = {}

class WorkflowExecutionContext:
    """Context for a single workflow execution instance."""
    workflow_task_id: str
    session_id: str
    user_id: str
    a2a_context: Dict[str, Any]
    workflow_state: WorkflowExecutionState
    active_persona_calls: Dict[str, PersonaCallContext]
    lock: threading.Lock
```

**Workflow Execution State** - Persisted to session service:
```python
class WorkflowExecutionState(BaseModel):
    """State stored in ADK session for workflow execution."""
    workflow_name: str
    execution_id: str
    start_time: datetime

    # Current execution status
    current_node_id: Optional[str] = None
    completed_nodes: Dict[str, str] = {}  # node_id → artifact_name
    pending_nodes: List[str] = []

    # Fork/join tracking
    active_branches: Dict[str, List[str]] = {}  # fork_id → branch_node_ids

    # Error tracking
    error_state: Optional[Dict[str, Any]] = None

    # Cached node outputs for value resolution
    node_outputs: Dict[str, Dict[str, Any]] = {}

    # Metadata
    metadata: Dict[str, Any] = {}
```

**State Lifecycle:**

1. **Creation** - On workflow start:
```python
async def _initialize_workflow_state(
    self,
    workflow_input: Dict[str, Any],
    a2a_context: Dict[str, Any]
) -> WorkflowExecutionState:
    execution_id = str(uuid.uuid4())

    state = WorkflowExecutionState(
        workflow_name=self.workflow_name,
        execution_id=execution_id,
        start_time=datetime.now(timezone.utc),
        pending_nodes=self.dag_executor.get_initial_nodes()
    )

    # Store in session
    session = await self.session_service.get_session(
        app_name=self.workflow_name,
        user_id=a2a_context["user_id"],
        session_id=a2a_context["session_id"]
    )

    session.state["workflow_execution"] = state.model_dump()
    await self.session_service.update_session(session)

    return state
```

2. **Updates** - After each node completes:
```python
async def _update_workflow_state(
    self,
    workflow_context: WorkflowExecutionContext,
    node_id: str,
    result_artifact_name: str
):
    state = workflow_context.workflow_state

    # Mark node complete
    state.completed_nodes[node_id] = result_artifact_name

    # Update pending nodes
    next_nodes = self.dag_executor.get_next_nodes(state)
    state.pending_nodes = next_nodes
    state.current_node_id = next_nodes[0] if next_nodes else None

    # Persist to session
    session = await self._get_workflow_session(workflow_context)
    session.state["workflow_execution"] = state.model_dump()
    await self.session_service.update_session(session)
```

3. **Cleanup** - On workflow completion:
```python
async def _cleanup_workflow_state(
    self,
    workflow_context: WorkflowExecutionContext
):
    # Set TTL on session state for auto-cleanup
    session = await self._get_workflow_session(workflow_context)

    # Mark workflow complete
    state = workflow_context.workflow_state
    state.metadata["completion_time"] = datetime.now(timezone.utc).isoformat()
    state.metadata["status"] = "completed"

    session.state["workflow_execution"] = state.model_dump()
    await self.session_service.update_session(session)

    # Remove from active workflows
    with self.active_workflows_lock:
        self.active_workflows.pop(workflow_context.workflow_task_id, None)
```

**State Persistence Strategy:**

- State is stored in the ADK session service's `state` dictionary
- Session ID from the original A2A request is used as the key
- State is serialized to JSON using Pydantic's `model_dump()`
- State includes only serializable data (no object references)
- TTL is configured at the session service level (not per-workflow)

#### 3.1.5. A2A Protocol Integration

WorkflowExecutorComponent integrates with the A2A protocol as both an agent (receiving requests) and a client (calling personas).

**As an Agent (Receiving Requests):**

1. **Subscription Setup** - WorkflowApp configures subscriptions:
```python
# In WorkflowApp.__init__
request_topic = a2a.get_agent_request_topic(
    namespace,
    workflow_name
)
subscriptions.append(request_topic)
```

2. **Request Handling** - Component receives SendMessageRequest:
```python
async def handle_task_request(
    self,
    a2a_request: A2ARequest,
    original_message: SolaceMessage
):
    # Extract message and context
    message = a2a.get_message_from_send_request(a2a_request)
    request_id = a2a.get_request_id(a2a_request)

    # Extract user properties
    user_properties = original_message.get_user_properties()
    user_id = user_properties.get("userId")
    user_config = user_properties.get("a2aUserConfig", {})

    # Create A2A context
    a2a_context = {
        "logical_task_id": str(uuid.uuid4()),
        "session_id": message.contextId,
        "user_id": user_id,
        "a2a_user_config": user_config,
        "jsonrpc_request_id": request_id,
        "original_solace_message": original_message,
        # ... other context
    }

    # Execute workflow
    await self.execute_workflow(message, a2a_context)
```

3. **Status Updates** - Published during execution:
```python
async def _publish_node_status(
    self,
    node_id: str,
    status: str,
    a2a_context: Dict
):
    status_event = TaskStatusUpdateEvent(
        task_id=a2a_context["logical_task_id"],
        context_id=a2a_context["session_id"],
        status=a2a.create_task_status(
            state=TaskState.working,
            message=a2a.create_agent_text_message(
                text=f"Executing node: {node_id}"
            )
        ),
        final=False,
        kind="status-update",
        metadata={
            "workflow_node_id": node_id,
            "workflow_node_status": status
        }
    )

    # Publish to status topic
    status_topic = a2a_context.get("statusTopic") or \
        a2a.get_gateway_status_topic(
            self.namespace,
            self.get_gateway_id(),
            a2a_context["logical_task_id"]
        )

    response = a2a.create_success_response(
        result=status_event,
        request_id=a2a_context["jsonrpc_request_id"]
    )

    self.publish_a2a_message(
        payload=response.model_dump(exclude_none=True),
        topic=status_topic,
        user_properties={"a2aUserConfig": a2a_context["a2a_user_config"]}
    )
```

4. **Final Response** - Published on completion:
```python
async def finalize_workflow_success(self, workflow_context: Dict):
    # Create final result artifact
    final_artifact = await self._construct_final_output(workflow_context)

    # Create final task response
    final_task = a2a.create_final_task(
        task_id=workflow_context["logical_task_id"],
        context_id=workflow_context["session_id"],
        final_status=a2a.create_task_status(
            state=TaskState.completed,
            message=a2a.create_agent_text_message(
                text="Workflow completed successfully"
            )
        ),
        metadata={"workflow_name": self.workflow_name}
    )

    # Publish response
    response_topic = workflow_context.get("replyToTopic") or \
        a2a.get_client_response_topic(
            self.namespace,
            workflow_context["client_id"]
        )

    response = a2a.create_success_response(
        result=final_task,
        request_id=workflow_context["jsonrpc_request_id"]
    )

    self.publish_a2a_message(
        payload=response.model_dump(exclude_none=True),
        topic=response_topic
    )

    # ACK original message
    original_message = workflow_context.get("original_solace_message")
    if original_message:
        original_message.call_acknowledgements()
```

**As a Client (Calling Personas):**

The workflow executor uses PersonaCaller to invoke persona agents via A2A. This follows the same pattern as PeerAgentTool in SamAgentComponent.

1. **Subscription Setup** - Subscribe to persona responses:
```python
# In _async_setup_and_run
response_subscription = a2a.get_agent_response_subscription_topic(
    self.namespace,
    self.workflow_name
)
self.subscribe_to_topic(response_subscription)

status_subscription = a2a.get_agent_status_subscription_topic(
    self.namespace,
    self.workflow_name
)
self.subscribe_to_topic(status_subscription)
```

2. **Request Publishing** - Handled by PersonaCaller (detailed in Section 3.5)

3. **Response Correlation** - Match responses to requests:
```python
async def handle_persona_response(
    self,
    response: JSONRPCResponse,
    message: SolaceMessage
):
    # Extract sub-task ID from topic
    topic = message.get_destination_name()
    sub_task_id = self._extract_sub_task_id_from_topic(topic)

    # Find workflow context
    workflow_context = self._find_workflow_by_sub_task(sub_task_id)
    if not workflow_context:
        log.warning(f"Received response for unknown sub-task: {sub_task_id}")
        return

    # Extract result
    task = a2a.get_response_result(response)

    # Process node completion
    await self.dag_executor.handle_node_completion(
        workflow_context,
        sub_task_id,
        task
    )
```

#### 3.1.6. Event Processing Flow

WorkflowExecutorComponent handles multiple event types:

```python
def process_event(self, event: Event):
    """Process incoming events on the async loop."""
    loop = self.get_async_loop()

    if event.event_type == EventType.MESSAGE:
        # Parse A2A message
        payload = event.data.get_payload_as_dict()
        a2a_request = A2ARequest.model_validate(payload)
        method = a2a.get_request_method(a2a_request)

        if method == "message/send":
            # New workflow request
            coro = self.handle_task_request(a2a_request, event.data)
        elif method == "tasks/cancel":
            # Workflow cancellation. This triggers cancellation of the
            # entire workflow and propagates cancel requests to any
            # active persona calls.
            task_id = a2a.get_task_id_from_cancel_request(a2a_request)
            coro = self.handle_cancel_request(task_id)
        else:
            # Check if it's a persona response
            topic = event.data.get_destination_name()
            if self._is_persona_response_topic(topic):
                coro = self.handle_persona_response(a2a_request, event.data)
            else:
                log.warning(f"Unknown A2A method: {method}")
                return

        # Schedule on async loop
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        future.add_done_callback(self._handle_event_completion)

    elif event.event_type == EventType.TIMER:
        # Timer for periodic operations (if needed)
        pass

    elif event.event_type == EventType.CACHE_EXPIRY:
        # Handle persona call timeouts
        coro = self.handle_persona_timeout(event.data)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
```

