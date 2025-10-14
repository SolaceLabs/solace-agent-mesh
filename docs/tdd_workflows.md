# Technical Design Document: Prescriptive Workflows for SAM

**Version:** 1.0  
**Status:** Draft  
**Author:** SAM Engineering Team  
**Last Updated:** 2025-01-13  
**Related Documents:** [PRD: Prescriptive Workflows](prd_workflows.md)

---

## 1. Overview

### 1.1 Purpose

This Technical Design Document (TDD) provides detailed technical specifications for implementing Prescriptive Workflows in the Solace Agent Mesh (SAM). It bridges the gap between the Product Requirements Document (PRD) and actual implementation by defining:

- Component architecture and interactions
- Data structures and API contracts
- Algorithms for workflow execution and validation
- Embed syntax specifications
- Schema validation approach
- Flow control implementations

### 1.2 Scope

This TDD covers the technical design for:
- **Core Workflow Execution:** WorkflowExecutorComponent, WorkflowApp, DAG execution engine
- **Embed Systems:** Value references (`«value:...»`) and result artifact marking (`«result:...»`)
- **Schema Validation:** Validation at workflow edges, compatibility checking
- **Flow Control:** If/else, case/switch, fork/join, loop nodes
- **State Management:** Workflow execution state persistence
- **Integration:** How workflows integrate with existing SAM components

**Out of Scope:**
- Agent Executor implementation (covered in separate TDD)
- Visual workflow designer
- Advanced error recovery mechanisms
- Workflow versioning system

### 1.3 Key Architectural Principles

1. **Workflows are Agents:** Workflows appear identical to regular agents externally
2. **Data Integrity First:** Critical data never passes through LLM context
3. **Schema-Driven:** All workflow edges validated against schemas
4. **Fail Fast:** Validation errors caught at earliest possible point
5. **Backward Compatible:** No breaking changes to existing SAM functionality
6. **Stateful Execution:** Workflow state persisted for recovery and debugging

---

## 2. System Architecture

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Solace Event Mesh                                              │
│  - {namespace}/a2a/v1/agent/request/{workflow_name}             │
│  - {namespace}/a2a/v1/agent/response/{workflow_name}            │
│  - {namespace}/a2a/v1/agent/status/{workflow_name}              │
│  - {namespace}/a2a/v1/discovery/agentcard                       │
└─────────────────────────────────────────────────────────────────┘
                              ▲  │
                              │  ▼
┌─────────────────────────────────────────────────────────────────┐
│  SAC Process: Workflow Agent                                    │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  WorkflowApp (extends SamAgentApp)                        │ │
│  │  - Validates workflow configuration                       │ │
│  │  - Publishes workflow agent card                          │ │
│  │  - Creates WorkflowExecutorComponent                      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  WorkflowExecutorComponent                                │ │
│  │  - DAG Execution Engine                                   │ │
│  │  - Schema Validator                                       │ │
│  │  - Embed Resolver                                         │ │
│  │  - Flow Control Executor                                  │ │
│  │  - A2A Client                                             │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  ADK Services (Shared)                                    │ │
│  │  - Session Service (state persistence)                    │ │
│  │  - Artifact Service (data storage)                        │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │ Delegates to
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agent Executors / Standalone Agents                            │
│  - ExtractInfoAgent, ValidateInfoAgent, etc.                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

#### WorkflowApp
- Load and validate workflow YAML configuration
- Create WorkflowExecutorComponent instance
- Configure broker subscriptions
- Publish workflow agent card
- Handle graceful shutdown

#### WorkflowExecutorComponent
- Receive A2A task requests
- Execute workflow DAG
- Manage workflow execution state
- Validate schemas at workflow edges
- Delegate to node agents via A2A
- Publish status updates
- Handle errors and retries

#### DAG Execution Engine
- Parse workflow definition into internal DAG representation
- Perform topological sort for execution order
- Track node dependencies
- Execute nodes sequentially or in parallel
- Manage execution state transitions

#### Schema Validator
- Validate node inputs against persona input schemas
- Validate node outputs against persona output schemas
- Check schema compatibility between connected nodes
- Generate clear validation error messages
- Trigger retry logic on validation failures

#### Embed Resolver
- Resolve value references (`«value:artifact:path»`)
- Parse result artifact embeds (`«result:...»`)
- Extract values from artifacts using JSON paths
- Handle resolution errors

