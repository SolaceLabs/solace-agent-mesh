# Workflows Detailed Architecture

This document provides a comprehensive technical architecture of Workflows in Solace Agent Mesh (SAM). It is intended for developers who need deep understanding of the implementation details, code paths, and design rationale. This document is self-contained; there is no need to read other workflow architecture documents.

## Table of Contents

1. [Overview](#overview)
2. [Design Philosophy](#design-philosophy)
3. [Core Components](#core-components)
4. [Agent Card and Discovery](#agent-card-and-discovery)
5. [WorkflowAgentTool: Invoking Workflows](#workflowagenttool-invoking-workflows)
6. [Workflow Protocol Messages](#workflow-protocol-messages)
7. [WorkflowNodeHandler: Agent-Side Support](#workflownodehandler-agent-side-support)
8. [DAG Execution Engine](#dag-execution-engine)
9. [Node Type Implementations](#node-type-implementations)
10. [Template Expression Resolution](#template-expression-resolution)
11. [Conditional Expression Evaluation](#conditional-expression-evaluation)
12. [Execution State Management](#execution-state-management)
13. [Error Handling and Recovery](#error-handling-and-recovery)
14. [Workflow Definition Schema](#workflow-definition-schema)
15. [Implementation Files Reference](#implementation-files-reference)

---

## Overview

Workflows enable DAG-based orchestration of agents with schema validation and data integrity guarantees. Previously called "Prescribed Workflows," this feature is now referred to simply as "Workflows."

A workflow defines a directed acyclic graph (DAG) of nodes that execute in dependency order. Each node typically invokes an agent to perform work. The workflow engine coordinates execution, manages data flow between nodes, and validates data at boundaries.

### What Problems Workflows Solve

1. **Reliability**—Schema validation at workflow edges ensures type safety and predictable behavior across agent invocations.

2. **Data Integrity**—Artifact-based data flow prevents LLM hallucination of critical values. When an agent needs to pass an order ID or customer key to the next step, that value travels through the artifact system, not through LLM generation.

3. **Composability**—Workflows appear as agents, so they can be invoked by other workflows or by the orchestrator using the same A2A protocol.

4. **Observability**—The workflow engine publishes structured events at each execution stage, enabling debugging, monitoring, and visualization.

---

## Design Philosophy

### Workflows-as-Agents Pattern

The fundamental design decision: externally, a workflow is indistinguishable from a regular agent. It publishes an Agent Card, accepts A2A tasks, and returns responses through the standard protocol.

This was a deliberate choice over introducing a separate "workflow" entity type. The alternative would have required:
- New discovery mechanisms
- New invocation protocols
- Special handling in the orchestrator and gateways
- Separate tooling for workflow invocation

By implementing workflows as agents:
- Workflows are discoverable through the same Agent Card mechanism
- Any agent (including the orchestrator) can invoke a workflow without special handling
- Workflows can invoke other workflows, enabling composition
- The `WorkflowExecutorComponent` extends the same base as regular agent components, reusing infrastructure for message handling, session management, and artifact storage

### Argo Workflows Alignment

During design, we evaluated several workflow engines: AWS Step Functions, Apache Airflow, and Argo Workflows. Argo Workflows was the closest match to SAM's needs.

**What we adopted from Argo:**
- `dependencies` as an alias for `depends_on`
- `withParam` and `withItems` for map node item sources
- `retryStrategy` with backoff configuration
- `when` clauses for conditional node execution
- Template syntax patterns

**What we extended for SAM:**
- `agent_name` to specify which agent executes a node
- Template expressions using `{{path.to.value}}` syntax (simplified from Argo's `{{=...}}`)
- `coalesce` and `concat` operators for data transformation
- Workflow-specific Agent Card extensions
- Schema validation at node boundaries

We support both Argo field names and SAM equivalents (for example, both `depends_on` and `dependencies` work) to make the syntax familiar to developers with Argo experience.

---

## Core Components

### Component Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Calling Agent                                 │
│  (Orchestrator or any agent with WorkflowAgentTool)                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ A2A SendMessageRequest
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   WorkflowExecutorComponent                          │
│                   (src/solace_agent_mesh/workflow/component.py)      │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  Agent Card     │  │  DAGExecutor    │  │   AgentCaller       │  │
│  │  Publishing     │  │                 │  │                     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              WorkflowExecutionContext (per execution)        │    │
│  │  - execution_id, task_id, caller_agent                       │    │
│  │  - sub_task_to_node mapping                                  │    │
│  │  - WorkflowExecutionState (node progress, outputs, etc.)     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ A2A Request (WorkflowNodeRequestData)
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Worker Agent                                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   WorkflowNodeHandler                        │    │
│  │   (src/solace_agent_mesh/agent/sac/workflow_support/handler.py)  │
│  │                                                              │    │
│  │   - Detects WorkflowNodeRequestData                          │    │
│  │   - Validates input against schema                           │    │
│  │   - Injects workflow instructions into LLM                   │    │
│  │   - Validates output against schema                          │    │
│  │   - Returns WorkflowNodeResultData                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### WorkflowExecutorComponent

**Location:** `src/solace_agent_mesh/workflow/component.py`

The execution engine that:
- Loads workflow definitions from YAML configuration
- Publishes Agent Cards with workflow-specific extensions
- Manages workflow execution lifecycles
- Coordinates DAGExecutor and AgentCaller
- Handles A2A protocol messages (requests, responses, events)
- Maintains active workflow contexts

Key methods:
- `_create_workflow_agent_card()`: Builds Agent Card with extensions
- `handle_a2a_request()`: Entry point for workflow invocation
- `_handle_node_completion()`: Processes agent responses
- `finalize_workflow_success()`: Completes workflow and returns result
- `publish_workflow_event()`: Emits execution events for observability

### DAGExecutor

**Location:** `src/solace_agent_mesh/workflow/dag_executor.py`

Handles the execution graph:
- Analyzes node dependencies at initialization
- Determines which nodes can run next based on completed dependencies
- Evaluates conditional expressions for branching
- Resolves template expressions (`{{node.output.field}}`)
- Manages skipped branches and join synchronization

Key methods:
- `get_next_nodes()`: Returns nodes ready to execute
- `get_initial_nodes()`: Returns nodes with no dependencies
- `execute_workflow()`: Main execution loop
- `execute_node()`: Dispatches individual node execution
- `resolve_value()`: Resolves template expressions and operators
- `_skip_branch()`: Recursively skips nodes on untaken branches

### AgentCaller

**Location:** `src/solace_agent_mesh/workflow/agent_caller.py`

Dispatches tasks to worker agents:
- Resolves node input from templates or implicit inference
- Constructs A2A messages with `WorkflowNodeRequestData`
- Retrieves schemas from Agent Card extensions
- Applies schema overrides when specified
- Correlates responses back to originating workflow

Key methods:
- `call_agent()`: Main entry point for agent invocation
- `_resolve_node_input()`: Resolves input data from templates
- `_construct_agent_message()`: Builds A2A request message
- `_publish_agent_request()`: Sends request via Solace

---

## Agent Card and Discovery

### Extension URIs

Workflows use three Agent Card extensions:

| Extension | URI | Purpose |
|-----------|-----|---------|
| Agent Type | `https://solace.com/a2a/extensions/agent-type` | Identifies the agent as a workflow |
| Schemas | `https://solace.com/a2a/extensions/sam/schemas` | Input/output JSON schemas |
| Visualization | `https://solace.com/a2a/extensions/sam/workflow-visualization` | Mermaid diagram |

### Agent Type Extension

```json
{
  "uri": "https://solace.com/a2a/extensions/agent-type",
  "description": "Specifies the type of agent (e.g., 'workflow').",
  "params": {
    "type": "workflow"
  }
}
```

When an agent discovers another agent, it checks this extension. If `type` is `"workflow"`, SAM creates a `WorkflowAgentTool` instead of the standard `PeerAgentTool`. This is handled in `SamAgentComponent._process_agent_card()`:

```python
for ext in agent_card.capabilities.extensions:
    if ext.uri == EXTENSION_URI_AGENT_TYPE:
        agent_type = ext.params.get("type", "standard")
    elif ext.uri == EXTENSION_URI_SCHEMAS:
        input_schema = ext.params.get("input_schema")

if agent_type == "workflow" and input_schema:
    tool = WorkflowAgentTool(
        target_agent_name=agent_card.name,
        input_schema=input_schema,
        host_component=self,
    )
```

### Schemas Extension

```json
{
  "uri": "https://solace.com/a2a/extensions/sam/schemas",
  "description": "Input and output JSON schemas for the workflow.",
  "params": {
    "input_schema": {
      "type": "object",
      "properties": {
        "order_id": {"type": "string", "description": "Order identifier"},
        "amount": {"type": "integer", "description": "Order amount in cents"}
      },
      "required": ["order_id", "amount"]
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "status": {"type": "string"},
        "processed_id": {"type": "string"}
      }
    }
  }
}
```

The `input_schema` serves multiple purposes:
1. `WorkflowAgentTool` uses it to generate function declarations for the LLM
2. The workflow engine validates incoming requests against it
3. Documentation for callers about expected input format

### Visualization Extension

```json
{
  "uri": "https://solace.com/a2a/extensions/sam/workflow-visualization",
  "params": {
    "mermaid_source": "graph TD\n    Start([Start])\n    ..."
  }
}
```

The workflow engine auto-generates a Mermaid diagram from the workflow definition via `_generate_mermaid_diagram()`. Node shapes correspond to types:
- Rounded rectangles for agent nodes
- Diamonds for conditional and switch nodes
- Circles for join nodes
- Stadium shapes for loop nodes

### Agent Card Creation

The `_create_workflow_agent_card()` method assembles the complete Agent Card:

```python
def _create_workflow_agent_card(self) -> AgentCard:
    extensions_list = []

    # Agent type extension (always present)
    agent_type_extension = AgentExtension(
        uri=EXTENSION_URI_AGENT_TYPE,
        params={"type": "workflow"},
    )
    extensions_list.append(agent_type_extension)

    # Schema extension (if schemas defined)
    if input_schema or output_schema:
        schemas_extension = AgentExtension(
            uri=EXTENSION_URI_SCHEMAS,
            params={
                "input_schema": input_schema,
                "output_schema": output_schema,
            },
        )
        extensions_list.append(schemas_extension)

    # Visualization extension
    mermaid_source = self._generate_mermaid_diagram()
    viz_extension = AgentExtension(
        uri=EXTENSION_URI_WORKFLOW_VISUALIZATION,
        params={"mermaid_source": mermaid_source},
    )
    extensions_list.append(viz_extension)

    return AgentCard(
        name=self.workflow_name,
        description=self.workflow_definition.description,
        skills=self.workflow_definition.skills or [],
        capabilities=AgentCapabilities(extensions=extensions_list),
        url=f"solace:{a2a.get_agent_request_topic(self.namespace, self.workflow_name)}",
    )
```

---

## WorkflowAgentTool: Invoking Workflows

**Location:** `src/solace_agent_mesh/agent/tools/workflow_tool.py`

The `WorkflowAgentTool` is an ADK tool that enables LLM agents to invoke workflows. It supports dual-mode invocation: parameter mode and artifact mode.

### Tool Declaration Generation

The tool dynamically generates its ADK function declaration from the workflow's input schema:

```python
def _get_declaration(self) -> adk_types.FunctionDeclaration:
    properties = self.input_schema.get("properties", {})
    adk_properties = {}

    # Always add input_artifact option
    adk_properties["input_artifact"] = adk_types.Schema(
        type=adk_types.Type.STRING,
        description="Filename of an existing artifact containing the input JSON data. "
                    "Use this OR individual parameters.",
        nullable=True,
    )

    # Add each schema property
    for prop_name, prop_def in properties.items():
        json_type = prop_def.get("type", "string")
        adk_type = self._map_json_type_to_adk(json_type)

        adk_properties[prop_name] = adk_types.Schema(
            type=adk_type,
            description=prop_def.get("description", ""),
            nullable=True,  # Force optional for dual-mode support
        )

    return adk_types.FunctionDeclaration(
        name=self.name,
        description=f"Invoke the '{self.target_agent_name}' workflow. "
                    "Dual-mode: provide parameters directly OR 'input_artifact'.",
        parameters=adk_types.Schema(
            type=adk_types.Type.OBJECT,
            properties=adk_properties,
            required=[],  # All optional
        ),
    )
```

All parameters are marked as optional (`nullable=True`, empty `required` array) to support both invocation modes.

### Parameter Mode

When the LLM provides parameters directly (without `input_artifact`):

1. **Validation**: Parameters are validated against the workflow's `input_schema` using JSON Schema:
   ```python
   jsonschema.validate(instance=args, schema=self.input_schema)
   ```

2. **Artifact Creation**: Valid parameters are serialized to JSON and saved as an artifact:
   ```python
   payload_artifact_name = f"wi_{sanitized_wf_name}.json"
   await save_artifact_with_metadata(
       artifact_service=self.host_component.artifact_service,
       filename=payload_artifact_name,
       content_bytes=json.dumps(payload_data).encode("utf-8"),
       mime_type="application/json",
   )
   ```

3. **Invocation**: The artifact reference is included in the A2A message metadata.

Parameter mode is best for simple inputs that the LLM is constructing.

### Artifact Mode

When the LLM provides an `input_artifact` reference:

```python
input_artifact_name = args.get("input_artifact")
if input_artifact_name:
    # Pass-through: no re-validation, no re-serialization
    return input_artifact_name, None
```

The artifact filename is passed directly to the workflow. The workflow validates on receipt. Data stays in artifact form, never re-tokenized.

Artifact mode is essential for:
- Passing large datasets without re-tokenizing
- Chaining workflow outputs to inputs
- Preserving data integrity for critical values (IDs, keys, etc.)

### A2A Message Construction

Both modes result in an A2A `SendMessageRequest`:

```python
def _prepare_a2a_message(self, payload_artifact_name, payload_artifact_version, ...):
    a2a_message_parts = [
        a2a.create_text_part(
            text=f"Invoking workflow with input artifact: {payload_artifact_name}"
        )
    ]

    invoked_artifacts = []
    if payload_artifact_name:
        artifact_ref = {"filename": payload_artifact_name}
        if payload_artifact_version is not None:
            artifact_ref["version"] = payload_artifact_version
        invoked_artifacts.append(artifact_ref)

    a2a_metadata = {
        "sessionBehavior": "RUN_BASED",
        "parentTaskId": main_logical_task_id,
        "function_call_id": tool_context.function_call_id,
        "agent_name": self.target_agent_name,
        "invoked_with_artifacts": invoked_artifacts,
    }

    return a2a.create_user_message(
        parts=a2a_message_parts,
        metadata=a2a_metadata,
    )
```

Key metadata fields:
- `sessionBehavior: "RUN_BASED"`: Each workflow execution runs in isolated context
- `invoked_with_artifacts`: References the input artifact(s)
- `function_call_id`: Links back to the ADK function call for response routing

---

## Workflow Protocol Messages

**Location:** `src/solace_agent_mesh/common/data_parts.py`

Workflows communicate using structured `DataPart` messages embedded in A2A protocol messages. These are Pydantic models that serialize to JSON.

### WorkflowNodeRequestData

Sent by the workflow engine to an agent when invoking it as a node:

```python
class WorkflowNodeRequestData(BaseModel):
    type: Literal["workflow_node_request"] = "workflow_node_request"
    workflow_name: str          # Name of the workflow
    node_id: str                # ID of the workflow node
    input_schema: Optional[Dict[str, Any]]   # Schema to validate input against
    output_schema: Optional[Dict[str, Any]]  # Schema to validate output against
    suggested_output_filename: Optional[str] # Suggested filename for output artifact
```

This data part appears as the first part in the A2A message. The `WorkflowNodeHandler` in the target agent detects this and activates workflow mode.

The `suggested_output_filename` is generated by the workflow engine with a unique suffix:
```python
unique_suffix = sub_task_id[-8:]
safe_workflow_name = re.sub(r"[^a-zA-Z0-9_-]", "_", workflow_state.workflow_name)
suggested_output_filename = f"{safe_workflow_name}_{node.id}_{unique_suffix}.json"
```

### WorkflowNodeResultData

Returned by an agent to the workflow engine after node execution:

```python
class WorkflowNodeResultData(BaseModel):
    type: Literal["workflow_node_result"] = "workflow_node_result"
    status: Literal["success", "failure"]
    artifact_name: Optional[str]        # Output artifact filename (if success)
    artifact_version: Optional[int]     # Output artifact version
    error_message: Optional[str]        # Error description (if failure)
    validation_errors: Optional[List[str]]  # Schema validation errors
    retry_count: int = 0                # Number of retries attempted
```

### Execution Event Messages

These messages are published for observability and UI visualization:

**WorkflowExecutionStartData**: Published when a workflow execution begins
```python
class WorkflowExecutionStartData(BaseModel):
    type: Literal["workflow_execution_start"] = "workflow_execution_start"
    workflow_name: str
    execution_id: str
    input_artifact_ref: Optional[ArtifactRef]
    workflow_input: Optional[Dict[str, Any]]
```

**WorkflowNodeExecutionStartData**: Published when a workflow node begins execution
```python
class WorkflowNodeExecutionStartData(BaseModel):
    type: Literal["workflow_node_execution_start"] = "workflow_node_execution_start"
    node_id: str
    node_type: str  # "agent", "conditional", "switch", "join", "loop", "map", "fork"
    agent_name: Optional[str]
    sub_task_id: Optional[str]          # Links to A2A sub-task for agent nodes

    # Type-specific fields
    condition: Optional[str]            # For conditional/loop nodes
    true_branch: Optional[str]          # For conditional nodes
    false_branch: Optional[str]
    cases: Optional[List[SwitchCaseInfo]]  # For switch nodes
    wait_for: Optional[List[str]]       # For join nodes
    join_strategy: Optional[str]
    max_iterations: Optional[int]       # For loop nodes
```

**WorkflowNodeExecutionResultData**: Published when a workflow node completes
```python
class WorkflowNodeExecutionResultData(BaseModel):
    type: Literal["workflow_node_execution_result"] = "workflow_node_execution_result"
    node_id: str
    status: Literal["success", "failure", "skipped"]
    output_artifact_ref: Optional[ArtifactRef]
    error_message: Optional[str]
    condition_result: Optional[bool]    # For conditional nodes
    selected_branch: Optional[str]      # Which branch was taken
```

**WorkflowExecutionResultData**: Published when workflow execution completes
```python
class WorkflowExecutionResultData(BaseModel):
    type: Literal["workflow_execution_result"] = "workflow_execution_result"
    workflow_name: str
    execution_id: str
    status: Literal["success", "failure"]
    output_artifact_ref: Optional[ArtifactRef]
    error_message: Optional[str]
```

---

## WorkflowNodeHandler: Agent-Side Support

**Location:** `src/solace_agent_mesh/agent/sac/workflow_support/handler.py`

The `WorkflowNodeHandler` is a critical component that lives within standard agents. It enables any agent to participate as a workflow node without code changes.

### Detection and Activation

When an A2A message arrives at an agent, the handler checks for `WorkflowNodeRequestData`:

```python
def detect_workflow_request(self, message: A2AMessage) -> Optional[WorkflowNodeRequestData]:
    """Check if this message is a workflow node request."""
    for part in message.parts:
        if hasattr(part, 'data') and part.data:
            if part.data.get('type') == 'workflow_node_request':
                return WorkflowNodeRequestData(**part.data)
    return None
```

If detected, the handler takes over execution for that request.

### Input Validation

Before the agent's LLM runs, the handler validates incoming data against the node's schema:

```python
async def _validate_input(self, message, input_schema, a2a_context):
    input_data = await self._extract_input_data(message, input_schema, a2a_context)
    errors = validate_against_schema(input_data, input_schema)
    return errors if errors else None
```

If validation fails, the handler immediately returns an error to the workflow:

```python
if validation_errors:
    result_data = WorkflowNodeResultData(
        status="failure",
        error_message=f"Input validation failed: {validation_errors}",
    )
    return await self._return_workflow_result(workflow_data, result_data, a2a_context)
```

### Input Data Extraction

The handler supports two input formats:

1. **Single text field schema**: If the schema has exactly one property named `text` of type `string`, all text parts are aggregated:
   ```python
   def _is_single_text_schema(self, schema):
       properties = schema.get("properties", {})
       if len(properties) != 1 or "text" not in properties:
           return False
       return properties["text"].get("type") == "string"

   async def _extract_text_input(self, message):
       text_parts = [p.text for p in message.parts if hasattr(p, 'text')]
       return {"text": "\n".join(text_parts)}
   ```

2. **Structured schema**: Data is extracted from the first `FilePart` (JSON/YAML/CSV):
   ```python
   async def _extract_file_input(self, message, input_schema, a2a_context):
       file_parts = a2a.get_file_parts_from_message(message)
       file_part = file_parts[0]

       if a2a.is_file_part_bytes(file_part):
           return await self._process_file_with_bytes(file_part, ...)
       elif a2a.is_file_part_uri(file_part):
           return await self._process_file_with_uri(file_part, ...)
   ```

### System Prompt Injection

The handler injects workflow-specific instructions into the LLM's system prompt:

```python
def _generate_workflow_instructions(self, workflow_data, output_schema):
    instructions = f"""
## WORKFLOW NODE EXECUTION MODE

You are executing as part of the workflow '{workflow_data.workflow_name}'.
Your task ID within this workflow is: {workflow_data.node_id}

### Required Output Format

You MUST produce your result as a JSON artifact and signal completion using the result embed format:
«result:artifact=<filename>:<version> status=success»

For example: «result:artifact=output.json:0 status=success»
"""

    if output_schema:
        instructions += f"""
### Output Schema Requirements

Your output artifact MUST conform to this JSON Schema:
{json.dumps(output_schema, indent=2)}
"""

    return instructions
```

This callback is chained with any existing system instruction callback:

```python
def chained_callback(context, request):
    original_instr = original_callback(context, request) if original_callback else None
    workflow_instr = workflow_callback(context, request)
    return "\n\n".join(filter(None, [original_instr, workflow_instr]))

self.host.set_agent_system_instruction_callback(chained_callback)
```

### Result Embed Pattern

To signal completion, the agent must output a result embed in its response:

```
«result:artifact=output.json:0 status=success»
```

The handler parses this embed to identify the output artifact. If the agent fails:

```
«result:status=failure message="Description of the problem"»
```

### Output Validation

After the agent produces a result, the handler loads the referenced artifact and validates it against the output schema:

```python
async def _finalize_workflow_node_execution(self, adk_session, last_model_event,
                                            workflow_data, output_schema, retry_count):
    # Parse result embed from model output
    result_info = self._parse_result_embed(last_model_event.content)

    if result_info['status'] == 'failure':
        return WorkflowNodeResultData(status="failure", error_message=result_info['message'])

    # Load and validate artifact
    artifact = await self._load_artifact(result_info['artifact_name'])

    if output_schema:
        validation_errors = validate_against_schema(artifact.data, output_schema)
        if validation_errors:
            # Retry logic could go here
            return WorkflowNodeResultData(
                status="failure",
                validation_errors=validation_errors,
                retry_count=retry_count,
            )

    return WorkflowNodeResultData(
        status="success",
        artifact_name=result_info['artifact_name'],
        artifact_version=result_info['version'],
    )
```

### Session Handling

Workflow nodes execute with run-based session semantics:

```python
# Create run-based session ID
original_session_id = a2a_context.get("session_id")
logical_task_id = a2a_context.get("logical_task_id")
session_id = f"{original_session_id}:{logical_task_id}:run"

# Always create a new session for workflow nodes
adk_session = await self.host.session_service.create_session(
    app_name=self.host.agent_name,
    user_id=user_id,
    session_id=session_id,
)
```

This ensures each node invocation starts fresh while maintaining the ability to extract the parent session for artifact sharing.

---

## DAG Execution Engine

**Location:** `src/solace_agent_mesh/workflow/dag_executor.py`

The `DAGExecutor` manages the execution graph and coordinates node execution.

### Initialization

At workflow load time, the executor analyzes the graph structure:

```python
def __init__(self, workflow_definition, host_component):
    self.host = host_component
    self.nodes = {node.id: node for node in workflow_definition.nodes}

    # Build dependency graph
    self.dependencies = {}      # node_id -> [dependency_ids]
    self.reverse_dependencies = {}  # node_id -> [dependent_ids]

    for node in workflow_definition.nodes:
        deps = node.depends_on or []
        # Support Argo alias
        if hasattr(node, 'dependencies') and node.dependencies:
            deps = node.dependencies
        self.dependencies[node.id] = deps

        for dep in deps:
            if dep not in self.reverse_dependencies:
                self.reverse_dependencies[dep] = []
            self.reverse_dependencies[dep].append(node.id)

    # Identify inner nodes (targets of map/loop)
    self.inner_nodes = set()
    for node in workflow_definition.nodes:
        if node.type == "map":
            self.inner_nodes.add(node.node)
        elif node.type == "loop":
            self.inner_nodes.add(node.node)
```

### Graph Validation

The executor validates the DAG structure:

```python
def validate_dag(self) -> List[str]:
    errors = []

    # Check for cycles
    if self._has_cycles():
        errors.append("Workflow DAG contains cycles")

    # Check for invalid dependencies
    for node_id, deps in self.dependencies.items():
        for dep in deps:
            if dep not in self.nodes:
                errors.append(f"Node '{node_id}' depends on non-existent node '{dep}'")

    # Check for unreachable nodes
    reachable = self._get_reachable_nodes()
    for node_id in self.nodes:
        if node_id not in reachable and node_id not in self.inner_nodes:
            errors.append(f"Node '{node_id}' is unreachable")

    return errors

def _has_cycles(self) -> bool:
    """Detect cycles using depth-first search."""
    visited = set()
    rec_stack = set()

    def dfs(node_id):
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

### Main Execution Loop

The `execute_workflow` method is the main execution loop:

```python
async def execute_workflow(self, workflow_state, workflow_context):
    while True:
        # Get next nodes to execute
        next_nodes = self.get_next_nodes(workflow_state)

        if not next_nodes:
            # Check if workflow is complete
            if len(workflow_state.completed_nodes) == len(self.nodes):
                await self.host.finalize_workflow_success(workflow_context)
                return

            # Check if workflow is stuck
            if not workflow_state.pending_nodes and not workflow_state.active_branches:
                # Finished execution path (some nodes may be skipped)
                await self.host.finalize_workflow_success(workflow_context)
                return

            # Wait for pending nodes to complete
            return  # Execution resumes on node completion

        # Execute next nodes
        for node_id in next_nodes:
            await self.execute_node(node_id, workflow_state, workflow_context)

            # Track pending if not completed synchronously
            if node_id not in workflow_state.completed_nodes:
                workflow_state.pending_nodes.append(node_id)

        # Persist state
        await self.host._update_workflow_state(workflow_context, workflow_state)
```

### Determining Next Nodes

```python
def get_next_nodes(self, workflow_state) -> List[str]:
    """Get nodes that are ready to execute."""
    ready = []

    for node_id, deps in self.dependencies.items():
        # Skip already completed or pending nodes
        if node_id in workflow_state.completed_nodes:
            continue
        if node_id in workflow_state.pending_nodes:
            continue
        # Skip nodes marked as skipped
        if node_id in workflow_state.skipped_nodes:
            continue
        # Skip inner nodes (handled by their parent map/loop)
        if node_id in self.inner_nodes:
            continue

        # Check if all dependencies are satisfied
        deps_satisfied = all(
            dep in workflow_state.completed_nodes or dep in workflow_state.skipped_nodes
            for dep in deps
        )

        if deps_satisfied:
            ready.append(node_id)

    return ready

def get_initial_nodes(self) -> List[str]:
    """Get nodes with no dependencies."""
    return [
        node_id for node_id, deps in self.dependencies.items()
        if not deps and node_id not in self.inner_nodes
    ]
```

---

## Node Type Implementations

### Agent Node

**Execution flow:**

```python
async def _execute_agent_node(self, node, workflow_state, workflow_context, sub_task_id):
    # Check 'when' clause if present (Argo-style conditional)
    if node.when:
        should_execute = evaluate_condition(node.when, workflow_state)
        if not should_execute:
            # Mark as skipped
            workflow_state.skipped_nodes[node.id] = f"when_clause_false: {node.when}"
            workflow_state.completed_nodes[node.id] = "SKIPPED_BY_WHEN"
            workflow_state.node_outputs[node.id] = {
                "output": None, "skipped": True, "skip_reason": "when_clause_false"
            }

            # Publish skipped event
            result_data = WorkflowNodeExecutionResultData(
                node_id=node.id,
                status="skipped",
            )
            await self.host.publish_workflow_event(workflow_context, result_data)

            # Continue workflow
            await self.execute_workflow(workflow_state, workflow_context)
            return

    # Invoke agent
    await self.host.agent_caller.call_agent(node, workflow_state, workflow_context, sub_task_id)
```

### Conditional Node

**Execution flow:**

```python
async def _execute_conditional_node(self, node, workflow_state, workflow_context):
    # Evaluate condition
    result = evaluate_condition(node.condition, workflow_state)

    # Select branch
    next_node_id = node.true_branch if result else node.false_branch

    # Mark conditional as complete
    workflow_state.completed_nodes[node.id] = "conditional_evaluated"
    workflow_state.node_outputs[node.id] = {
        "output": {"condition_result": result, "condition": node.condition}
    }

    # Skip the untaken branch
    untaken_node_id = node.false_branch if result else node.true_branch
    if untaken_node_id:
        await self._skip_branch(untaken_node_id, workflow_state)

    # Continue execution
    await self.execute_workflow(workflow_state, workflow_context)
```

**Branch skipping:**

```python
async def _skip_branch(self, node_id, workflow_state):
    """Recursively skip a branch starting from node_id."""
    if node_id in workflow_state.skipped_nodes:
        return
    if node_id in workflow_state.completed_nodes:
        return

    workflow_state.skipped_nodes[node_id] = "branch_not_taken"

    # Recursively skip dependents
    for dependent_id in self.reverse_dependencies.get(node_id, []):
        # Only skip if ALL dependencies lead to skipped nodes
        all_deps_skipped = all(
            dep in workflow_state.skipped_nodes
            for dep in self.dependencies.get(dependent_id, [])
        )
        if all_deps_skipped:
            await self._skip_branch(dependent_id, workflow_state)
```

### Switch Node

**Execution flow:**

```python
async def _execute_switch_node(self, node, workflow_state, workflow_context):
    selected_branch = None

    # Evaluate cases in order, first match wins
    for i, case in enumerate(node.cases):
        result = evaluate_condition(case.condition, workflow_state)
        if result:
            selected_branch = case.node
            break

    # Use default if no case matched
    if selected_branch is None and node.default:
        selected_branch = node.default

    # Mark switch as complete
    workflow_state.completed_nodes[node.id] = "switch_evaluated"

    # Skip all non-selected branches
    all_branches = [case.node for case in node.cases]
    if node.default:
        all_branches.append(node.default)

    for branch_id in all_branches:
        if branch_id != selected_branch:
            await self._skip_branch(branch_id, workflow_state)

    await self.execute_workflow(workflow_state, workflow_context)
```

### Join Node

**Execution flow:**

```python
async def _execute_join_node(self, node, workflow_state, workflow_context):
    # Initialize join tracking
    if node.id not in workflow_state.join_completion:
        workflow_state.join_completion[node.id] = {"completed": [], "results": {}}

    join_state = workflow_state.join_completion[node.id]

    # Check which wait_for nodes have completed
    for wait_id in node.wait_for:
        if wait_id in workflow_state.completed_nodes:
            if wait_id not in join_state["completed"]:
                join_state["completed"].append(wait_id)
                if wait_id in workflow_state.node_outputs:
                    join_state["results"][wait_id] = workflow_state.node_outputs[wait_id].get("output")

    completed_count = len(join_state["completed"])
    total_count = len(node.wait_for)

    # Check if join condition is satisfied
    is_ready = False
    if node.strategy == "all":
        is_ready = completed_count == total_count
    elif node.strategy == "any":
        is_ready = completed_count >= 1
    elif node.strategy == "n_of_m":
        is_ready = completed_count >= node.n

    if is_ready:
        # Mark join as complete
        workflow_state.completed_nodes[node.id] = "join_completed"
        workflow_state.node_outputs[node.id] = {"output": join_state["results"]}

        await self.execute_workflow(workflow_state, workflow_context)
```

### Map Node

The map node executes a target node for each item in an array. Items are processed with optional concurrency control.

### Loop Node

The loop node repeatedly executes a target node until a condition becomes false or `max_iterations` is reached.

---

## Template Expression Resolution

**Location:** `src/solace_agent_mesh/workflow/dag_executor.py`

Template expressions enable data flow between nodes using `{{path.to.value}}` syntax.

### Resolution Logic

```python
def resolve_value(self, value: Any, workflow_state: WorkflowExecutionState) -> Any:
    """Resolve a value, handling templates and operators."""
    if isinstance(value, str):
        return self._resolve_template(value, workflow_state)
    elif isinstance(value, dict):
        # Check for operators
        if "coalesce" in value:
            return self._resolve_coalesce(value["coalesce"], workflow_state)
        elif "concat" in value:
            return self._resolve_concat(value["concat"], workflow_state)
        else:
            # Recursively resolve dict values
            return {k: self.resolve_value(v, workflow_state) for k, v in value.items()}
    elif isinstance(value, list):
        return [self.resolve_value(v, workflow_state) for v in value]
    else:
        return value

def _resolve_template(self, template: str, workflow_state: WorkflowExecutionState) -> Any:
    """Resolve {{...}} template expressions."""
    # Check if entire string is a single template
    match = re.fullmatch(r'\{\{(.+?)\}\}', template.strip())
    if match:
        return self._resolve_path(match.group(1).strip(), workflow_state)

    # Otherwise, do string substitution
    def replace_match(m):
        resolved = self._resolve_path(m.group(1).strip(), workflow_state)
        return str(resolved) if resolved is not None else ""

    return re.sub(r'\{\{(.+?)\}\}', replace_match, template)

def _resolve_path(self, path: str, workflow_state: WorkflowExecutionState) -> Any:
    """Resolve a dot-separated path like 'node_id.output.field'."""
    parts = path.split(".")

    # Handle workflow input
    if parts[0] == "workflow" and parts[1] == "input":
        data = workflow_state.node_outputs.get("workflow_input", {}).get("output", {})
        parts = parts[2:]
    # Handle map item
    elif parts[0] == "_map_item":
        data = workflow_state.node_outputs.get("_map_item", {}).get("output")
        parts = parts[1:]
    # Handle node output
    else:
        node_id = parts[0]
        if node_id not in workflow_state.node_outputs:
            return None
        data = workflow_state.node_outputs[node_id]
        parts = parts[1:]

    # Navigate remaining path
    for part in parts:
        if isinstance(data, dict) and part in data:
            data = data[part]
        else:
            return None

    return data
```

### Operators

**Coalesce**: Returns the first non-null value

```python
def _resolve_coalesce(self, values: List[Any], workflow_state) -> Any:
    """Return first non-null resolved value."""
    for value in values:
        resolved = self.resolve_value(value, workflow_state)
        if resolved is not None:
            return resolved
    return None
```

Essential for conditional workflows where only one branch executes:
```yaml
output_mapping:
  status:
    coalesce:
      - "{{manual_review.output.status}}"
      - "{{auto_approve.output.status}}"
```

**Concat**: Joins strings or arrays

```python
def _resolve_concat(self, values: List[Any], workflow_state) -> Any:
    """Concatenate resolved values."""
    resolved = [self.resolve_value(v, workflow_state) for v in values]

    # If all are strings, join as string
    if all(isinstance(v, str) for v in resolved):
        return "".join(resolved)
    # If any are arrays, flatten and concatenate
    result = []
    for v in resolved:
        if isinstance(v, list):
            result.extend(v)
        else:
            result.append(v)
    return result
```

---

## Conditional Expression Evaluation

**Location:** `src/solace_agent_mesh/workflow/flow_control/conditional.py`

Conditional expressions are evaluated using `simpleeval` for safe Python expression evaluation.

### Argo Compatibility

Template aliases transform Argo syntax to SAM syntax:

```python
TEMPLATE_ALIASES = {
    "{{item}}": "{{_map_item}}",           # Argo loop variable
    "{{item.": "{{_map_item.",
    "workflow.parameters.": "workflow.input.",  # Argo input syntax
}

def _apply_template_aliases(expression: str) -> str:
    result = expression
    for alias, target in TEMPLATE_ALIASES.items():
        result = result.replace(alias, target)
    return result
```

### Evaluation

```python
def evaluate_condition(condition_expr: str, workflow_state: WorkflowExecutionState) -> bool:
    # Apply template aliases
    condition_expr = _apply_template_aliases(condition_expr)

    # Build context from completed nodes
    context = {}
    for node_id, output_data in workflow_state.node_outputs.items():
        context[node_id] = {"output": output_data.get("output")}

    functions = {"true": True, "false": False, "null": None}

    # Replace {{...}} patterns with resolved values
    def replace_match(match):
        path = match.group(1).strip()
        parts = path.split(".")

        # Navigate path in workflow state
        if parts[0] == "workflow" and parts[1] == "input":
            data = workflow_state.node_outputs["workflow_input"]["output"]
            parts = parts[2:]
        else:
            node_id = parts[0]
            data = workflow_state.node_outputs[node_id]
            parts = parts[1:]

        for part in parts:
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                return "None"

        return str(data)

    clean_expr = re.sub(r"\{\{(.+?)\}\}", replace_match, condition_expr)

    result = simple_eval(clean_expr, names=context, functions=functions)
    return bool(result)
```

---

## Execution State Management

**Location:** `src/solace_agent_mesh/workflow/workflow_execution_context.py`

### WorkflowExecutionState

Tracks node execution progress as a Pydantic model (serializable to JSON):

```python
class WorkflowExecutionState(BaseModel):
    # Identification
    workflow_name: str
    execution_id: str
    start_time: datetime

    # Node tracking
    current_node_id: Optional[str] = None
    completed_nodes: Dict[str, str] = Field(default_factory=dict)  # node_id -> artifact_name
    pending_nodes: List[str] = Field(default_factory=list)
    skipped_nodes: Dict[str, str] = Field(default_factory=dict)    # node_id -> reason

    # Fork/join tracking
    active_branches: Dict[str, List[Dict]] = Field(default_factory=dict)
    join_completion: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Loop tracking
    loop_iterations: Dict[str, int] = Field(default_factory=dict)

    # Retry tracking
    retry_counts: Dict[str, int] = Field(default_factory=dict)

    # Error tracking
    error_state: Optional[Dict[str, Any]] = None

    # Cached node outputs for value resolution
    node_outputs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### WorkflowExecutionContext

Tracks a single workflow execution (not serialized):

```python
class WorkflowExecutionContext:
    def __init__(self, workflow_task_id: str, a2a_context: Dict):
        self.workflow_task_id = workflow_task_id
        self.a2a_context = a2a_context
        self.workflow_state: Optional[WorkflowExecutionState] = None

        # Sub-task tracking
        self.sub_task_to_node: Dict[str, str] = {}  # sub_task_id -> node_id
        self.node_to_sub_task: Dict[str, str] = {}  # node_id -> sub_task_id
        self.lock = threading.Lock()
        self.cancellation_event = threading.Event()

    def track_agent_call(self, node_id: str, sub_task_id: str):
        """Track correlation between node and sub-task."""
        with self.lock:
            self.sub_task_to_node[sub_task_id] = node_id
            self.node_to_sub_task[node_id] = sub_task_id

    def get_node_id_for_sub_task(self, sub_task_id: str) -> Optional[str]:
        with self.lock:
            return self.sub_task_to_node.get(sub_task_id)

    def cancel(self):
        """Signal cancellation."""
        self.cancellation_event.set()

    def is_cancelled(self) -> bool:
        return self.cancellation_event.is_set()
```

---

## Error Handling and Recovery

### Node Failure

When a node fails, the error is captured in workflow state:

```python
except Exception as e:
    workflow_state.error_state = {
        "failed_node_id": node_id,
        "failure_reason": "execution_error",
        "error_message": str(e),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    raise WorkflowNodeFailureError(node_id, str(e)) from e
```

### Retry Strategy

Nodes can specify retry behavior:

```yaml
retryStrategy:
  limit: 3
  retryPolicy: "OnFailure"
  backoff:
    duration: "1s"
    factor: 2
    maxDuration: "30s"
```

The executor tracks retry counts per node:

```python
if node.retry_strategy and workflow_state.retry_counts.get(node.id, 0) < node.retry_strategy.limit:
    workflow_state.retry_counts[node.id] = workflow_state.retry_counts.get(node.id, 0) + 1
    # Re-queue node for execution
```

### Exit Handlers

Workflows can specify exit handlers for cleanup:

```yaml
onExit:
  always: notification_node      # Runs regardless of outcome
  onSuccess: success_handler     # Runs only on success
  onFailure: failure_handler     # Runs only on failure
```

Or simple form:
```yaml
onExit: cleanup_node
```

---

## Workflow Definition Schema

### Complete Structure

```yaml
workflow:
  description: string     # Required: Human-readable description

  input_schema:           # Optional: JSON Schema for workflow input
    type: object
    properties: {}
    required: []

  output_schema:          # Optional: JSON Schema for workflow output
    type: object
    properties: {}

  nodes:                  # Required: List of workflow nodes
    - id: string
      type: string
      # ... node-specific fields

  output_mapping:         # Required: Map node outputs to workflow output
    field_name: "{{node_id.output.field}}"

  skills:                 # Optional: Skills for agent card
    - id: string
      name: string
      description: string

  # Argo-compatible fields
  onExit: string | object # Optional: Exit handler
  failFast: boolean       # Optional: Stop on failure (default: true)
  retryStrategy: object   # Optional: Default retry strategy
```

### Node Type Schemas

**Agent Node:**
```yaml
- id: string
  type: agent
  agent_name: string
  depends_on: [string]
  input: object
  input_schema_override: object
  output_schema_override: object
  when: string
  retryStrategy: object
  timeout: string
```

**Conditional Node:**
```yaml
- id: string
  type: conditional
  depends_on: [string]
  condition: string
  true_branch: string
  false_branch: string
```

**Switch Node:**
```yaml
- id: string
  type: switch
  depends_on: [string]
  cases:
    - when: string
      then: string
  default: string
```

**Map Node:**
```yaml
- id: string
  type: map
  depends_on: [string]
  items: string | object
  node: string
  concurrency_limit: integer
  max_items: integer
```

**Fork Node:**
```yaml
- id: string
  type: fork
  depends_on: [string]
  branches:
    - id: string
      agent_name: string
      input: object
      output_key: string
  fail_fast: boolean
```

**Join Node:**
```yaml
- id: string
  type: join
  depends_on: [string]
  wait_for: [string]
  strategy: "all" | "any" | "n_of_m"
  n: integer
```

**Loop Node:**
```yaml
- id: string
  type: loop
  depends_on: [string]
  node: string
  condition: string
  max_iterations: integer
  delay: string
```

---

## Implementation Files Reference

| Component | File | Purpose |
|-----------|------|---------|
| Workflow Executor | `src/solace_agent_mesh/workflow/component.py` | Execution engine, Agent Card, A2A handling |
| DAG Executor | `src/solace_agent_mesh/workflow/dag_executor.py` | Node execution logic, dependency resolution |
| Node Definitions | `src/solace_agent_mesh/workflow/app.py` | Pydantic models for nodes and workflow |
| Agent Caller | `src/solace_agent_mesh/workflow/agent_caller.py` | A2A dispatch, input resolution |
| Execution Context | `src/solace_agent_mesh/workflow/workflow_execution_context.py` | State management |
| Conditional Eval | `src/solace_agent_mesh/workflow/flow_control/conditional.py` | Expression evaluation |
| Node Handler | `src/solace_agent_mesh/agent/sac/workflow_support/handler.py` | Agent-side support |
| Schema Validator | `src/solace_agent_mesh/agent/sac/workflow_support/validator.py` | JSON Schema validation |
| Workflow Tool | `src/solace_agent_mesh/agent/tools/workflow_tool.py` | Tool for invoking workflows |
| Data Models | `src/solace_agent_mesh/common/data_parts.py` | Protocol message models |
| Constants | `src/solace_agent_mesh/common/constants.py` | Extension URIs |
| Agent Card Utils | `src/solace_agent_mesh/common/agent_card_utils.py` | Schema extraction from cards |
