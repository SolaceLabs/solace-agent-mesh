---
title: Creating Workflows
sidebar_position: 421
---

Workflows enable you to orchestrate multiple agents in coordinated sequences to accomplish complex, multi-step tasks. This guide walks you through creating workflows, configuring different node types, and managing data flow between agents.

Before continuing with this guide, make sure you are familiar with the basic [workflow concept](../components/workflows.md) and [agents](../components/agents.md).

## Understanding Workflow Configuration

Workflows are configured through YAML files similar to agents, but use the `solace_agent_mesh.workflow.app` module. A workflow configuration consists of three main parts:

1. **Workflow Metadata**: Basic information like namespace, agent name, and description
2. **Workflow Definition**: The DAG structure including nodes, dependencies, and data flow
3. **Schema Definitions**: Optional input and output schemas for type safety

The workflow executes as a Directed Acyclic Graph (DAG) where nodes run in topological order based on their dependencies. Each node can access workflow input and outputs from completed nodes using template expressions.

## Basic Workflow Structure

Here is the basic structure of a workflow configuration:

```yaml
apps:
  - name: my_workflow
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "MyWorkflow"
      display_name: "My Workflow Description"

      workflow:
        description: |
          A clear description of what this workflow does, its inputs, and outputs.
          This appears in the agent card for discovery.

        input_schema:
          type: object
          properties:
            # Define expected input fields
          required: []

        output_schema:
          type: object
          properties:
            # Define expected output fields
          required: []

        nodes:
          # Define workflow nodes here

        output_mapping:
          # Map node outputs to final workflow output

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service
```

The `app_module` must be set to `solace_agent_mesh.workflow.app` to use the workflow engine. The workflow definition lives under `app_config.workflow` and defines the structure, nodes, and data flow.

## Defining Schemas

Input and output schemas are optional but recommended for type safety and clear contracts. They use JSON Schema format:

```yaml
workflow:
  input_schema:
    type: object
    properties:
      order_id:
        type: string
        description: "Unique order identifier"
      amount:
        type: integer
        description: "Order amount in cents"
    required: [order_id, amount]

  output_schema:
    type: object
    properties:
      final_status:
        type: string
        enum: ["approved", "pending_review", "rejected"]
      processed_order_id:
        type: string
    required: [final_status, processed_order_id]
```

These schemas validate data at workflow boundaries and provide documentation for users and other agents.

## Configuring Node Types

Workflows support four node types: agent, conditional, map, and fork. Each serves a different orchestration purpose.

### Agent Nodes

Agent nodes invoke agents to perform work. The workflow waits for the agent to complete and captures its output.

```yaml
nodes:
  - id: evaluate_risk
    type: agent
    agent_name: "RiskEvaluator"
    input:
      amount: "{{workflow.input.amount}}"
      customer_id: "{{workflow.input.customer_id}}"
```

**Key Fields:**