#### Flow Control Executor
- Evaluate conditional expressions (if/else, case/switch)
- Coordinate parallel execution (fork/join)
- Manage loop iterations
- Merge outputs from parallel branches

#### A2A Client
- Send A2A SendTask requests to node agents
- Wait for and process responses
- Handle timeouts
- Publish workflow status updates

### 2.3 Integration with Existing SAM Components

**Integration Points:**

1. **SamAgentApp:** WorkflowApp extends SamAgentApp, reusing broker configuration and agent card publishing
2. **ComponentBase:** WorkflowExecutorComponent extends ComponentBase, reusing event handling
3. **ADK Services:** Workflow state stored in session.state, node outputs stored as artifacts
4. **A2A Protocol:** Workflows use standard A2A SendTask/Response messages
5. **Embed System:** New embeds added to existing resolver

**Backward Compatibility:**
- All new functionality is additive
- Workflows are opt-in
- Existing agents unaffected
- No protocol changes required

---

## 3. Embed Specifications

### 3.1 Value Reference Embed

#### Purpose
Enable agents to reference data values without LLM manipulation, ensuring data integrity for critical values like IDs, keys, and structured data.

#### Syntax

```
«value:artifact_name:json_path»
```

**Components:**
- `artifact_name`: Name of the artifact containing the data
- `json_path`: Dot-separated path with optional array indices (e.g., `field.nested[0].value`)

#### Examples

```
«value:customer_info.json:customer_id»
«value:order_data.json:shipping.address.zip_code»
«value:products.json:items[0].sku»
«value:config.json:api.endpoints.production.url»
```

#### Resolution Process

1. **Parse Reference:** Extract artifact name and JSON path
2. **Load Artifact:** Retrieve artifact from artifact service
3. **Parse JSON:** Parse artifact content as JSON
4. **Extract Value:** Navigate JSON path to extract value
5. **Return Value:** Return extracted value for tool execution

#### Error Handling

- **Invalid Syntax:** Clear error message with expected format
- **Artifact Not Found:** List available artifacts
- **Invalid JSON Path:** Show available keys at failed path level
- **Non-JSON Artifact:** Explain value references only work with JSON

#### Integration

Value references are resolved **before** tool execution in the tool wrapper, ensuring the LLM never sees or manipulates the actual values.

### 3.2 Result Artifact Embed

#### Purpose
Enable agents to explicitly mark their output artifact and signal success/failure status.

#### Syntax

```
«result:artifact=name[:version] status=success|failure [message=text]»
```

**Parameters:**
- `artifact`: Name of result artifact (optional version)
- `status`: Either `success` or `failure` (required)
- `message`: Optional message (required for failure, optional for success)

#### Examples

```
# Success with artifact
«result:artifact=customer_info.json status=success»

# Success with message
«result:artifact=analysis.json status=success message=Processed 1000 records»

# Success with specific version
«result:artifact=report.pdf:3 status=success»

# Failure without artifact
«result:status=failure message=Customer validation failed: invalid email»

# Failure with debug artifact
«result:artifact=error_log.txt status=failure message=Processing error»
```

#### Validation Rules

1. **Status Required:** Every result embed must have `status` parameter
2. **Success Requires Artifact:** If `status=success`, `artifact` parameter required
3. **Failure Requires Message:** If `status=failure`, `message` parameter required
4. **Single Result Embed:** Only one result embed allowed per agent response
5. **Artifact Version:** Version optional, defaults to "latest"

#### Processing

1. **Extract Embed:** Find result embed in agent response text
2. **Parse Parameters:** Extract artifact, status, and message
3. **Validate Rules:** Check required parameters present
4. **Handle Status:**
   - **Success:** Load artifact, validate against output schema, pass to next node
   - **Failure:** Skip validation, propagate error (no retry)

---

## 4. Schema Validation System

### 4.1 Schema Storage and Resolution

#### Schema Location

Schemas are stored with agent persona definitions in agent executor configurations:

```yaml
personas:
  - agent_name: "DataAnalyzerAgent"
    input_schema: {...}
    output_schema: {...}
```

#### Schema Discovery

Schemas are discovered via agent cards published to the discovery topic. Each agent card includes the persona's input and output schemas.

#### Schema Caching

Workflow executor maintains a cache of persona schemas:
- Cache populated from agent registry (discovery)
- Cache invalidated when agent cards updated
- Cache used for validation and compatibility checking

### 4.2 Validation Points

Schema validation occurs at workflow edges:

1. **Workflow Input → First Node(s):**
   - Validate workflow input against workflow input schema (if defined)
   - Validate first node input against persona input schema

2. **Node Output → Next Node Input:**
   - Validate node output against persona output schema
   - Validate next node input (after mapping) against persona input schema

3. **Last Node → Workflow Output:**
   - Validate last node output against workflow output schema (if defined)

### 4.3 Validation Algorithm

**Validation Library:** `jsonschema` (Python standard)

**Validation Process:**
1. Load schema from cache
2. Validate data against schema using jsonschema
3. Collect validation errors
4. Format error messages with context
5. Return validation result

**Error Message Format:**
```
Schema validation failed for Node 'extract_info' output:
  - Path 'customer_name': Field is required but missing
  - Path 'email': Expected type 'string', got 'integer'

Expected schema:
{
  "type": "object",
  "properties": {
    "customer_name": {"type": "string"},
    "email": {"type": "string"}
  },
  "required": ["customer_name", "email"]
}

Received data:
{
  "email": 12345
}
```

### 4.4 Retry Logic

**Retry on Validation Failure:**
- Max retries: 3 attempts
- Retry prompt includes validation error
- Agent sees full history plus error message
- Agent can correct output without redoing work

**No Retry on Explicit Failure:**
- If agent returns `status=failure`, no retry
- Explicit failure propagates immediately

### 4.5 Schema Compatibility Checking

**Purpose:** Validate at workflow load time (or first execution) that node outputs are compatible with downstream node inputs.

**Compatibility Rules:**
1. Types must match
2. All target required fields must exist in source
3. Enum constraints must be compatible
4. Nested objects recursively checked

**Compatibility Check Process:**
1. For each workflow edge (node A → node B)
2. Get output schema of node A
3. Get input schema of node B
4. Check compatibility
5. Report errors if incompatible

**Note:** For MVP, compatibility checking happens at runtime (first execution). Future enhancement: check at workflow load time after all persona schemas discovered.

---

## 5. Workflow Execution Engine

### 5.1 DAG Representation

#### Core Data Structures

**NodeConfig:**
- Node ID, type (agent/if/fork/etc.)
- Agent persona name (for agent nodes)
- Input mapping (template expressions)
- Request template (optional, for contextualizing the task)
- Dependencies (depends_on list)
- Timeout configuration
- Resolved schemas (input/output)
- Flow control specific fields (condition, branches, etc.)

**WorkflowConfig:**
- Workflow name, description
- Input/output schemas (optional)
- List of nodes
- Output mapping
- Computed: node map, execution order

**NodeState:**
- Node ID, status (pending/running/completed/failed/skipped)
- Start/end times
- Input/output data
- Error message
- Retry count

**WorkflowExecutionState:**
- Workflow ID, name, status
- Start/end times
- Map of node states
- Current node ID
- Workflow input/output
- Error tracking
- User/session IDs

#### Dependency Graph

The dependency graph is built from node `depends_on` lists and used for:
- Topological sort (execution order)
- Identifying ready nodes (all dependencies completed)
- Detecting cycles (validation)

### 5.2 Execution Algorithm

#### High-Level Flow

1. **Initialize State:** Create workflow execution state, initialize all node states to "pending"
2. **Validate Input:** Validate workflow input against workflow input schema (if defined)
3. **Build Graph:** Create dependency graph from node definitions
4. **Execute Loop:**
   - Get nodes ready to execute (all dependencies completed)
   - Execute ready nodes (potentially in parallel)
   - Mark completed nodes
   - Repeat until all nodes completed or failure
5. **Extract Output:** Extract final output from last node(s)
6. **Validate Output:** Validate workflow output against workflow output schema (if defined)
7. **Finalize:** Mark workflow as completed/failed, persist state

#### Node Execution Lifecycle

```
PENDING → RUNNING → COMPLETED
                 ↓
              FAILED
```

**For Each Node:**
1. **Prepare Input:** Resolve input mapping templates using previous node outputs
2. **Validate Input:** Validate against persona input schema
3. **Save Input Artifact:** Save resolved input as structured artifact
4. **Build Request:** Generate request using request template (or default)
5. **Inject Workflow Prompt:** Add workflow-specific system instructions
6. **Execute:** Delegate to agent via A2A (or execute flow control logic)
7. **Extract Result:** Parse result embed from agent response
8. **Handle Status:**
   - Success: Load artifact, validate output, store for next nodes
   - Failure: Mark node as failed, propagate error
