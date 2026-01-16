---
title: Creating Workflows
sidebar_position: 425
---

# Creating Workflows

This guide walks through building workflows that orchestrate multiple agents. You'll learn how to define execution sequences, pass data between nodes, handle branching logic, and process collections.

## Prerequisites

Before creating workflows, you need:
- A running Solace Agent Mesh instance
- At least one agent deployed that your workflow can call
- Familiarity with YAML configuration files

## A Simple Workflow

Start with a workflow that calls two agents in sequence. The first agent analyzes text, and the second summarizes the analysis.

```yaml
apps:
  # First, define the agents (or reference existing ones)

  - name: text_workflow
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "TextAnalysisWorkflow"

      workflow:
        description: "Analyzes text and produces a summary"

        input_schema:
          type: object
          properties:
            text:
              type: string
              description: "Text to analyze"
          required: [text]

        nodes:
          - id: analyze
            type: agent
            agent_name: "TextAnalyzer"
            input:
              content: "{{workflow.input.text}}"

          - id: summarize
            type: agent
            agent_name: "Summarizer"
            depends_on: [analyze]
            input:
              analysis: "{{analyze.output}}"

        output_mapping:
          summary: "{{summarize.output.summary}}"
          key_points: "{{summarize.output.key_points}}"
```

Key points:
- The workflow uses `app_module: solace_agent_mesh.workflow.app`
- `depends_on: [analyze]` ensures `summarize` waits for `analyze` to complete
- Template expressions like `{{analyze.output}}` pass data between nodes

## Running a Workflow

Workflows register as agents, so you invoke them the same way you'd invoke any agent. From the orchestrator or another agent, simply call the workflow by its `agent_name`.

The workflow appears in the UI's agent list and can be triggered through any gateway.

## Passing Data with Templates

Template expressions connect your workflow's pieces together.

### Workflow Input

Access input fields with `{{workflow.input.field_name}}`:

```yaml
input_schema:
  type: object
  properties:
    customer_id:
      type: string
    include_history:
      type: boolean

nodes:
  - id: fetch_customer
    type: agent
    agent_name: "CustomerService"
    input:
      id: "{{workflow.input.customer_id}}"
      fetch_history: "{{workflow.input.include_history}}"
```

### Node Output

Reference completed nodes with `{{node_id.output.field}}`:

```yaml
- id: validate
  type: agent
  agent_name: "Validator"
  input:
    data: "{{workflow.input.payload}}"

- id: process
  type: agent
  agent_name: "Processor"
  depends_on: [validate]
  input:
    validated_data: "{{validate.output.cleaned_data}}"
    validation_score: "{{validate.output.confidence}}"
```

### Handling Missing Values

Use `coalesce` when a value might not exist:

```yaml
- id: enrich
  type: agent
  agent_name: "DataEnricher"
  input:
    primary_source: "{{workflow.input.preferred_source}}"
    data:
      coalesce:
        - "{{optional_step.output.result}}"
        - "{{workflow.input.fallback_data}}"
```

The first non-null value is used.

## Adding Instructions

The `instruction` field provides context to agents beyond the structured input:

```yaml
- id: generate_report
  type: agent
  agent_name: "ReportGenerator"
  input:
    data: "{{analysis.output.metrics}}"
  instruction: |
    Generate an executive summary for {{workflow.input.audience}}.
    Focus on trends related to {{workflow.input.focus_area}}.
    Keep the tone {{workflow.input.tone}}.
```

Instructions support the same template expressions as input fields.

## Conditional Branching

Switch nodes route execution based on data values.

