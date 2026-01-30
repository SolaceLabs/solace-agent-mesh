---
title: Creating Workflows
sidebar_position: 425
---

# Creating Workflows

This guide walks through building workflows that orchestrate multiple agents. You'll learn how to define execution sequences, pass data between nodes, handle branching logic, and process collections.

## Prerequisites

Before creating workflows, you need:
- A running Solace Agent Mesh instance
- The shared configuration file [`examples/shared_config.yaml`](https://github.com/SolaceDev/solace-agent-mesh/blob/main/examples/shared_config.yaml) which defines broker connections, LLM models, and service configurations
- Familiarity with YAML configuration files

## Your First Workflow

Create a file called `text_analysis_workflow.yaml`. This workflow calls two agents in sequence: one to analyze text and another to summarize the analysis.

Note that for simplicity the **agents and workflows are defined in the same file below**. While this is convenient for examples, in production you might separate them. The workflow references agents by their `agent_name`, and everything runs together.

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: text_analysis_workflow.log

# Import shared configuration (broker, models, services)
# Note that this file is in the examples/ directory
!include ../shared_config.yaml

apps:
  # ============================================================================
  # AGENT: Text Analyzer
  # Analyzes text and identifies key themes
  # ============================================================================
  - name: text_analyzer_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "TextAnalyzer"
      model: *planning_model

      instruction: |
        You analyze text content.
        1. Read the 'content' from input
        2. Identify key themes, sentiment, and notable phrases

      # Note that input_schema can be optionally defined in the agent config
      # and overridden in the workflow if desired.
      input_schema:
        type: object
        properties:
          content: {type: string, description: "Text to analyze"}
        required: [content]

      # Note that output_schema can be optionally defined in the agent config
      # and overridden in the workflow if desired.
      output_schema:
        type: object
        properties:
          themes: {type: array, items: {type: string}}
          sentiment: {type: string}
          word_count: {type: integer}
        required: [themes, sentiment]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Analyzes text content for themes and sentiment"
        skills: [{id: "analyze", name: "Analyze Text", description: "Analyzes text", tags: ["analysis"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  # ============================================================================
  # AGENT: Summarizer
  # Creates summaries from analysis results
  # ============================================================================
  - name: summarizer_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "Summarizer"
      model: *planning_model

      instruction: |
        You create summaries from analysis results.
        1. Read the 'analysis' from input
        2. Create a concise summary highlighting key points

      input_schema:
        type: object
        properties:
          analysis: {type: object, description: "Analysis results to summarize"}
        required: [analysis]

      output_schema:
        type: object
        properties:
          summary: {type: string}
          key_points: {type: array, items: {type: string}}
        required: [summary, key_points]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Creates summaries from analysis"
        skills: [{id: "summarize", name: "Summarize", description: "Summarizes content", tags: ["summary"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  # ============================================================================
  # WORKFLOW: Text Analysis Pipeline
  # Orchestrates the analysis and summarization agents
  # ============================================================================
  - name: text_analysis_workflow
    app_base_path: .
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
              max_points: 5
            # Override the agent's default input_schema for this workflow.
            # This adds a 'max_points' field that the agent doesn't normally expect.
            input_schema:
              type: object
              properties:
                analysis: {type: object, description: "Analysis results to summarize"}
                max_points: {type: integer, description: "Maximum number of key points to return"}
              required: [analysis]
            # Additional instructions for this workflow invocation
            instruction: "Limit the key_points array to at most `max_points` items."

        output_mapping:
          summary: "{{summarize.output.summary}}"
          key_points: "{{summarize.output.key_points}}"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}
```

Key points:
- The `!include` directive imports shared configuration with broker, model, and service definitions
- Both agents and the workflow are in the same `apps` list
- The workflow uses `app_module: solace_agent_mesh.workflow.app`
- `depends_on: [analyze]` ensures `summarize` waits for `analyze` to complete
- Template expressions like `{{analyze.output}}` pass data between nodes
- The `summarize` node overrides the agent's `input_schema` to add a `max_points` field—useful when a workflow needs different input than what the agent defines by default
- The `instruction` field on the `summarize` node provides additional context to the agent for this specific workflow invocation

## Running a Workflow

Run the workflow file directly:

```bash
sam run text_analysis_workflow.yaml
```

Workflows register as agents, so you can invoke them the same way you'd invoke any agent. The workflow appears in the UI's agent list and can be triggered through any gateway.

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

Switch nodes route execution based on data values. Here's a complete example. Save this as `request_router_workflow.yaml`:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: request_router_workflow.log

!include ../shared_config.yaml

apps:
  # ============================================================================
  # AGENT: Request Classifier
  # ============================================================================
  - name: classifier_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "RequestClassifier"
      model: *planning_model

      instruction: |
        Classify the incoming request.
        1. Read the 'request' text
        2. Determine the type: "billing", "technical", or "general"
        3. Assess urgency: "high", "medium", or "low"

      input_schema:
        type: object
        properties:
          request: {type: string}
        required: [request]

      output_schema:
        type: object
        properties:
          type: {type: string, enum: ["billing", "technical", "general"]}
          urgency: {type: string, enum: ["high", "medium", "low"]}
        required: [type, urgency]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Classifies support requests"
        skills: [{id: "classify", name: "Classify Request", description: "Classifies requests", tags: ["classification"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  # ============================================================================
  # AGENTS: Handlers for each request type
  # ============================================================================
  - name: billing_handler_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "BillingHandler"
      model: *planning_model

      instruction: |
        Handle billing-related requests.
        1. Read the 'request' text
        2. Generate an appropriate response

      input_schema:
        type: object
        properties:
          request: {type: string}
        required: [request]

      output_schema:
        type: object
        properties:
          response: {type: string}
          handler: {type: string}
        required: [response, handler]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Handles billing requests"
        skills: [{id: "billing", name: "Handle Billing", description: "Billing support", tags: ["billing"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  - name: technical_handler_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "TechnicalHandler"
      model: *planning_model

      instruction: |
        Handle technical support requests.
        1. Read the 'request' text
        2. Generate an appropriate technical response

      input_schema:
        type: object
        properties:
          request: {type: string}
        required: [request]

      output_schema:
        type: object
        properties:
          response: {type: string}
          handler: {type: string}
        required: [response, handler]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Handles technical requests"
        skills: [{id: "technical", name: "Handle Technical", description: "Technical support", tags: ["technical"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  - name: general_handler_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "GeneralHandler"
      model: *planning_model

      instruction: |
        Handle general inquiries.
        1. Read the 'request' text
        2. Generate a helpful response

      input_schema:
        type: object
        properties:
          request: {type: string}
        required: [request]

      output_schema:
        type: object
        properties:
          response: {type: string}
          handler: {type: string}
        required: [response, handler]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Handles general inquiries"
        skills: [{id: "general", name: "Handle General", description: "General support", tags: ["general"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  # ============================================================================
  # WORKFLOW: Request Router
  # ============================================================================
  - name: request_router_workflow
    app_base_path: .
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "RequestRouterWorkflow"

      workflow:
        description: "Routes support requests to appropriate handlers"

        input_schema:
          type: object
          properties:
            request:
              type: string
              description: "The support request text"
          required: [request]

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
            default: handle_general

          - id: handle_billing
            type: agent
            agent_name: "BillingHandler"
            depends_on: [route_request]
            input:
              request: "{{workflow.input.request}}"

          - id: handle_technical
            type: agent
            agent_name: "TechnicalHandler"
            depends_on: [route_request]
            input:
              request: "{{workflow.input.request}}"

          - id: handle_general
            type: agent
            agent_name: "GeneralHandler"
            depends_on: [route_request]
            input:
              request: "{{workflow.input.request}}"

        output_mapping:
          response:
            coalesce:
              - "{{handle_billing.output.response}}"
              - "{{handle_technical.output.response}}"
              - "{{handle_general.output.response}}"
          handled_by:
            coalesce:
              - "{{handle_billing.output.handler}}"
              - "{{handle_technical.output.handler}}"
              - "{{handle_general.output.handler}}"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}
```

Cases are evaluated top to bottom. The first matching condition wins. Nodes in non-selected branches are skipped entirely.

Notice that branch nodes must list the switch node in their `depends_on`. This ensures they only run when selected.

## Processing Collections

Map nodes iterate over arrays. Each item is processed by the target node. Save this as `batch_processor_workflow.yaml`:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: batch_processor_workflow.log

!include ../shared_config.yaml

apps:
  # ============================================================================
  # AGENT: Item Processor
  # Processes individual items from a batch
  # ============================================================================
  - name: item_processor_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "ItemProcessor"
      model: *planning_model

      instruction: |
        Process a single item from a batch.
        1. Read 'item_id', 'quantity', and 'price' from input
        2. Calculate line_total = quantity * price

      input_schema:
        type: object
        properties:
          item_id: {type: string}
          quantity: {type: integer}
          price: {type: number}
        required: [item_id, quantity, price]

      output_schema:
        type: object
        properties:
          item_id: {type: string}
          line_total: {type: number}
          processed: {type: boolean}
        required: [item_id, line_total, processed]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Processes individual items"
        skills: [{id: "process", name: "Process Item", description: "Processes items", tags: ["processing"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  # ============================================================================
  # WORKFLOW: Batch Processor
  # ============================================================================
  - name: batch_processor_workflow
    app_base_path: .
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "BatchProcessorWorkflow"

      workflow:
        description: "Processes a batch of items in parallel"

        input_schema:
          type: object
          properties:
            items:
              type: array
              items:
                type: object
                properties:
                  item_id: {type: string}
                  quantity: {type: integer}
                  price: {type: number}
                required: [item_id, quantity, price]
          required: [items]

        nodes:
          - id: process_all_items
            type: map
            items: "{{workflow.input.items}}"
            node: process_single_item
            concurrency_limit: 3
            max_items: 50

          - id: process_single_item
            type: agent
            agent_name: "ItemProcessor"
            input:
              item_id: "{{_map_item.item_id}}"
              quantity: "{{_map_item.quantity}}"
              price: "{{_map_item.price}}"

        output_mapping:
          processed_items: "{{process_all_items.output.results}}"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}
```

Inside the target node, `{{_map_item}}` is the current item. After all iterations complete, the map node's output contains `results`—an array of each iteration's output in order.

Set `concurrency_limit` to control parallelism. Without it, all items process simultaneously.

## Polling with Loops

Loop nodes repeat until a condition becomes false. Use them for polling or retry patterns. Save this as `polling_workflow.yaml`:

```yaml
log:
  stdout_log_level: INFO
  log_file_level: DEBUG
  log_file: polling_workflow.log

!include ../shared_config.yaml

apps:
  # ============================================================================
  # AGENT: Status Checker
  # Checks if a task is ready (simulates polling an external service)
  # ============================================================================
  - name: status_checker_app
    app_base_path: .
    app_module: solace_agent_mesh.agent.sac.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "StatusChecker"
      model: *planning_model

      instruction: |
        Check if a task is ready.
        1. Read 'task_id' and 'iteration' from input
        2. Simulate checking: if iteration >= 3, set ready = true

      input_schema:
        type: object
        properties:
          task_id: {type: string}
          iteration: {type: integer}
        required: [task_id, iteration]

      output_schema:
        type: object
        properties:
          task_id: {type: string}
          iteration: {type: integer}
          ready: {type: boolean}
          message: {type: string}
        required: [task_id, ready]

      tools:
        - tool_type: builtin-group
          group_name: "artifact_management"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card:
        description: "Checks task status"
        skills: [{id: "check", name: "Check Status", description: "Checks status", tags: ["status"]}]
      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}

  # ============================================================================
  # WORKFLOW: Polling Workflow
  # ============================================================================
  - name: polling_workflow
    app_base_path: .
    app_module: solace_agent_mesh.workflow.app
    broker:
      <<: *broker_connection

    app_config:
      namespace: ${NAMESPACE}
      agent_name: "PollingWorkflow"

      workflow:
        description: "Polls until a task is ready"

        input_schema:
          type: object
          properties:
            task_id:
              type: string
              description: "Task to poll for"
          required: [task_id]

        nodes:
          - id: poll_until_ready
            type: loop
            node: check_status
            condition: "{{check_status.output.ready}} == false"
            max_iterations: 10
            delay: "5s"

          - id: check_status
            type: agent
            agent_name: "StatusChecker"
            input:
              task_id: "{{workflow.input.task_id}}"
              iteration: "{{_loop_iteration}}"

        output_mapping:
          task_id: "{{workflow.input.task_id}}"
          final_status: "{{check_status.output.ready}}"
          iterations: "{{poll_until_ready.output.iterations_completed}}"

      session_service:
        <<: *default_session_service
      artifact_service:
        <<: *default_artifact_service

      agent_card_publishing: {interval_seconds: 10}
      agent_discovery: {enabled: false}
```

The loop runs `check_status` repeatedly. The first iteration always executes; the condition is checked before each subsequent iteration. Once the condition is false (task ready), execution continues.

The `delay` adds a wait between iterations—essential for polling to avoid overwhelming the target service.

## Composing Workflows

Workflow nodes call other workflows as sub-workflows:

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
        workflow_input: "{{workflow.input}}"

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

## Example Workflows

The repository includes complete example workflows:

- [`examples/agents/all_node_types_workflow.yaml`](https://github.com/SolaceLabs/solace-agent-mesh/blob/main/examples/agents/all_node_types_workflow.yaml) - Comprehensive example demonstrating all node types in an order processing pipeline
- [`examples/agents/jira_bug_triage_workflow.yaml`](https://github.com/SolaceLabs/solace-agent-mesh/blob/main/examples/agents/jira_bug_triage_workflow.yaml) - Real-world example of a bug triage workflow with conditional branching

## Reference

For complete field documentation and the JSON Schema, see [Workflows](../components/workflows.md).