9. **Update State:** Update node state, persist to session storage

#### Parallel Execution

Nodes with no dependencies between them can execute in parallel:
- Identify independent nodes
- Execute concurrently using asyncio.gather
- Wait for all to complete before proceeding

### 5.3 State Management

#### State Storage

Workflow execution state is stored in ADK session storage:
- Location: `session.state.workflow_execution`
- Format: JSON-serializable dict
- Persistence: Follows session service configuration (memory/SQL)

#### State Contents

- Workflow metadata (ID, name, status)
- Node states (all nodes)
- Current execution position
- Input/output data
- Error information
- Timestamps

#### State Recovery

If workflow executor restarts:
1. Load session from session service
2. Extract workflow execution state
3. Resume from current node
4. Re-execute failed nodes if needed

**Note:** For MVP, state recovery is best-effort. Full resume capability is future enhancement.

---

## 6. Flow Control Nodes

### 6.1 If/Else Node

#### Purpose
Conditional branching based on previous node output.

#### Configuration

```yaml
- id: routing
  type: if
  condition: "{{validate_customer.output.is_valid}} == true"
  then:
    - id: create_account
      agent_persona: "CreateAccountAgent"
      request_template: |
        Create a new customer account with the validated information.
        Customer name: {{input.customer_name}}
        Email: {{input.email}}
  else:
    - id: send_rejection
      agent_persona: "NotificationAgent"
      request_template: |
        Send a rejection email to the customer.
        Reason: {{input.error_message}}
```

#### Execution

1. **Evaluate Condition:** Parse condition expression, substitute node outputs, evaluate
2. **Select Branch:** Execute `then` branch if true, `else` branch if false
3. **Execute Branch:** Execute all nodes in selected branch
4. **Skip Other Branch:** Mark other branch nodes as "skipped"

#### Condition Syntax

Conditions reference node outputs by ID:
```
{{node_id.output.field}} == value
{{node_id.output.field}} > 100
{{node_id.output.status}} == "approved"
```

Supported operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `not`

### 6.2 Case/Switch Node

#### Purpose
Multi-way branching based on expression value.

#### Configuration

```yaml
- id: route_by_priority
  type: case
  expression: "{{classify.output.priority}}"
  cases:
    - value: "high"
      nodes:
        - id: urgent_handler
          agent_persona: "UrgentHandler"
    - value: "medium"
      nodes:
        - id: standard_handler
          agent_persona: "StandardHandler"
    - value: "low"
      nodes:
        - id: batch_handler
          agent_persona: "BatchHandler"
  default:
    - id: fallback_handler
      agent_persona: "FallbackHandler"
```

#### Execution

1. **Evaluate Expression:** Substitute node outputs, get value
2. **Match Case:** Find matching case value
3. **Execute Branch:** Execute nodes in matched case
4. **Default:** If no match, execute default branch
5. **Skip Others:** Mark other branch nodes as "skipped"

### 6.3 Fork Node (with Implicit Join)

#### Purpose
Parallel execution of multiple branches with automatic waiting and output merging.

#### Configuration

```yaml
- id: parallel_enrichment
  type: fork
  branches:
    - id: enrich_billing
      agent_persona: "BillingEnricher"
      output_key: "billing"
    - id: enrich_shipping
      agent_persona: "ShippingEnricher"
      output_key: "shipping"
    - id: enrich_preferences
      agent_persona: "PreferencesEnricher"
      output_key: "preferences"
  # Implicit behavior:
  # - Waits for all branches to complete
  # - Merges outputs using output_keys
  # - If any branch fails, fork fails

- id: process_enriched_data
  agent_persona: "DataProcessor"
  depends_on: [parallel_enrichment]
  input:
    # Receives merged output: {billing: {...}, shipping: {...}, preferences: {...}}
    billing_info: "{{parallel_enrichment.output.billing}}"
    shipping_info: "{{parallel_enrichment.output.shipping}}"
```

#### Execution

**Fork Execution:**
1. **Start Branches:** Execute all branch nodes in parallel using asyncio.gather
2. **Track Progress:** Monitor each branch completion
3. **Wait for All:** Implicitly wait for all branches to complete (barrier synchronization)
4. **Merge Outputs:** Combine outputs using explicit `output_key` from each branch
5. **Validate Merged:** Validate merged output against dependent node's input schema
6. **Handle Errors:** If any branch fails, mark fork as failed (allow other branches to complete for cleanup)
7. **Pass to Next:** Fork's output is the merged object, available to dependent nodes