```yaml
nodes:
  - id: classify
    type: agent
    agent_name: "RequestClassifier"
    input:
      request: "{{workflow.input.request}}"

  - id: route_request
    type: switch
    depends_on: [classify]
    cases:
      - condition: "{{classify.output.type}} == 'billing'"
        node: handle_billing
      - condition: "{{classify.output.type}} == 'technical'"
        node: handle_technical
      - condition: "{{classify.output.urgency}} == 'high'"
        node: escalate
    default: handle_general

  - id: handle_billing
    type: agent
    agent_name: "BillingAgent"
    depends_on: [route_request]
    input:
      request: "{{workflow.input.request}}"

  - id: handle_technical
    type: agent
    agent_name: "TechSupport"
    depends_on: [route_request]
    input:
      request: "{{workflow.input.request}}"

  - id: escalate
    type: agent
    agent_name: "EscalationHandler"
    depends_on: [route_request]
    input:
      request: "{{workflow.input.request}}"

  - id: handle_general
    type: agent
    agent_name: "GeneralSupport"
    depends_on: [route_request]
    input:
      request: "{{workflow.input.request}}"

output_mapping:
  response:
    coalesce:
      - "{{handle_billing.output.response}}"
      - "{{handle_technical.output.response}}"
      - "{{escalate.output.response}}"
      - "{{handle_general.output.response}}"
```

Cases are evaluated top to bottom. The first matching condition wins. Nodes in non-selected branches are skipped entirely.

Notice that branch nodes must list the switch node in their `depends_on`. This ensures they only run when selected.

## Processing Collections

Map nodes iterate over arrays. Each item is processed by the target node.

```yaml
nodes:
  - id: fetch_orders
    type: agent
    agent_name: "OrderFetcher"
    input:
      customer_id: "{{workflow.input.customer_id}}"

  - id: process_orders
    type: map
    depends_on: [fetch_orders]
    items: "{{fetch_orders.output.orders}}"
    node: validate_order
    concurrency_limit: 3

  - id: validate_order
    type: agent
    agent_name: "OrderValidator"
    input:
      order: "{{_map_item}}"
      order_index: "{{_map_index}}"

output_mapping:
  validation_results: "{{process_orders.output.results}}"
```

Inside the target node, `{{_map_item}}` is the current item. After all iterations complete, the map node's output contains `results`—an array of each iteration's output in order.

Set `concurrency_limit` to control parallelism. Without it, all items process simultaneously.

## Polling with Loops

Loop nodes repeat until a condition becomes false. Use them for polling or retry patterns.

```yaml
nodes:
  - id: start_job
    type: agent
    agent_name: "JobStarter"
    input:
      job_config: "{{workflow.input.config}}"

  - id: wait_for_completion
    type: loop
    depends_on: [start_job]
    node: check_job
    condition: "{{check_job.output.status}} != 'complete'"
    max_iterations: 60
    delay: "10s"

  - id: check_job
    type: agent
    agent_name: "JobStatusChecker"
    input:
      job_id: "{{start_job.output.job_id}}"

  - id: get_results
    type: agent
    agent_name: "ResultFetcher"
    depends_on: [wait_for_completion]
    input:
      job_id: "{{start_job.output.job_id}}"

output_mapping:
  results: "{{get_results.output.data}}"
```

The loop runs `check_job` repeatedly. The first iteration always executes; the condition is checked before each subsequent iteration. Once the condition is false (job complete), execution continues to `get_results`.

The `delay` adds a wait between iterations—essential for polling to avoid overwhelming the target service.

## Composing Workflows

Workflow nodes call other workflows as sub-workflows:

```yaml
nodes:
  - id: validate_input
    type: workflow
    workflow_name: "InputValidationWorkflow"
    input:
      payload: "{{workflow.input.data}}"

  - id: process
    type: agent
    agent_name: "MainProcessor"
    depends_on: [validate_input]
    input:
      validated: "{{validate_input.output}}"
```

Sub-workflows are useful for:
- Reusing common sequences across multiple workflows
- Breaking complex workflows into manageable pieces
- Isolating concerns (validation, notification, etc.)

Workflows cannot call themselves directly. The `max_call_depth` setting (default 10) prevents runaway recursion through indirect calls.

## Error Handling

### Retries

Configure retries at the workflow level or per-node:

```yaml
workflow:
  # Default for all nodes
  retry_strategy:
    limit: 3
    retry_policy: "OnFailure"
    backoff:
      duration: "1s"
      factor: 2
      max_duration: "30s"

  nodes:
    - id: critical_step
      type: agent
      agent_name: "CriticalService"
      # Override for this node
      retry_strategy:
        limit: 5
        backoff:
          duration: "5s"
```

