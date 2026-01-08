# Workflows - Component Architecture Overview

This document provides an architectural overview of the Workflows feature, explaining how each component fits into the bigger picture and how they interact with each other.

## Table of Contents

1. [Introduction](#introduction)
2. [System Architecture](#system-architecture)
3. [Data Flow](#data-flow)
4. [Component Deep Dives](#component-deep-dives)
5. [Integration Points](#integration-points)

---

## Introduction

### What are Workflows?

Workflows enable users to define deterministic, structured execution flows as an alternative to purely LLM-driven orchestration. Unlike traditional agent-to-agent orchestration where an orchestrator agent decides what to do next based on LLM reasoning, workflows follow a predefined DAG (Directed Acyclic Graph) structure.

### Why Workflows?

| Aspect | Agent Orchestration | Workflows |
|--------|--------------------|-----------------------|
| Control Flow | LLM decides next steps | Predefined DAG structure |
| Predictability | Variable (depends on LLM) | Deterministic |
| Cost | Higher (multiple LLM calls for routing) | Lower (no routing LLM calls) |
| Flexibility | High (can adapt dynamically) | Moderate (fixed structure) |
| Debugging | Harder (non-deterministic) | Easier (predictable flow) |

Workflows are ideal for:
- Repeatable business processes
- Compliance-sensitive workflows
- Cost-sensitive batch operations
- Scenarios requiring audit trails

---

## System Architecture

### High-Level Architecture

![High-Level Architecture](workflows-architecture.svg)

<details>
<summary>Text version</summary>

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User/Client                                    │
│                    (WebUI, CLI, External Systems)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ A2A Protocol (via Solace Broker)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WorkflowExecutorComponent                            │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────────────┐│
│  │ Event Handlers  │──►│  DAG Executor   │──►│     Agent Caller            ││
│  │ (Protocol)      │   │  (Orchestration)│   │     (A2A Invocation)        ││
│  └─────────────────┘   └─────────────────┘   └─────────────────────────────┘│
│                                │                        │                   │
│                                ▼                        │                   │
│                       ┌─────────────────┐               │                   │
│                       │ Execution       │               │                   │
│                       │ Context/State   │               │                   │
│                       └─────────────────┘               │                   │
└───────────────────────────────┬─────────────────────────┼───────────────────┘
                                │                         │
                                │ A2A Status Events       │ A2A Messages
                                │                         ▼
                                │     ┌───────────────────────────────────────┐
                                │     │                 Agents                │
                                │     │  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
                                │     │  │ Agent A │ │ Agent B │ │ Agent C │  │
                                │     │  └─────────┘ └─────────┘ └─────────┘  │
                                │     └───────────────────┬───────────────────┘
                                │                         │
                                │                         │ A2A Status Events
                                ▼                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Frontend (WebUI)                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────────────┐ │
│  │ Task Visualizer │   │  Layout Engine  │   │     FlowChart               │ │
│  │ Processor       │──►│  (layoutEngine) │──►│     Components              │ │
│  └─────────────────┘   └─────────────────┘   └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

</details>

### Communication Patterns

All communication between components uses the **A2A (Agent-to-Agent) Protocol** over Solace messaging:

1. **Task Requests**: Client → Workflow → Agents
2. **Status Updates**: Agents → Workflow → Client (via SSE)
3. **Node Results**: Agents → Workflow (via correlation IDs)

---

## Data Flow

### Complete Request Flow

```
1. INPUT EVENT
   Workflow receives an A2A SendMessageRequest on its topic.
   This can originate from:
   - An event-based gateway (e.g., event-mesh-gateway)
   - An agent invoking the workflow as a tool
   - Another workflow calling this workflow as a nested step

2. WORKFLOW RECEIVES
   WorkflowExecutorComponent receives on sam/{namespace}/agent/{workflow_name}/request

3. EXECUTION STARTS
   - Parse input from message
   - Create WorkflowExecutionContext
   - Publish WorkflowExecutionStartData event

4. DAG EXECUTION
   For each ready node:
   a. Publish WorkflowNodeExecutionStartData
   b. For agent nodes: Call AgentCaller.call_agent()
   c. Wait for response (via correlation ID)
   d. On completion: Update state, check dependencies
   e. Publish WorkflowNodeExecutionResultData

5. AGENT EXECUTION (for each agent node)
   a. Agent receives StructuredInvocationRequest in message
   b. StructuredInvocationHandler.execute_structured_invocation()
   c. Validate input, run agent, validate output
   d. Return StructuredInvocationResult

6. WORKFLOW COMPLETES
   - Evaluate output_mapping
   - Publish final result
   - Run exit handlers if configured

7. OUTPUT EVENTS
   Results are delivered back to the caller:
   - Gateway clients receive status events in real-time (e.g., via SSE)
   - Calling agents receive the workflow result as a tool response
   - Parent workflows receive the result for template resolution
```

### Template Resolution Example

```yaml
# Workflow Definition
nodes:
  - id: fetch_data
    type: agent
    agent_name: DataFetcher
    input:
      query: "{{workflow.input.search_term}}"

  - id: process
    type: agent
    agent_name: Processor
    depends_on: [fetch_data]
    input:
      data: "{{fetch_data.output.results}}"
      count: "{{fetch_data.output.total}}"
```

**At Runtime:**
```python
# workflow.input = {"search_term": "AI agents"}
# After fetch_data completes:
# fetch_data.output = {"results": [...], "total": 42}

# process node input resolves to:
{
    "data": [...],   # from fetch_data.output.results
    "count": 42      # from fetch_data.output.total
}
```

---

## Component Deep Dives

### 1. Common/Shared Components

**Location:** `src/solace_agent_mesh/common/`

#### Purpose
Foundation layer providing shared data structures and utilities used across all workflow components.

#### Key Files

| File | Purpose |
|------|---------|
| `data_parts.py` | Pydantic models for workflow messages |
| `constants.py` | Workflow-related constants |
| `a2a/types.py` | A2A type extensions |
| `agent_card_utils.py` | Utilities for extracting schemas from agent cards |

#### Data Models

```python
# Structured invocation types (generic agent-as-function pattern)
StructuredInvocationRequest  # Caller → Agent: "Execute with schema validation"
StructuredInvocationResult   # Agent → Caller: "Here's the validated result"

# Workflow-specific visualization types
WorkflowExecutionStartData   # Workflow → Client: "Execution started"
WorkflowNodeExecutionStartData  # Workflow → Client: "Node started"
WorkflowNodeExecutionResultData # Workflow → Client: "Node completed"
WorkflowMapProgressData      # Workflow → Client: "Map iteration X of Y"
```

#### Role in Architecture
These models define the **contract** between components. They ensure type safety and validation across the system boundary.

Note: `StructuredInvocationRequest/Result` are generic types usable by any programmatic caller (workflows, gateways, APIs). The `WorkflowNode*` types are workflow-specific visualization events.

---

### 2. Workflow Definition Models

**Location:** `src/solace_agent_mesh/workflow/app.py`

#### Purpose
Define the YAML schema for workflow definitions using Pydantic models. This is the "language" users write to define workflows.

#### Node Types

```
WorkflowNode (base)
    ├── AgentNode       - Invoke an agent
    ├── ConditionalNode - Binary if/else branching
    ├── SwitchNode      - Multi-way branching (like switch/case)
    ├── LoopNode        - While-loop iteration
    └── MapNode         - Parallel for-each iteration
```

#### Workflow Structure

```yaml
workflow:
  description: "Human-readable description"
  input_schema: { ... }      # JSON Schema for workflow input
  output_schema: { ... }     # JSON Schema for workflow output

  nodes:
    - id: step1
      type: agent
      agent_name: "AgentA"
      input: { key: "{{workflow.input.value}}" }

    - id: branch
      type: conditional
      depends_on: [step1]
      condition: "'{{step1.output.status}}' == 'success'"
      true_branch: step2a
      false_branch: step2b

  output_mapping:
    result: "{{step1.output.data}}"
```

#### Key Features

- **Argo-compatible syntax**: Familiar to users of Argo Workflows
- **Template expressions**: `{{node.output.field}}` for data flow
- **Schema validation**: JSON Schema for input/output validation
- **DAG validation**: Ensures no cycles, valid references

#### Role in Architecture
The models serve as the **configuration layer** - they're parsed at startup and drive the DAG executor's behavior.

---

### 3. Workflow Runtime Components

**Location:** `src/solace_agent_mesh/workflow/`

#### 3.1 WorkflowExecutorComponent (`component.py`)

**Purpose:** Main orchestrator component that coordinates workflow execution.

**Responsibilities:**
- Lifecycle management (startup, shutdown)
- Message routing (request handling, response correlation)
- Agent card generation (workflows appear as agents)
- Event publishing (status updates to frontend)
- Workflow state management

**Key Interactions:**
```
Incoming A2A Request
        │
        ▼
┌───────────────────┐
│ Event Handlers    │  ← handle_task_request()
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ DAG Executor      │  ← execute_workflow()
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Agent Caller      │  ← call_agent()
└───────────────────┘
        │
        ▼
A2A Message to Agent
```

#### 3.2 DAGExecutor (`dag_executor.py`)

**Purpose:** Execute the workflow DAG by managing node dependencies and execution order.

**Key Algorithms:**

1. **Dependency Graph Building**
   ```python
   # For each node, track what it depends on
   dependencies = {
       "step2": ["step1"],
       "step3": ["step2"],
       "branch": ["step1"],
   }
   ```

2. **Execution Flow**
   ```
   1. Start with nodes that have no dependencies
   2. When a node completes, check reverse dependencies
   3. If all dependencies satisfied, execute next node(s)
   4. Handle branching (conditional/switch) by marking skipped paths
   5. Handle iteration (loop/map) with special completion logic
   ```

3. **Node Execution Dispatch**
   ```python
   match node.type:
       case "agent":      await _execute_agent_node(...)
       case "conditional": await _execute_conditional_node(...)
       case "switch":     await _execute_switch_node(...)
       case "loop":       await _execute_loop_node(...)
       case "map":        await _execute_map_node(...)
   ```

**State Machine:**
```
PENDING → RUNNING → COMPLETED
                 ↘ FAILED
                 ↘ SKIPPED (for unexecuted branches)
```

#### 3.3 AgentCaller (`agent_caller.py`)

**Purpose:** Handle A2A communication with agents.

**Responsibilities:**
- Resolve template expressions in node input
- Construct A2A messages with workflow context
- Manage sub-task correlation IDs
- Handle artifact creation for input data

**Template Resolution:**
```python
# Input definition
input:
  amount: "{{workflow.input.order.amount}}"
  previous: "{{step1.output.result}}"

# Resolved at runtime
input:
  amount: 150
  previous: {"status": "processed"}
```

#### 3.4 WorkflowExecutionContext (`workflow_execution_context.py`)

**Purpose:** Track state for a single workflow execution.

**Tracked State:**
- Execution ID and task ID
- Node states (pending, running, completed, failed, skipped)
- Node outputs (results from completed nodes)
- Sub-task correlations (which agent call maps to which node)
- Inherited branch info (for conditional nodes)

#### 3.5 Conditional Evaluator (`flow_control/conditional.py`)

**Purpose:** Safely evaluate condition expressions.

**Technology:** Uses `simpleeval` for sandboxed expression evaluation.

```python
# Supported expressions
"'{{node.output.status}}' == 'success'"
"{{node.output.count}} > 10"
"'error' in '{{node.output.message}}'"
```

---

### 4. Structured Invocation Support

**Location:** `src/solace_agent_mesh/agent/sac/structured_invocation/`

#### Purpose
Enable agents to be invoked with schema-validated input/output, functioning as a "structured function call" pattern. Used by workflows and other programmatic callers that need predictable, validated responses.

#### 4.1 StructuredInvocationHandler (`handler.py`)

**Responsibilities:**
- Detect structured invocation context in incoming messages
- Validate input against schema
- Execute agent with structured prompts
- Validate output against schema (with retry logic)
- Format result as `StructuredInvocationResult`

**Execution Flow:**
```
Incoming A2A Message
        │
        ▼
┌───────────────────────┐
│ Extract Structured    │  ← Is this a structured invocation?
│ Invocation Context    │     (check for StructuredInvocationRequest)
└───────────────────────┘
        │ Yes
        ▼
┌───────────────────────┐
│ Validate Input        │  ← Against input_schema
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Execute ADK Agent     │  ← With structured prompt
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Extract & Validate    │  ← Parse result embed, validate output
│ Output                │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Send Result           │  ← StructuredInvocationResult
└───────────────────────┘
```

**Result Embed Pattern:**
Agents signal completion using a special embed in their output:
```
«result:artifact=output.json status=success»
```

#### 4.2 Schema Validator (`validator.py`)

Simple JSON Schema validation using `jsonschema` library.

---

### 5. Workflow Tool for Agents

**Location:** `src/solace_agent_mesh/agent/tools/workflow_tool.py`

#### Purpose
Allow agents to invoke workflows as tools, enabling LLM-driven agents to call prescriptive workflows.

#### How It Works

1. **Discovery**: When workflows publish agent cards, the tool creates dynamic tool definitions
2. **Invocation**: Agent LLM decides to call workflow tool with parameters
3. **Execution**: Tool sends A2A request to workflow, waits for completion
4. **Result**: Tool returns workflow output to agent

```python
class WorkflowAgentTool(BaseTool):
    """
    Dynamically generated tool for each discovered workflow.
    Supports two invocation modes:
    1. Parameter Mode: Pass arguments directly
    2. Artifact Mode: Pass reference to input artifact
    """
```

#### Role in Architecture
This creates a **bridge** between agent-driven orchestration and prescriptive workflows, allowing the best of both worlds.

---

### 6. Frontend Visualization

**Location:** `client/webui/frontend/src/lib/components/activities/FlowChart/`

#### Purpose
Render real-time workflow execution visualization in the WebUI.

#### Component Hierarchy

```
FlowChartPanel
    │
    ├── WorkflowRenderer
    │       │
    │       ├── EdgeLayer (connections)
    │       │
    │       └── Node Components
    │               ├── AgentNode
    │               ├── UserNode
    │               ├── ToolNode
    │               ├── LLMNode
    │               ├── ConditionalNode
    │               ├── SwitchNode
    │               ├── LoopNode
    │               ├── MapNode
    │               └── WorkflowGroup (containers)
    │
    └── NodeDetailsCard (sidebar details)
```

#### Layout Engine (`utils/layoutEngine.ts`)

**Purpose:** Transform execution events into a visual tree structure.

**Process:**
```
VisualizerStep[] (events)
        │
        ▼
┌───────────────────────┐
│ processSteps()        │  ← Build tree from events
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ calculateLayout()     │  ← Assign positions/dimensions
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ calculateEdges()      │  ← Compute connections
└───────────────────────┘
        │
        ▼
LayoutResult { nodes, edges, totalWidth, totalHeight }
```

**Key Challenges:**
- Handling nested agents (workflows calling agents calling tools)
- Parallel execution (map iterations, concurrent branches)
- Dynamic updates (nodes completing in real-time)
- Collapse/expand for complex workflows

#### Node Components

Each node type has a dedicated React component:

| Component | Purpose | Visual Style |
|-----------|---------|--------------|
| `AgentNode` | Agent invocation | Card with header |
| `WorkflowGroup` | Container for nested items | Bordered group |
| `ConditionalNode` | If/else decision | Diamond shape |
| `SwitchNode` | Multi-way decision | Diamond with multiple outputs |
| `MapNode` | Parallel iteration | Container with iteration count |
| `LoopNode` | While loop | Container with iteration info |

#### Node Details Card

Sidebar component showing detailed information about selected node:
- Input/output data
- Timing information
- Error details
- Artifact references

---

### 7. Supporting Components

#### 7.1 Task Visualizer Processor

**Location:** `client/webui/frontend/src/lib/components/activities/taskVisualizerProcessor.ts`

**Purpose:** Transform raw A2A events into `VisualizerStep` objects for the layout engine.

**Event Types Processed:**
- `USER_REQUEST` - Initial user input
- `AGENT_START/END` - Agent lifecycle
- `AGENT_TOOL_INVOCATION_START/RESULT` - Tool calls
- `AGENT_LLM_CALL/RESPONSE` - LLM interactions
- `WORKFLOW_EXECUTION_START` - Workflow begins
- `WORKFLOW_NODE_EXECUTION_START/RESULT` - Node lifecycle
- `WORKFLOW_MAP_PROGRESS` - Map iteration updates

#### 7.2 Gateway Extensions

**Location:** `src/solace_agent_mesh/gateway/http_sse/component.py`

Minor modifications to forward workflow-specific events to clients via SSE.

---

## Integration Points

### With Existing SAM Components

| Component | Integration |
|-----------|-------------|
| SamAgentComponent | Extended with StructuredInvocationHandler |
| Agent Registry | Workflows register as agents |
| Artifact Service | Input/output stored as artifacts |
| Session Service | Workflow sessions for artifact scoping |
| A2A Protocol | Standard message format with workflow extensions |

### Extension Points

1. **Custom Node Types**: Add new node types in `app.py` and `dag_executor.py`
2. **Custom Validators**: Extend schema validation in `validator.py`
3. **Custom Visualizations**: Add node components in `nodes/`
4. **Exit Handlers**: Define cleanup/notification logic

---

## Summary

The Workflows feature introduces a layered architecture:

1. **Foundation Layer** (data_parts, constants) - Shared contracts
2. **Definition Layer** (app.py) - YAML schema and validation
3. **Runtime Layer** (component, dag_executor, agent_caller) - Execution engine
4. **Agent Layer** (structured_invocation) - Agent participation
5. **Tool Layer** (workflow_tool) - Agent-to-workflow bridge
6. **Visualization Layer** (V2 components) - Real-time UI

Each layer has clear responsibilities and well-defined interfaces, enabling independent development and testing.