#### Output Merging

Each fork branch specifies an `output_key`. The fork node automatically merges outputs:

```python
merged_output = {
  "billing": enrich_billing_output,
  "shipping": enrich_shipping_output,
  "preferences": enrich_preferences_output
}
```

#### Error Handling

- If **any branch fails**, the fork node fails
- All other branches are allowed to complete (for proper cleanup)
- Fork node's status becomes "failed"
- Workflow fails (unless retry succeeds)

#### Future Enhancement

If partial joins are needed, add optional `wait_for` parameter:

```yaml
- id: parallel_work
  type: fork
  branches:
    - id: critical_1
      agent_persona: "CriticalAgent1"
      output_key: "critical1"
    - id: critical_2
      agent_persona: "CriticalAgent2"
      output_key: "critical2"
    - id: optional_logging
      agent_persona: "LoggingAgent"
      output_key: "logs"
  wait_for: [critical_1, critical_2]  # Optional: only wait for these branches
  # If omitted, waits for all branches (default behavior)
```

### 6.4 Loop Node

#### Purpose
Iterate over a list or until a condition is met.

#### Configuration

```yaml
- id: process_items
  type: loop
  max_iterations: 100
  iterate_over: "{{extract.output.items}}"
  loop_body:
    - id: process_item
      agent_persona: "ItemProcessor"
      input:
        item: "{{loop.current_item}}"
        index: "{{loop.current_index}}"
```

#### Execution

1. **Initialize:** Set iteration counter to 0
2. **Check Limit:** Ensure counter < max_iterations
3. **Get Next Item:** Get next item from list (or evaluate condition)
4. **Execute Body:** Execute loop body nodes with current item
5. **Increment:** Increment counter
6. **Repeat:** Go to step 2
7. **Collect Results:** Aggregate outputs from all iterations

#### Loop Variables

- `loop.current_item`: Current item being processed
- `loop.current_index`: Current iteration index (0-based)
- `loop.iteration_count`: Total iterations so far

---

## 7. Workflow Node Request Generation

### 7.1 Request Template System

#### Purpose
Provide rich, contextualized task descriptions to workflow nodes that reference previous node outputs while maintaining persona reusability.

#### Request Template Location

Request templates are defined in the workflow node configuration (not in persona definitions):

```yaml
workflow:
  nodes:
    - id: validate_customer
      agent_persona: "ValidationAgent"
      input:
        customer_name: "{{extract_info.output.customer_name}}"
        email: "{{extract_info.output.email}}"
      
      # Optional: Custom request template
      request_template: |
        Validate the customer information extracted from the document.
        
        Customer Name: {{input.customer_name}}
        Email Address: {{input.email}}
        
        Ensure the email format is valid and the name is not empty.
```

#### Template Variable Resolution

**Available Variables:**
- `{{input.field_name}}`: References a field from the node's input (after input mapping resolved)
- `{{workflow.name}}`: Workflow name
- `{{node.id}}`: Current node ID

**Resolution Process:**
1. Workflow executor resolves input mapping (e.g., `{{extract_info.output.customer_name}}` → actual value)
2. Saves resolved input as artifact: `node_{node_id}_input.json`
3. Processes request template, replacing `{{input.field}}` with `«value:node_{node_id}_input.json:field»`
4. Sends resolved request to agent

**Example Resolution:**

Template:
```
Customer Name: {{input.customer_name}}
Email: {{input.email}}
```

Resolved:
```
Customer Name: «value:node_validate_customer_input.json:customer_name»
Email: «value:node_validate_customer_input.json:email»
```

#### Default Request Template

If no `request_template` provided, the framework generates a default:

```
Your task: {first_sentence_of_persona_instruction}

Input data is available in artifact: {input_artifact_name}

Available input fields:
{list_of_input_schema_properties_with_types}

Please complete your task according to your instructions and mark your output with the result embed.
```

Example default:
```
Your task: Validate customer information for correctness.

Input data is available in artifact: node_validate_customer_input.json

Available input fields:
- customer_name (string): Customer's full name
- email (string): Customer's email address

Please complete your task according to your instructions and mark your output with the result embed.
```

### 7.2 Workflow System Prompt Injection

#### Purpose
Provide workflow-specific instructions to agents executing as workflow nodes, ensuring they understand the structured execution context and requirements.

#### System Prompt Structure

The complete prompt sent to a workflow node agent consists of:

1. **Persona's Base Instruction** (from persona definition)
2. **Workflow Execution Mode Header**
3. **Resolved Request Template** (with value references)
4. **Input Data Specification**
5. **Value Reference Protocol**
6. **Output Requirements**

#### Complete System Prompt Template

```
{persona_base_instruction}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFLOW EXECUTION MODE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You are executing as part of a structured workflow.

Workflow: {workflow_name}
Node ID: {node_id}
Your Role: {node_position_description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TASK REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{resolved_request_template}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT DATA SPECIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your input data is stored in a structured artifact: {input_artifact_name}

Input Schema (describes available fields):
{input_schema_formatted}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VALUE REFERENCE PROTOCOL (CRITICAL)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT: You have NOT been given the actual input data values.

To use input data in tool calls or generated content, you MUST use value references.

Syntax: «value:{input_artifact_name}:field_path»

Examples:
  - To reference 'customer_id': «value:{input_artifact_name}:customer_id»
  - To reference nested field: «value:{input_artifact_name}:address.zip_code»
  - To reference array item: «value:{input_artifact_name}:items[0].sku»

WHY THIS MATTERS:
- Value references ensure data integrity (prevents hallucination or typos)
- The framework resolves references to actual values when calling tools
- You MUST NOT attempt to guess, fabricate, or recall data values

WHEN TO LOAD ACTUAL DATA:
- Only load the input artifact if you need to make content-based decisions
- Use the load_artifact tool if you need to inspect data for logic/routing
- For pass-through or transformation tasks, use value references exclusively

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT REQUIREMENTS (MANDATORY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You MUST mark your output using the result embed:

Success:
  «result:artifact=output_filename.json status=success [message=optional]»

Failure:
  «result:status=failure message=reason_for_failure»

Your output artifact MUST conform to this schema:
{output_schema_formatted}

If you cannot complete your task:
- Use status=failure
- Provide a clear, specific error message
- Do NOT retry on your own (the framework handles retries)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Focus solely on your assigned task
- Do not attempt to access data outside your input artifact
- Do not make assumptions about other workflow nodes or overall workflow goals
- Do not deviate from the specified output schema
```

#### Template Variables

The system prompt template is populated with:

| Variable | Description | Example |
|----------|-------------|---------|
| `{persona_base_instruction}` | Agent persona's instruction | "Validate customer information for correctness." |
| `{workflow_name}` | Name of the workflow | "CustomerOnboardingWorkflow" |
| `{node_id}` | ID of current node | "validate_customer" |
| `{node_position_description}` | Optional context | "Node 2 of 5 in workflow" |
| `{resolved_request_template}` | Request with value references | "Validate customer: Name: «value:...»" |
| `{input_artifact_name}` | Name of input artifact | "node_validate_customer_input.json" |
| `{input_schema_formatted}` | Pretty-printed input schema | JSON schema with descriptions |
| `{output_schema_formatted}` | Pretty-printed output schema | JSON schema with descriptions |

#### Schema Formatting

Schemas are formatted for readability:

```json
{
  "type": "object",
  "properties": {
    "customer_name": {
      "type": "string",
      "description": "Customer's full name"
    },
    "email": {
      "type": "string",
      "description": "Customer's email address"
    }
  },
  "required": ["customer_name", "email"]
}
```

#### Injection Point

The workflow system prompt is injected in `WorkflowExecutorComponent._execute_node()`:

1. Load persona's base instruction from persona definition
2. Build workflow system prompt using template
3. Combine: `base_instruction + "\n\n" + workflow_prompt`
4. Send combined instruction to agent via A2A SendTask

#### Configuration Options

Workflow-level configuration for prompt injection (optional, for future):

```yaml
workflow:
  prompt_injection:
    include_position_info: true  # Include "Node X of Y"
    include_visual_separators: true  # Include ━━━ separators
    custom_preamble: "Additional context..."  # Optional custom text
```

**Note:** For MVP, use fixed template. Configuration can be added later if needed.

---

## 8. Data Structures

### 8.1 Configuration Models

**WorkflowConfig:**
- Parsed from YAML
- Validated at load time
- Contains all node definitions
- Includes input/output schemas

**NodeConfig:**
- Represents single workflow node
- Type-specific fields (agent persona, condition, branches, etc.)
- Resolved schemas attached at load time

**FlowControlNodeConfig:**
- Specialized configs for if/case/fork/join/loop
- Condition expressions
- Branch definitions
- Merge strategies

