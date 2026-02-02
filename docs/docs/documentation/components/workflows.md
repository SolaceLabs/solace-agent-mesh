---
title: Workflows
sidebar_position: 225
---

# Workflows

Workflows orchestrate multiple agents through YAML configuration. Unlike the [orchestrator](./orchestrator.md), which uses AI to dynamically decide how to accomplish tasks, workflows follow explicit paths you define. Each step, branch, and iteration is specified in configuration.

Use workflows when you need:
- Predictable execution that follows the same path every time
- Business processes with compliance or audit requirements
- Visual representation of agent interactions in the UI
- Fine-grained control over error handling and retries

## Workflows vs. Orchestrator

The orchestrator excels at open-ended tasks where the AI determines the best approach. Workflows are better when you know exactly what steps need to happen and in what order.

| Aspect | Orchestrator | Workflows |
|--------|--------------|-----------|
| Control flow | AI decides | You define |
| Visibility | Emergent behavior | Explicit DAG |
| Best for | Exploratory tasks | Repeatable processes |

## Configuration Overview

A workflow is defined in the `workflow` section of your YAML configuration file:

```yaml
apps:
  - name: my_workflow
    app_module: solace_agent_mesh.workflow.app
    broker:
      # ... broker configuration

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "MyWorkflow"

      workflow:
        description: "Process incoming orders"
        version: "1.0.0"

        input_schema:
          type: object
          properties:
            order_id:
              type: string
          required: [order_id]

        nodes:
          - id: validate_order
            type: agent
            agent_name: "OrderValidator"
            input:
              order_id: "{{workflow.input.order_id}}"

          - id: process_payment
            type: agent
            agent_name: "PaymentProcessor"
            depends_on: [validate_order]
            input:
              order_data: "{{validate_order.output}}"

        output_mapping:
          status: "{{process_payment.output.status}}"
          confirmation: "{{process_payment.output.confirmation_number}}"
```

### Top-Level Fields

| Field | Required | Description |
|-------|----------|-------------|
| `description` | Yes | What the workflow does |
| `nodes` | Yes | The workflow steps |
| `output_mapping` | Yes | Maps node outputs to final workflow output |
| `version` | No | Semantic version (default: "1.0.0") |
| `input_schema` | No | JSON Schema for workflow input validation |
| `output_schema` | No | JSON Schema for workflow output validation |
| `skills` | No | Skills exposed in the agent card |
| `on_exit` | No | Exit handler for cleanup |
| `fail_fast` | No | Stop on first failure (default: true) |
| `max_call_depth` | No | Limit for nested workflows (default: 10) |
| `retry_strategy` | No | Default retry configuration for all nodes |

### App-Level Settings

These settings go in `app_config`, outside the `workflow` block:

| Field | Default | Description |
|-------|---------|-------------|
| `max_workflow_execution_time_seconds` | 1800 | Maximum total workflow runtime (30 minutes) |
| `default_node_timeout_seconds` | 300 | Default timeout per node (5 minutes) |
| `default_max_map_items` | 100 | Safety limit for map node iterations |

## Node Types

### Agent Node

Invokes an agent and captures its output.

```yaml
- id: analyze_data
  type: agent
  agent_name: "DataAnalyzer"
  input:
    dataset: "{{workflow.input.dataset}}"
    parameters: "{{workflow.input.analysis_params}}"
  instruction: "Focus on anomalies in the {{workflow.input.target_field}} field"
  timeout: "10m"
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier for this node |
| `type` | Yes | Must be `agent` |
| `agent_name` | Yes | Name of the agent to call |
| `input` | No | Input data mapping (template expressions allowed) |
| `instruction` | No | Additional context for the agent |
| `depends_on` | No | Node IDs that must complete first |
| `timeout` | No | Override default timeout (e.g., "30s", "5m", "1h") |
| `retry_strategy` | No | Override default retry behavior |
| `input_schema_override` | No | Override agent's input schema |
| `output_schema_override` | No | Override agent's output schema |

### Switch Node

Routes execution based on conditions. Cases are evaluated in order; the first match wins.

```yaml
- id: route_by_priority
  type: switch
  depends_on: [classify_ticket]
  cases:
    - condition: "{{classify_ticket.output.priority}} == 'critical'"
      node: escalate_immediately
    - condition: "{{classify_ticket.output.priority}} == 'high'"
      node: assign_senior_agent
  default: add_to_queue
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier |
| `type` | Yes | Must be `switch` |
| `cases` | Yes | List of condition/node pairs |
| `default` | No | Node to execute if no case matches |
| `depends_on` | No | Node IDs that must complete first |

