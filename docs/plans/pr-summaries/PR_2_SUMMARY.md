# PR 2: Workflow Definition Models

## Overview

This PR introduces the Pydantic models that define the YAML schema for workflow definitions. These models provide Argo Workflows-compatible syntax with SAM extensions, enabling users to define deterministic, structured workflow DAGs.

## Branch Information

- **Branch Name:** `pr/workflows-2-models`
- **Target:** `pr/workflows-1-foundation`

## Files Changed

### `src/solace_agent_mesh/workflow/app.py`

Complete workflow definition model hierarchy:

#### Retry & Exit Handlers

| Model | Purpose |
|-------|---------|
| `BackoffStrategy` | Exponential backoff configuration for retries |
| `RetryStrategy` | Retry configuration (limit, policy, backoff) |
| `ExitHandler` | Cleanup/notification on workflow completion |

#### Node Types

| Model | Purpose |
|-------|---------|
| `WorkflowNode` | Base node class with id, type, depends_on |
| `AgentNode` | Invoke an agent with input/output schemas |
| `ConditionalNode` | Binary if/else branching |
| `SwitchNode` | Multi-way branching (first match wins) |
| `SwitchCase` | Individual case in switch node |
| `LoopNode` | While-loop iteration until condition false |
| `MapNode` | Parallel for-each iteration over items |

#### Workflow Definition & Configuration

| Model | Purpose |
|-------|---------|
| `WorkflowDefinition` | Complete workflow DAG with nodes, schemas, exit handlers |
| `WorkflowAppConfig` | App configuration extending SamAgentAppConfig |
| `WorkflowApp` | Custom App class for workflow orchestration |

### `src/solace_agent_mesh/workflow/__init__.py`

Package initialization and exports.

## Key Concepts

### Argo Workflows Compatibility

The models support Argo-style field names via aliases:

```yaml
# Both syntaxes work:
depends_on: [step1]      # SAM style
dependencies: [step1]     # Argo style

true_branch: step2        # SAM style
trueBranch: step2         # Argo style
```

### Node Type Summary

| Type | Use Case | Key Fields |
|------|----------|------------|
| `agent` | Call an agent | `agent_name`, `input`, `when`, `retry_strategy` |
| `conditional` | Binary branch | `condition`, `true_branch`, `false_branch` |
| `switch` | Multi-way branch | `cases[]`, `default` |
| `loop` | While iteration | `node`, `condition`, `max_iterations` |
| `map` | For-each parallel | `items`, `node`, `concurrency_limit` |

### DAG Validation

`WorkflowDefinition.validate_dag_structure()` ensures:
- All node references are valid
- Branch targets depend on their parent node
- Exit handler references exist
- No configuration contradictions

### Template Expression Syntax

Input mappings use template expressions:

```yaml
input:
  query: "{{workflow.input.search_term}}"
  data: "{{previous_node.output.results}}"
```