### 8.2 Execution State Models

**WorkflowExecutionState:**
- Complete state of workflow execution
- Persisted to session storage
- Used for monitoring and recovery

**NodeState:**
- State of individual node execution
- Status, timing, data, errors
- Retry tracking

### 8.3 Schema Models

**Schema Representation:**
- Standard JSON Schema format
- Stored in persona definitions
- Cached in workflow executor

**ValidationResult:**
- Success/failure status
- Error messages
- Validation errors list

**CompatibilityResult:**
- Compatibility check result
- List of incompatibility errors

---

## 9. API Contracts

### 9.1 WorkflowApp

**Initialization:**
- Extends SamAgentApp
- Validates workflow configuration
- Creates WorkflowExecutorComponent

**Key Methods:**
- `__init__(app_info, **kwargs)`: Initialize app with workflow config
- Inherits broker setup, subscription management from SamAgentApp

### 9.2 WorkflowExecutorComponent

**Initialization:**
- Extends ComponentBase
- Loads workflow definition
- Initializes DAG execution engine, schema validator, etc.

**Key Methods:**
- `process_event(event)`: Handle incoming A2A requests
- `_execute_workflow(workflow_input, user_id, session_id)`: Execute workflow DAG
- `_execute_node(node, node_input)`: Execute single node
- `_validate_schema(data, schema, context)`: Validate data against schema
- `_resolve_value_reference(reference)`: Resolve value reference embed
- `_parse_result_embed(response_text)`: Parse result embed from response

### 9.3 Schema Validator

**Key Methods:**
- `validate(data, schema, context)`: Validate data against schema
- `check_compatibility(source_schema, target_schema)`: Check schema compatibility

### 9.4 Embed Resolver

**Key Methods:**
- `resolve_value_reference(reference, artifact_service, ...)`: Resolve value reference
- `extract_json_path(data, path)`: Extract value using JSON path
- `parse_result_embed(embed_string)`: Parse result embed
- `extract_result_embed_from_response(response_text)`: Find and parse result embed

### 9.5 Flow Control Executor

**Key Methods:**
- `execute_if_node(node, state)`: Execute if/else node
- `execute_case_node(node, state)`: Execute case/switch node
- `execute_fork_node(node, state)`: Execute fork node with implicit join (parallel execution, wait for all, merge outputs)
- `execute_loop_node(node, state)`: Execute loop node
- `evaluate_condition(condition, state)`: Evaluate conditional expression

---

## 10. Error Handling

### 10.1 Error Types

**WorkflowConfigurationError:**
- Invalid workflow YAML
- Missing required fields
- Invalid node references

**SchemaValidationError:**
- Input/output doesn't match schema
- Includes detailed error messages
- Triggers retry logic

**NodeExecutionError:**
- Node execution failed
- Includes node ID and error message
- May trigger retry or fail workflow

**ValueReferenceError:**
- Value reference resolution failed
- Artifact not found or invalid path
- Triggers retry with error message

**TimeoutError:**
- Node or workflow exceeded timeout
- Includes timeout duration
- Fails workflow

### 10.2 Error Propagation

**Node Failure:**
- Mark node as failed
- Store error message in node state
- Fail workflow (unless retry succeeds)

**Workflow Failure:**
- Mark workflow as failed
- Store error message in workflow state
- Publish failure status update
- Return error response to caller

### 10.3 Retry Strategy

**Automatic Retry:**
- Schema validation failures: Up to 3 retries with error in prompt
- Value reference failures: Up to 3 retries with error in prompt
- Tool execution errors: Agent decides (existing behavior)

**No Retry:**
- Explicit failure status (`status=failure`)
- Timeout errors
- Configuration errors

---

## 11. Monitoring and Observability

### 11.1 Status Updates

Workflow publishes A2A status updates at key points:

**Events:**
- Workflow started
- Node started (node ID, timestamp)
- Node completed (node ID, duration)
- Node failed (node ID, error)
- Workflow completed (duration, output summary)
- Workflow failed (error message)

**Format:**
- Standard A2A status update format
- Metadata only (no intermediate data)
- Published to workflow status topic

### 11.2 Execution Trace

Workflow execution state includes complete trace:
- All node states with timing
- Input/output data for each node
- Error messages
- Retry counts

**Access:**
- Via session storage
- Can be retrieved for debugging
- Used for workflow visualization (future)

### 11.3 Metrics