Each case has:
- `condition`: Expression to evaluate (see [Condition Expressions](#condition-expressions))
- `node`: ID of the node to execute if condition is true

Nodes in branches that aren't selected are skipped entirely.

### Map Node

Executes a node for each item in a collection. Items are processed in parallel by default.

```yaml
- id: process_all_items
  type: map
  depends_on: [fetch_items]
  items: "{{fetch_items.output.item_list}}"
  node: process_single_item
  concurrency_limit: 5
  max_items: 50

- id: process_single_item
  type: agent
  agent_name: "ItemProcessor"
  input:
    item: "{{_map_item}}"
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier |
| `type` | Yes | Must be `map` |
| `node` | Yes | Node ID to execute for each item |
| `items` | Yes* | Template expression resolving to an array |
| `depends_on` | No | Node IDs that must complete first |
| `concurrency_limit` | No | Max parallel executions (unlimited if not set) |
| `max_items` | No | Safety limit (default: 100) |

*Or use `withItems` for a static list, or `withParam` for Argo-style syntax.

The target node accesses the current item via `{{_map_item}}` or `{{_map_item.field}}`. The current index is available as `{{_map_index}}`.

After all iterations complete, the map node's output contains a `results` array with each iteration's output in order.

### Loop Node

Repeats a node until a condition becomes false. The first iteration always runs; the condition is checked before subsequent iterations.

```yaml
- id: poll_until_ready
  type: loop
  node: check_status
  condition: "{{check_status.output.ready}} == false"
  max_iterations: 30
  delay: "10s"

- id: check_status
  type: agent
  agent_name: "StatusChecker"
  input:
    task_id: "{{workflow.input.task_id}}"
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier |
| `type` | Yes | Must be `loop` |
| `node` | Yes | Node ID to execute repeatedly |
| `condition` | Yes | Continue while this is true |
| `depends_on` | No | Node IDs that must complete first |
| `max_iterations` | No | Safety limit (default: 100) |
| `delay` | No | Wait between iterations (e.g., "5s", "1m") |

The current iteration number (starting at 0) is available as `{{_loop_iteration}}`.

### Workflow Node

Invokes another workflow as a sub-workflow.

```yaml
- id: run_validation_workflow
  type: workflow
  workflow_name: "ValidationWorkflow"
  input:
    data: "{{workflow.input.payload}}"
  timeout: "15m"
```

The fields match agent nodes, except `workflow_name` replaces `agent_name`. Workflows cannot call themselves directly.

The `max_call_depth` setting (default: 10) limits how deeply workflows can nest to prevent infinite recursion.

## Template Expressions

Template expressions reference data from workflow input or node outputs using `{{...}}` syntax.

### Available References

| Expression | Description |
|------------|-------------|
| `{{workflow.input.field}}` | Workflow input field |
| `{{node_id.output.field}}` | Output from a completed node |
| `{{_map_item}}` | Current item in a map iteration |
| `{{_map_item.field}}` | Field from current map item |
| `{{_map_index}}` | Current map iteration index (0-based) |
| `{{_loop_iteration}}` | Current loop iteration number (0-based) |

### Operators

**coalesce** returns the first non-null value:

```yaml
output_mapping:
  result:
    coalesce:
      - "{{primary_source.output.value}}"
      - "{{fallback_source.output.value}}"
      - "default_value"
```

**concat** joins values as strings:

```yaml
input:
  message:
    concat:
      - "Processing order "
      - "{{workflow.input.order_id}}"
      - " for customer "
      - "{{workflow.input.customer_name}}"
```

## Condition Expressions

Switch conditions and loop conditions use a safe expression syntax:

**Comparisons:** `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`

**Boolean:** `and`, `or`, `not`

**Literals:** strings (quoted), numbers, `true`, `false`, `null`

Examples:
```yaml
# Equality
"{{node.output.status}} == 'complete'"

# Numeric comparison
"{{node.output.count}} > 10"

# Boolean logic
"{{node.output.ready}} == true and {{node.output.errors}} == 0"

# Membership
"{{node.output.category}} in ['A', 'B', 'C']"
```

## Dependencies and Parallelism

Nodes declare dependencies with `depends_on`. A node executes only after all its dependencies complete.

```yaml
nodes:
  - id: fetch_user
    type: agent
    agent_name: "UserService"

  - id: fetch_orders
    type: agent
    agent_name: "OrderService"

  # These two run in parallel (no dependencies between them)

  - id: generate_report
    type: agent
    agent_name: "ReportGenerator"
    depends_on: [fetch_user, fetch_orders]  # Waits for both
```

Nodes with no dependencies (or whose dependencies are all satisfied) run in parallel automatically.

## Error Handling

### Retry Strategy

Configure retries at the workflow level (applies to all nodes) or per-node:

```yaml
workflow:
  retry_strategy:
    limit: 3
    retry_policy: "OnFailure"
    backoff:
      duration: "2s"
      factor: 2.0
      max_duration: "30s"
```

| Field | Default | Description |
|-------|---------|-------------|
| `limit` | 3 | Maximum retry attempts |
| `retry_policy` | "OnFailure" | When to retry: "Always", "OnFailure", "OnError" |
| `backoff.duration` | "1s" | Initial wait before first retry |
| `backoff.factor` | 2.0 | Multiplier for each subsequent retry |
| `backoff.max_duration` | None | Cap on backoff duration |

### Exit Handlers

Run cleanup or notification nodes when the workflow completes:

```yaml
workflow:
  on_exit: cleanup_resources  # Always runs
```

Or specify different handlers for different outcomes:

```yaml
workflow:
  on_exit:
    on_success: send_success_notification
    on_failure: send_failure_alert
    on_cancel: cleanup_partial_state
    always: log_completion
```

Exit handler nodes must be defined in the `nodes` array like any other node.

### Fail-Fast Behavior

By default (`fail_fast: true`), when a node fails, no new nodes are scheduled. Nodes already running continue to completion.

Set `fail_fast: false` to allow independent branches to continue executing even when one branch fails.

## Workflow Discovery

Workflows register themselves as agents and publish agent cards for discovery. Other agents and the orchestrator can invoke workflows just like any other agent.

The workflow's input and output schemas appear in the agent card, along with any skills you define:

```yaml
workflow:
  skills:
    - id: "process_order"
      name: "Process Order"
      description: "Validates and processes a customer order"
      tags: ["orders", "processing"]
```

## Schema Reference

The complete JSON Schema for workflow definitions is available at [`src/solace_agent_mesh/common/schemas/workflow_schema.json`](https://github.com/SolaceDev/solace-agent-mesh/blob/main/src/solace_agent_mesh/common/schemas/workflow_schema.json).

Use this schema with your IDE or YAML validator for autocompletion and validation while writing workflow configurations.

## Next Steps

For a hands-on guide to building workflows, see [Creating Workflows](../developing/creating-workflows.md).