### Exit Handlers

Run cleanup regardless of success or failure:

```yaml
workflow:
  on_exit:
    always: log_completion
    on_failure: send_alert
    on_success: send_confirmation

  nodes:
    # ... workflow nodes ...

    - id: log_completion
      type: agent
      agent_name: "AuditLogger"
      input:
        workflow: "{{workflow.input}}"

    - id: send_alert
      type: agent
      agent_name: "AlertSender"
      input:
        error: "{{workflow.error}}"

    - id: send_confirmation
      type: agent
      agent_name: "NotificationSender"
      input:
        result: "{{workflow.output}}"
```

Exit handlers are regular nodes in your workflow—they just get triggered automatically on workflow completion.

## Timeouts

Set timeouts to prevent workflows or nodes from running indefinitely:

```yaml
app_config:
  # Workflow-level settings
  max_workflow_execution_time_seconds: 3600  # 1 hour total
  default_node_timeout_seconds: 300          # 5 minutes per node

  workflow:
    nodes:
      - id: long_running_task
        type: agent
        agent_name: "SlowProcessor"
        timeout: "30m"  # Override for this node
```

## Testing Workflows

Test workflows incrementally:

1. **Start simple.** Get a two-node workflow running before adding complexity.

2. **Check data flow.** Use agents that echo their input to verify template expressions resolve correctly.

3. **Test branches independently.** For switch nodes, create test inputs that exercise each branch.

4. **Limit iterations during development.** Set low `max_items` and `max_iterations` values while testing map and loop nodes.

5. **Watch the UI.** The workflow visualization shows execution progress and helps identify where things go wrong.

## Example: Document Processing Pipeline

This example combines several patterns into a realistic workflow:

```yaml
workflow:
  description: "Processes uploaded documents through classification, extraction, and storage"

  input_schema:
    type: object
    properties:
      document_ids:
        type: array
        items:
          type: string
      output_format:
        type: string
        enum: ["json", "csv", "xml"]
    required: [document_ids]

  nodes:
    # Process each document in parallel
    - id: process_documents
      type: map
      items: "{{workflow.input.document_ids}}"
      node: process_single_doc
      concurrency_limit: 5

    - id: process_single_doc
      type: agent
      agent_name: "DocumentProcessor"
      input:
        document_id: "{{_map_item}}"

    # Route based on overall success rate
    - id: check_results
      type: agent
      agent_name: "ResultAnalyzer"
      depends_on: [process_documents]
      input:
        results: "{{process_documents.output.results}}"

    - id: route_by_success
      type: switch
      depends_on: [check_results]
      cases:
        - condition: "{{check_results.output.success_rate}} >= 0.95"
          node: generate_report
        - condition: "{{check_results.output.success_rate}} >= 0.5"
          node: partial_report_with_errors
      default: escalate_failures

    - id: generate_report
      type: agent
      agent_name: "ReportGenerator"
      depends_on: [route_by_success]
      input:
        data: "{{process_documents.output.results}}"
        format: "{{workflow.input.output_format}}"

    - id: partial_report_with_errors
      type: agent
      agent_name: "ReportGenerator"
      depends_on: [route_by_success]
      input:
        data: "{{process_documents.output.results}}"
        format: "{{workflow.input.output_format}}"
        include_errors: true

    - id: escalate_failures
      type: agent
      agent_name: "EscalationHandler"
      depends_on: [route_by_success]
      input:
        failed_documents: "{{check_results.output.failures}}"

  on_exit:
    always: audit_log

  nodes:
    - id: audit_log
      type: agent
      agent_name: "AuditLogger"
      input:
        workflow_input: "{{workflow.input}}"
        timestamp: "{{workflow.start_time}}"

  output_mapping:
    report:
      coalesce:
        - "{{generate_report.output.report}}"
        - "{{partial_report_with_errors.output.report}}"
    success_rate: "{{check_results.output.success_rate}}"
    escalated: "{{escalate_failures.output.ticket_id}}"

  retry_strategy:
    limit: 2
    backoff:
      duration: "5s"
```

## Reference

For complete field documentation and the JSON Schema, see [Workflows](../components/workflows.md).