**Key Metrics:**
- Workflow execution duration
- Node execution durations
- Schema validation success/failure rates
- Retry counts
- Error rates by type

**Collection:**
- Logged during execution
- Stored in workflow state
- Can be exported to monitoring systems

---

## 12. Deployment and Operations

### 12.1 Deployment Model

**Workflow as SAC App:**
- Each workflow is a separate SAC app
- Configured via YAML
- Runs in own process (or shared with other apps)
- Has own queue on broker

**Scaling:**
- Multiple instances of same workflow for load balancing
- Solace broker handles distribution
- Each instance processes different workflow executions

### 12.2 Graceful Upgrades

**Shutdown Mode:**
1. Old workflow instance receives shutdown signal
2. Unbinds from queue (stops accepting new requests)
3. Completes in-flight workflows within timeout
4. After timeout, force-stops
5. New workflow instance binds to queue, handles new requests

**Configuration:**
- Shutdown timeout configurable per workflow
- Default: 30 minutes
- Logged for monitoring

### 12.3 Configuration Management

**Workflow Definition:**
- Stored in YAML files
- Version controlled
- Deployed with SAC app

**Schema Management:**
- Schemas stored with agent personas
- Discovered via agent cards
- Cached by workflow executor

**Updates:**
- Workflow config changes require restart
- Schema changes handled via graceful shutdown
- No in-flight workflow upgrades (MVP)

---

## 13. Testing Strategy

### 13.1 Unit Tests

**Components to Test:**
- Schema validator (validation, compatibility checking)
- Embed resolver (value references, result embeds)
- DAG execution engine (topological sort, dependency tracking)
- Flow control executor (condition evaluation, branch selection)

**Test Approach:**
- Mock dependencies (artifact service, A2A client)
- Test edge cases (invalid schemas, missing artifacts, etc.)
- Verify error messages

### 13.2 Integration Tests

**Scenarios:**
- Simple linear workflow (3-5 nodes)
- Conditional workflow (if/else)
- Parallel workflow (fork/join)
- Nested workflow (workflow calling workflow)
- Error scenarios (validation failures, timeouts)

**Test Approach:**
- Use test agent personas with known schemas
- Verify end-to-end execution
- Check state persistence
- Validate status updates

### 13.3 Performance Tests

**Metrics:**
- Workflow execution latency
- Schema validation overhead
- Value reference resolution time
- Parallel execution efficiency

**Targets:**
- Workflow latency < 2x sequential agent calls
- Schema validation < 100ms per node
- Value reference resolution < 50ms per reference

---

## 14. Future Enhancements

### 14.1 Workflow Visualization

**Goal:** Provide visual representation of workflow execution

**Features:**
- DAG visualization
- Real-time execution progress
- Node status indicators
- Execution timeline

### 14.2 Advanced Error Recovery

**Goal:** Support compensation and rollback

**Features:**
- Compensation nodes (undo operations)
- Rollback on failure
- Partial workflow recovery

### 14.3 Workflow Versioning

**Goal:** Support multiple versions of workflows and schemas

**Features:**
- Version locking (workflow uses specific persona versions)
- Schema evolution (backward compatibility)
- Gradual rollout (canary deployments)

### 14.4 Workflow Templates

**Goal:** Provide reusable workflow patterns

**Features:**
- Template library (common patterns)
- Parameterized templates
- Template composition

### 14.5 Enhanced Monitoring

**Goal:** Comprehensive workflow observability

**Features:**
- Performance dashboards
- Execution analytics
- Anomaly detection
- Cost tracking (LLM token usage)

---

## 15. Open Questions and Decisions

### 15.1 Resolved Decisions

1. **Workflows are agents:** ✅ Decided - workflows appear as regular agents
2. **Schemas with personas:** ✅ Decided - schemas stored with persona definitions
3. **Value references:** ✅ Decided - `«value:artifact:path»` syntax
4. **Result embeds:** ✅ Decided - `«result:artifact=name status=success|failure»` syntax
5. **Runtime validation:** ✅ Decided - validate at first execution (MVP)

### 15.2 Open Questions

1. **State persistence strategy:** Follow session service configuration (memory/SQL)
2. **Workflow visualization:** Defer to future enhancement
3. **Testing approach:** Provide best practices, no special tooling (MVP)
4. **Error recovery:** Basic retry logic (MVP), advanced recovery future
5. **Versioning:** Always use latest persona versions (MVP), versioning future

---

**End of TDD**