- **`id`** (required): Unique identifier for this node
- **`type`** (required): Must be `"agent"`
- **`agent_name`** (required): Name of the agent to invoke (must match an agent's `agent_name`)
- **`input`** (optional): Explicit input mapping using template expressions. If omitted, the workflow infers input from dependencies
- **`depends_on`** (optional): Array of node IDs that must complete before this node runs
- **`input_schema_override`** (optional): Override the agent's input schema
- **`output_schema_override`** (optional): Override the agent's output schema

**Accessing Output:**

Other nodes can access this node's output using `{{evaluate_risk.output.field_name}}`.

**Example with Dependencies:**

```yaml
nodes:
  - id: fetch_data
    type: agent
    agent_name: "DataFetcher"
    input:
      query: "{{workflow.input.search_term}}"

  - id: analyze_data
    type: agent
    agent_name: "DataAnalyzer"
    depends_on: [fetch_data]
    input:
      dataset: "{{fetch_data.output.results}}"
```

### Conditional Nodes

Conditional nodes evaluate expressions and route execution to different branches based on the result.

```yaml
nodes:
  - id: check_risk
    type: agent
    agent_name: "RiskEvaluator"
    input:
      amount: "{{workflow.input.amount}}"

  - id: risk_decision
    type: conditional
    depends_on: [check_risk]
    condition: "'{{check_risk.output.risk_level}}' == 'high'"
    true_branch: manual_review
    false_branch: auto_approve

  - id: manual_review
    type: agent
    agent_name: "ManualReviewer"
    depends_on: [risk_decision]
    input:
      order_id: "{{workflow.input.order_id}}"

  - id: auto_approve
    type: agent
    agent_name: "AutoApprover"
    depends_on: [risk_decision]
    input:
      order_id: "{{workflow.input.order_id}}"
```

**Key Fields:**

- **`id`** (required): Unique identifier for this node
- **`type`** (required): Must be `"conditional"`
- **`condition`** (required): Python expression evaluated using simpleeval. Use string comparisons with quotes
- **`true_branch`** (required): Node ID to execute if condition is true
- **`false_branch`** (optional): Node ID to execute if condition is false
- **`depends_on`** (optional): Array of node IDs that must complete first

**Condition Expression Syntax:**

Conditions use simpleeval for safe Python expression evaluation. Always use string comparisons with quotes:

```yaml
# Correct
condition: "'{{node.output.status}}' == 'success'"
condition: "'{{node.output.value}}' > 100"

# Incorrect (missing quotes around template)
condition: "{{node.output.status}} == 'success'"
```

**Important:** Both `true_branch` and `false_branch` target nodes must include the conditional node in their `depends_on` list. This ensures they don't execute before the condition is evaluated.

### Map Nodes

Map nodes process arrays by executing a target node for each item, with optional parallel execution.

```yaml
nodes:
  - id: generate_items
    type: agent
    agent_name: "ItemGenerator"

  - id: process_all_items
    type: map
    depends_on: [generate_items]
    items: "{{generate_items.output.items}}"
    node: process_single_item
    concurrency_limit: 5

  - id: process_single_item
    type: agent
    agent_name: "ItemProcessor"
    input:
      item_id: "{{_map_item.id}}"
      item_name: "{{_map_item.name}}"
```

**Key Fields:**

- **`id`** (required): Unique identifier for this node
- **`type`** (required): Must be `"map"`
- **`items`** (required): Template expression referencing an array, or an object with operators (like `coalesce`)
- **`node`** (required): ID of the node to execute for each item
- **`concurrency_limit`** (optional): Maximum number of concurrent executions (default: unlimited)
- **`max_items`** (optional): Maximum number of items to process (default: 100)
- **`depends_on`** (optional): Array of node IDs that must complete first

**Accessing Map Items:**

The target node accesses the current item via the special `{{_map_item}}` variable:

```yaml
input:
  field1: "{{_map_item.property}}"
  field2: "{{_map_item.nested.value}}"
```

**Map Output Structure:**

The map node produces an output object with a `results` array containing all item outputs:

```yaml
{
  "results": [
    {"processed_name": "PROCESSED_Item1", "status": "done"},
    {"processed_name": "PROCESSED_Item2", "status": "done"}
  ]
}
```

Access map results in subsequent nodes:

```yaml
- id: summarize
  type: agent
  agent_name: "Summarizer"
  depends_on: [process_all_items]
  input:
    results: "{{process_all_items.output.results}}"
```

### Fork Nodes

Fork nodes execute multiple branches in parallel and merge their outputs. This is useful for gathering data from multiple sources concurrently.

```yaml
nodes:
  - id: gather_data
    type: fork
    branches:
      - id: fetch_customer
        agent_name: "CustomerService"
        input:
          customer_id: "{{workflow.input.id}}"
        output_key: customer_data

      - id: fetch_orders
        agent_name: "OrderService"
        input:
          customer_id: "{{workflow.input.id}}"
        output_key: order_history
```

**Key Fields:**

- **`id`** (required): Unique identifier for this node
- **`type`** (required): Must be `"fork"`
- **`branches`** (required): Array of branch definitions
- **`depends_on`** (optional): Array of node IDs that must complete first

**Branch Definition:**

Each branch requires:
- **`id`**: Branch identifier
- **`agent_name`**: Agent to invoke
- **`input`**: Input mapping for the agent
- **`output_key`**: Key name for this branch's output in the merged result

**Fork Output Structure:**

The fork node merges all branch outputs into a single object:

```yaml
{
  "customer_data": { ... },
  "order_history": [ ... ]
}
```

## Template Expressions and Data Flow

Template expressions enable data flow between nodes using the syntax `{{path.to.value}}`.

### Accessing Data

**Workflow Input:**

```yaml
input:
  user_query: "{{workflow.input.query}}"
  user_id: "{{workflow.input.user_id}}"
```

**Node Outputs:**

```yaml
input:
  analysis_result: "{{analyze_data.output.summary}}"
  score: "{{evaluate_risk.output.risk_score}}"
```

**Map Items:**

```yaml
input:
  current_item: "{{_map_item.name}}"
  item_metadata: "{{_map_item.metadata.tags}}"
```

### Operators

Workflows support special operators for data transformation and fallback logic.

**Coalesce Operator:**

The `coalesce` operator returns the first non-null value from a list. This is useful for handling optional branches or providing defaults.

```yaml
output_mapping:
  final_status:
    coalesce:
      - "{{manual_review.output.status}}"
      - "{{auto_approve.output.status}}"
      - "pending"
```

In a conditional workflow, only one branch executes. The `coalesce` operator picks whichever output exists.

**Concat Operator:**

The `concat` operator joins strings or arrays:

```yaml
output_mapping:
  summary_message:
    concat:
      - "Processed "
      - "{{workflow.input.order_count}}"
      - " orders. Status: "
      - "{{final_node.output.status}}"
```

### Output Mapping

The `output_mapping` section constructs the workflow's final output from node results:

```yaml
output_mapping:
  processed_order_id: "{{workflow.input.order_id}}"
  final_status:
    coalesce:
      - "{{manual_review.output.status}}"
      - "{{auto_approve.output.status}}"
  item_count: "{{summarize.output.total_processed}}"
  report:
    concat:
      - "Order "
      - "{{workflow.input.order_id}}"
      - " was "
      - "{{final_status}}"
```

## Dependency Management

The `depends_on` field controls execution order. A node waits for all its dependencies to complete before starting.

**Sequential Execution:**

```yaml
nodes:
  - id: step1
    type: agent
    agent_name: "Agent1"

  - id: step2
    type: agent
    agent_name: "Agent2"
    depends_on: [step1]

  - id: step3
    type: agent
    agent_name: "Agent3"
    depends_on: [step2]
```

**Parallel Execution:**

Nodes without dependencies or with satisfied dependencies run in parallel:

```yaml
nodes:
  - id: fetch_data
    type: agent
    agent_name: "DataFetcher"

  # These run in parallel after fetch_data completes
  - id: analyze_option_a
    type: agent
    agent_name: "AnalyzerA"
    depends_on: [fetch_data]

  - id: analyze_option_b
    type: agent
    agent_name: "AnalyzerB"
    depends_on: [fetch_data]

  # Waits for both analyses
  - id: compare_results
    type: agent
    agent_name: "Comparator"
    depends_on: [analyze_option_a, analyze_option_b]
```

**Conditional Dependencies:**

For conditional nodes, both branch targets must depend on the conditional node:

```yaml
- id: decide
  type: conditional
  condition: "..."
  true_branch: branch_a
  false_branch: branch_b

- id: branch_a
  type: agent
  agent_name: "AgentA"
  depends_on: [decide]  # Required!

- id: branch_b
  type: agent
  agent_name: "AgentB"
  depends_on: [decide]  # Required!
```

## Complete Working Examples

### Example 1: Simple Conditional Workflow

This workflow evaluates order risk and routes to either automatic approval or manual review:

```yaml
apps:
  - name: order_processor
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "OrderProcessor"
      display_name: "Order Processing Workflow"

      workflow:
        description: |
          Processes orders by evaluating risk and routing accordingly:
          - Low risk (amount <= 100): Auto-approve
          - High risk (amount > 100): Manual review

        input_schema:
          type: object
          properties:
            order_id: {type: string}
            amount: {type: integer}
          required: [order_id, amount]

        output_schema:
          type: object
          properties:
            final_status: {type: string}
            processed_order_id: {type: string}
          required: [final_status, processed_order_id]

        nodes:
          # Step 1: Evaluate risk
          - id: check_risk
            type: agent
            agent_name: "RiskEvaluator"
            input:
              amount: "{{workflow.input.amount}}"

          # Step 2: Branch based on risk
          - id: risk_branch
            type: conditional
            depends_on: [check_risk]
            condition: "'{{check_risk.output.risk_level}}' == 'high'"
            true_branch: send_to_review
            false_branch: auto_approve

          # High risk path
          - id: send_to_review
            type: agent
            agent_name: "ManualReviewer"
            depends_on: [risk_branch]
            input:
              order_id: "{{workflow.input.order_id}}"

          # Low risk path
          - id: auto_approve
            type: agent
            agent_name: "AutoApprover"
            depends_on: [risk_branch]
            input:
              order_id: "{{workflow.input.order_id}}"

        output_mapping:
          processed_order_id: "{{workflow.input.order_id}}"
          final_status:
            coalesce:
              - "{{send_to_review.output.status}}"
              - "{{auto_approve.output.status}}"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service
```

**How It Works:**

1. The workflow receives an order with `order_id` and `amount`
2. `RiskEvaluator` agent determines risk level based on amount
3. The conditional node routes high-risk orders to `ManualReviewer`, low-risk to `AutoApprover`
4. Only one branch executes; `coalesce` picks the active branch's status
5. The workflow returns the order ID and final status

### Example 2: Parallel Processing with Map

This workflow processes a list of items in parallel with concurrency control:

```yaml
apps:
  - name: batch_processor
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "BatchProcessor"
      display_name: "Batch Processing Workflow"

      workflow:
        description: |
          Processes batches of items in parallel:
          1. Optionally generates test data or uses provided items
          2. Processes each item concurrently (max 2 at a time)
          3. Summarizes results

        input_schema:
          type: object
          properties:
            mode:
              type: string
              enum: ["generate", "direct"]
            direct_items:
              type: array
              items: {type: object}
          required: [mode]

        output_schema:
          type: object
          properties:
            final_report: {type: string}
            item_count: {type: integer}
          required: [final_report, item_count]

        nodes:
          # Optional: Generate test data
          - id: mode_check
            type: conditional
            condition: "'{{workflow.input.mode}}' == 'generate'"
            true_branch: generate_data

          - id: generate_data
            type: agent
            agent_name: "DataGenerator"
            depends_on: [mode_check]

          # Process items in parallel
          - id: process_items
            type: map
            depends_on: [generate_data, mode_check]
            items:
              coalesce:
                - "{{generate_data.output.items}}"
                - "{{workflow.input.direct_items}}"
            node: process_single_item
            concurrency_limit: 2

          - id: process_single_item
            type: agent
            agent_name: "ItemProcessor"
            input:
              id: "{{_map_item.id}}"
              name: "{{_map_item.name}}"

          # Summarize results
          - id: summarize_results
            type: agent
            agent_name: "Summarizer"
            depends_on: [process_items]
            input:
              results: "{{process_items.output.results}}"

        output_mapping:
          item_count: "{{summarize_results.output.total_processed}}"
          final_report:
            concat:
              - "Workflow Complete. "
              - "{{summarize_results.output.summary_text}}"
              - " (Mode: "
              - "{{workflow.input.mode}}"
              - ")"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service
```

**How It Works:**

1. The workflow accepts either `mode: generate` or `mode: direct` with `direct_items`
2. If mode is "generate", the `DataGenerator` creates test items
3. The `coalesce` operator uses generated items if available, otherwise uses `direct_items`
4. The map node processes each item with a concurrency limit of 2
5. Each item is processed by `ItemProcessor` which accesses item properties via `{{_map_item}}`
6. Results are summarized and concatenated into a final report

## Best Practices

**Schema Design for Type Safety:**

Always define input and output schemas for workflows. This provides validation, documentation, and clear contracts for callers.

**Using Concurrency Limits Effectively:**

Set `concurrency_limit` on map nodes to control resource usage. Start with conservative limits (5-10) and adjust based on agent performance and system capacity.

**Workflow Composition Patterns:**

Build complex workflows by composing simpler patterns:
- **Pipeline**: Sequential nodes for multi-stage processing
- **Fan-out/Fan-in**: Map nodes for parallel processing, followed by aggregation
- **Decision Tree**: Nested conditional nodes for complex routing logic

**Naming Conventions for Clarity:**

Use descriptive node IDs that indicate purpose (`check_risk`, `process_items`, `summarize_results`). This makes workflows self-documenting and easier to debug.

For a complete reference of all workflow configuration parameters, see [Workflow Configuration](../installing-and-configuring/configurations.md#workflow-configuration).
