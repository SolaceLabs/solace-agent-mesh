# Workflows Configuration Guide

This guide describes how to configure workflows in Solace Agent Mesh. Workflows enable deterministic, structured execution flows as an alternative to LLM-driven orchestration—ideal for repeatable business processes, compliance-sensitive workflows, and cost-sensitive batch operations.

For architecture details, see [workflows-component-overview.md](./workflows-component-overview.md).

---

## Table of Contents

1. [Quick Start Structure](#quick-start-structure)
2. [App Configuration](#app-configuration)
3. [Workflow Definition](#workflow-definition)
4. [Node Types](#node-types)
5. [Template Expressions](#template-expressions)
6. [Retry Strategy](#retry-strategy)
7. [Exit Handlers](#exit-handlers)
8. [Input/Output Schemas](#inputoutput-schemas)
9. [Agent Configuration for Workflows](#agent-configuration-for-workflows)
10. [Dependencies and Execution Order](#dependencies-and-execution-order)

---

## Quick Start Structure

Minimal workflow configuration:

```yaml
apps:
  - name: my_workflow
    app_module: solace_agent_mesh.workflow.app
    broker: *broker_connection
    app_config:
      namespace: ${NAMESPACE}
      agent_name: "MyWorkflow"

      workflow:
        description: "Process incoming orders"
        nodes:
          - id: step1
            type: agent
            agent_name: "ProcessorAgent"
        outputMapping:
          result: "{{step1.output}}"
```

---

## App Configuration

Top-level `app_config` fields for workflows:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `namespace` | string | *required* | Namespace for agent discovery |
| `agent_name` | string | *required* | Workflow identifier (appears as agent name) |
| `display_name` | string | — | Human-readable name for UI |
| `max_workflow_execution_time_seconds` | int | `1800` | Maximum workflow runtime (30 min) |
| `default_node_timeout_seconds` | int | `300` | Default timeout for individual nodes (5 min) |
| `node_cancellation_timeout_seconds` | int | `30` | Grace period before force-failing cancelled nodes |
| `default_max_map_items` | int | `100` | Default max items for map nodes |

```yaml
app_config:
  namespace: ${NAMESPACE}
  agent_name: "OrderProcessor"
  display_name: "Order Processing Workflow"
  max_workflow_execution_time_seconds: 3600
  default_node_timeout_seconds: 600
  workflow: { ... }
```

---

## Workflow Definition

The `workflow` block defines the DAG structure:

| Field | Alias | Type | Required | Description |
|-------|-------|------|----------|-------------|
| `description` | — | string | yes | Human-readable workflow description |
| `input_schema` | `inputSchema` | object | no | JSON Schema for workflow input validation |
| `output_schema` | `outputSchema` | object | no | JSON Schema for workflow output validation |
| `nodes` | — | list | yes | List of workflow nodes (DAG vertices) |
| `output_mapping` | `outputMapping` | object | yes | Maps node outputs to final workflow result |
| `fail_fast` | `failFast` | bool | no | Stop scheduling new nodes on failure (default: `true`) |
| `retry_strategy` | `retryStrategy` | object | no | Default retry config for all nodes |
| `on_exit` | `onExit` | string/object | no | Exit handler configuration |
| `skills` | — | list | no | Skills for agent card registration |

```yaml
workflow:
  description: "Validate and process customer orders"
  inputSchema:
    type: object
    properties:
      order_id: { type: string }
    required: [order_id]
  failFast: true
  nodes: [ ... ]
  outputMapping:
    status: "{{final_step.output.status}}"
```

---

## Node Types

All nodes share these base fields:

| Field | Alias | Type | Required | Description |
|-------|-------|------|----------|-------------|
| `id` | — | string | yes | Unique node identifier |
| `type` | — | string | yes | Node type discriminator |
| `depends_on` | `dependencies` | list | no | Node IDs this node depends on |

### Agent Node

**Type:** `agent`

Invokes an agent as part of the workflow.

| Field | Alias | Type | Required | Description |
|-------|-------|------|----------|-------------|
| `agent_name` | — | string | yes | Name of agent to invoke |
| `input` | — | object | no | Input mapping using template expressions |
| `input_schema_override` | — | object | no | Override agent's default input schema |
| `output_schema_override` | — | object | no | Override agent's default output schema |
| `when` | — | string | no | Conditional execution expression |
| `retry_strategy` | `retryStrategy` | object | no | Node-specific retry configuration |
| `timeout` | — | string | no | Node-specific timeout (`'30s'`, `'5m'`, `'1h'`) |

```yaml
- id: validate_order
  type: agent
  agent_name: "OrderValidator"
  depends_on: [fetch_data]
  input:
    order_id: "{{workflow.input.order_id}}"
    data: "{{fetch_data.output.result}}"
  timeout: "2m"
  retryStrategy:
    limit: 3
```

### Conditional Node

**Type:** `conditional`

Binary (true/false) branching based on a condition expression.

| Field | Alias | Type | Required | Description |
|-------|-------|------|----------|-------------|
| `condition` | — | string | yes | Boolean expression to evaluate |
| `true_branch` | `trueBranch` | string | yes | Node ID to execute if true |
| `false_branch` | `falseBranch` | string | no | Node ID to execute if false |

> **Important:** Branch target nodes **must** list the conditional node in their `depends_on` field.

```yaml
- id: check_approval
  type: conditional
  depends_on: [calculate_total]
  condition: "{{calculate_total.output.amount}} > 500"
  trueBranch: manual_review
  falseBranch: auto_approve

- id: manual_review
  type: agent
  agent_name: "ManualReviewer"
  depends_on: [check_approval]  # Required!

- id: auto_approve
  type: agent
  agent_name: "AutoApprover"
  depends_on: [check_approval]  # Required!
```

### Switch Node

**Type:** `switch`

Multi-way branching with ordered case evaluation. First matching case wins.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cases` | list | yes | List of `{condition, node}` pairs |
| `default` | string | no | Fallback node ID if no cases match |

Each case has:
| Field | Alias | Description |
|-------|-------|-------------|
| `condition` | `when` | Expression to evaluate |
| `node` | `then` | Node ID to execute if condition matches |

> **Important:** All target nodes **must** list the switch node in their `depends_on` field.

```yaml
- id: route_shipping
  type: switch
  depends_on: [order_validation]
  cases:
    - condition: "'{{workflow.input.priority}}' == 'express'"
      node: ship_express
    - condition: "'{{workflow.input.priority}}' == 'standard'"
      node: ship_standard
  default: ship_economy

- id: ship_express
  type: agent
  agent_name: "ExpressShipper"
  depends_on: [route_shipping]
```

### Loop Node

**Type:** `loop`

Repeats a node while a condition remains true (while-loop).

| Field | Alias | Type | Required | Description |
|-------|-------|------|----------|-------------|
| `node` | — | string | yes | Node ID to execute repeatedly |
| `condition` | — | string | yes | Continue while this expression is true |
| `max_iterations` | `maxIterations` | int | no | Safety limit (default: `100`) |
| `delay` | — | string | no | Delay between iterations (`'5s'`, `'1m'`) |

**Special variable:** `{{_loop_iteration}}` — current iteration number (1-based)

```yaml
- id: poll_status
  type: loop
  depends_on: [submit_order]
  node: check_status
  condition: "{{check_status.output.ready}} == false"
  maxIterations: 10
  delay: "5s"

- id: check_status
  type: agent
  agent_name: "StatusChecker"
  input:
    order_id: "{{workflow.input.order_id}}"
    attempt: "{{_loop_iteration}}"
```

### Map Node

**Type:** `map`

Iterates over an array, executing a node for each item (for-each with optional parallelism).

| Field | Alias | Type | Required | Description |
|-------|-------|------|----------|-------------|
| `items` | — | string/object | one of three | Template expression for array |
| `with_param` | `withParam` | string | one of three | Argo-style: JSON array from step output |
| `with_items` | `withItems` | list | one of three | Static list of items |
| `node` | — | string | yes | Node ID to execute for each item |
| `max_items` | `maxItems` | int | no | Max items to process (default: `100`) |
| `concurrency_limit` | `concurrencyLimit` | int | no | Max parallel executions (default: unlimited) |

> Exactly **one** of `items`, `withParam`, or `withItems` must be provided.

**Special variable:** `{{_map_item}}` — current item being processed

```yaml
- id: process_items
  type: map
  depends_on: [fetch_orders]
  items: "{{fetch_orders.output.items}}"
  node: process_single
  maxItems: 50
  concurrencyLimit: 5

- id: process_single
  type: agent
  agent_name: "ItemProcessor"
  input:
    item_id: "{{_map_item.id}}"
    quantity: "{{_map_item.quantity}}"
```

With static items:
```yaml
- id: notify_channels
  type: map
  withItems: ["email", "sms", "slack"]
  node: send_notification
```

---

## Template Expressions

Template expressions allow dynamic data flow between nodes.

| Syntax | Description |
|--------|-------------|
| `{{workflow.input.field}}` | Access workflow input |
| `{{workflow.input.nested.field}}` | Access nested workflow input |
| `{{node_id.output}}` | Access entire node output |
| `{{node_id.output.field}}` | Access specific field from node output |
| `{{_map_item}}` | Current item in map iteration |
| `{{_map_item.field}}` | Field from current map item |
| `{{_loop_iteration}}` | Current loop iteration (1-based) |

### Coalesce Function

Select the first non-null value from multiple sources (useful for conditional branches):

```yaml
outputMapping:
  result:
    coalesce:
      - "{{express_ship.output.tracking}}"
      - "{{standard_ship.output.tracking}}"
      - "{{economy_ship.output.tracking}}"
```

### Condition Expressions

Used in `condition`, `when`, and `cases.condition` fields:

**Operators:** `==`, `!=`, `>`, `<`, `>=`, `<=`, `&&`, `||`

```yaml
# Numeric comparison
condition: "{{total.output.amount}} > 500"

# String comparison (use quotes around string values)
condition: "'{{classify.output.category}}' == 'premium'"

# Boolean check
condition: "{{check.output.valid}} == true"

# Combined conditions
when: "{{inventory.output.available}} == true && {{price.output.discount}} > 10"
```

---

## Retry Strategy

Configure automatic retries for transient failures.

| Field | Alias | Type | Default | Description |
|-------|-------|------|---------|-------------|
| `limit` | — | int | `3` | Maximum retry attempts |
| `retry_policy` | `retryPolicy` | string | `"OnFailure"` | When to retry: `Always`, `OnFailure`, `OnError` |
| `backoff` | — | object | — | Exponential backoff configuration |

**Backoff fields:**

| Field | Alias | Type | Default | Description |
|-------|-------|------|---------|-------------|
| `duration` | — | string | `"1s"` | Initial backoff duration |
| `factor` | — | float | `2.0` | Multiplier for exponential backoff |
| `max_duration` | `maxDuration` | string | — | Maximum backoff cap |

```yaml
# Workflow-level default
workflow:
  retryStrategy:
    limit: 3
    retryPolicy: "OnFailure"
    backoff:
      duration: "2s"
      factor: 2.0
      maxDuration: "1m"

# Node-level override
- id: flaky_service
  type: agent
  agent_name: "ExternalService"
  retryStrategy:
    limit: 5
    backoff:
      duration: "5s"
```

---

## Exit Handlers

Execute cleanup or notification nodes when workflow completes.

**Simple form** (single handler for all outcomes):
```yaml
workflow:
  onExit: "cleanup_resources"
```

**Structured form** (conditional handlers):
```yaml
workflow:
  onExit:
    always: "cleanup_resources"
    onSuccess: "send_success_notification"
    onFailure: "send_failure_alert"
```

| Field | Alias | Description |
|-------|-------|-------------|
| `always` | — | Node ID to execute regardless of outcome |
| `on_success` | `onSuccess` | Node ID to execute only on success |
| `on_failure` | `onFailure` | Node ID to execute only on failure |

---

## Input/Output Schemas

Define JSON Schema for workflow input/output validation.

```yaml
workflow:
  inputSchema:
    type: object
    properties:
      customer_id:
        type: string
        description: "Customer identifier"
      order_items:
        type: array
        items:
          type: object
          properties:
            sku: { type: string }
            quantity: { type: integer, minimum: 1 }
          required: [sku, quantity]
      priority:
        type: string
        enum: ["express", "standard", "economy"]
    required: [customer_id, order_items]

  outputSchema:
    type: object
    properties:
      order_id: { type: string }
      status: { type: string }
      tracking_number: { type: string }
    required: [order_id, status]
```

---

## Agent Configuration for Workflows

To work with workflows, agents can define input/output schemas in their configuration.

### Agent Schema Fields

Add these fields to agent `app_config`:

| Field | Type | Description |
|-------|------|-------------|
| `input_schema` | object | JSON Schema for validating agent input |
| `output_schema` | object | JSON Schema for validating agent output |

```yaml
apps:
  - name: order_validator
    app_module: solace_agent_mesh.agent.sac.app
    app_config:
      namespace: ${NAMESPACE}
      agent_name: "OrderValidator"

      input_schema:
        type: object
        properties:
          order_id: { type: string }
          items: { type: array }
        required: [order_id]

      output_schema:
        type: object
        properties:
          valid: { type: boolean }
          errors: { type: array }
        required: [valid]

      instruction: "Validate incoming orders..."
      agent_card: { ... }
```

### Result Embed Pattern

When invoked by a workflow, agents signal completion by outputting a result embed:

```
«result:artifact=output.json status=success»
```

The workflow executor extracts the artifact and validates it against the output schema.

### Schema Override in Workflows

Workflows can override an agent's default schemas per-node:

```yaml
- id: custom_validation
  type: agent
  agent_name: "GenericValidator"
  input_schema_override:
    type: object
    properties:
      data: { type: object }
    required: [data]
  output_schema_override:
    type: object
    properties:
      result: { type: string }
```

---

## Dependencies and Execution Order

### Execution Rules

1. **No dependencies** → Node starts immediately when workflow begins
2. **Single dependency** → Node waits for that dependency to complete
3. **Multiple dependencies** → Node waits for **all** dependencies (implicit join)
4. **Same dependency** → Nodes with the same dependency run in **parallel** (implicit fork)

### Parallel Execution

```yaml
nodes:
  - id: fetch_customer
    type: agent
    agent_name: "CustomerService"
    depends_on: [validate]

  - id: fetch_inventory
    type: agent
    agent_name: "InventoryService"
    depends_on: [validate]  # Both run in parallel after validate

  - id: process
    type: agent
    agent_name: "Processor"
    depends_on: [fetch_customer, fetch_inventory]  # Waits for both
```

### Branch Dependencies

**Critical:** Nodes that are targets of conditional/switch branches **must** declare the branching node in their `depends_on`:

```yaml
- id: check
  type: conditional
  condition: "{{prev.output.valid}}"
  trueBranch: path_a
  falseBranch: path_b

- id: path_a
  type: agent
  depends_on: [check]  # REQUIRED

- id: path_b
  type: agent
  depends_on: [check]  # REQUIRED
```

Without this dependency declaration, branch targets would execute immediately instead of waiting for the conditional evaluation.

---

## Complete Example

```yaml
apps:
  - name: order_workflow
    app_module: solace_agent_mesh.workflow.app
    broker: *broker_connection
    app_config:
      namespace: ${NAMESPACE}
      agent_name: "OrderProcessingWorkflow"
      display_name: "Order Processing"
      max_workflow_execution_time_seconds: 1800

      workflow:
        description: "End-to-end order processing with validation and shipping"

        inputSchema:
          type: object
          properties:
            order_id: { type: string }
            items: { type: array }
            priority: { type: string, enum: ["express", "standard"] }
          required: [order_id, items]

        outputSchema:
          type: object
          properties:
            status: { type: string }
            tracking: { type: string }

        failFast: true

        retryStrategy:
          limit: 2
          retryPolicy: "OnFailure"

        onExit:
          always: "cleanup"
          onFailure: "alert_ops"

        nodes:
          - id: validate
            type: agent
            agent_name: "OrderValidator"
            input:
              order_id: "{{workflow.input.order_id}}"
              items: "{{workflow.input.items}}"

          - id: check_valid
            type: conditional
            depends_on: [validate]
            condition: "{{validate.output.valid}} == true"
            trueBranch: process_items
            falseBranch: reject_order

          - id: process_items
            type: map
            depends_on: [check_valid]
            items: "{{workflow.input.items}}"
            node: process_single
            concurrencyLimit: 3

          - id: process_single
            type: agent
            agent_name: "ItemProcessor"
            input:
              item: "{{_map_item}}"

          - id: reject_order
            type: agent
            agent_name: "OrderRejector"
            depends_on: [check_valid]
            input:
              reason: "{{validate.output.errors}}"

          - id: ship
            type: agent
            agent_name: "ShippingService"
            depends_on: [process_items]
            input:
              order_id: "{{workflow.input.order_id}}"
              priority: "{{workflow.input.priority}}"

          - id: cleanup
            type: agent
            agent_name: "CleanupService"

          - id: alert_ops
            type: agent
            agent_name: "AlertService"

        outputMapping:
          status:
            coalesce:
              - "{{ship.output.status}}"
              - "{{reject_order.output.status}}"
          tracking: "{{ship.output.tracking_number}}"
```
