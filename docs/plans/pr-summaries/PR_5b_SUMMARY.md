# PR 5b: Workflow Runtime - DAG Executor Core

## Overview

This PR introduces the core DAG execution logic including dependency graph management, the main execution loop, agent node execution, and conditional node execution. This is the heart of workflow orchestration.

## Branch Information

- **Branch Name:** `pr/workflows-5b-dag-core`
- **Target:** `pr/workflows-5a-orchestrator`

## Files Changed

### `src/solace_agent_mesh/workflow/dag_executor.py` (first ~700 lines)

The `DAGExecutor` class provides the core execution engine:

| Method/Area | Purpose |
|-------------|---------|
| `__init__()` | Build dependency graph from workflow definition |
| `_build_dependency_graph()` | Map node → dependencies |
| `_build_reverse_dependencies()` | Map node → dependents |
| `get_initial_nodes()` | Find entry points (no dependencies) |
| `get_next_nodes()` | Find nodes ready to execute |
| `validate_dag()` | Validate DAG structure |
| `_has_cycles()` | Cycle detection via DFS |
| `execute_workflow()` | Main execution loop |
| `execute_node()` | Dispatch to node-type handler |
| `_execute_agent_node()` | Execute agent invocation |
| `_execute_conditional_node()` | Execute binary branching |

#### Key Algorithms

**Dependency Graph Building:**
```python
dependencies = {
    "step2": ["step1"],
    "step3": ["step2"],
    "branch": ["step1"],
}
reverse_dependencies = {
    "step1": ["step2", "branch"],
    "step2": ["step3"],
    ...
}
```

**Execution Loop:**
```
1. Get nodes with all dependencies satisfied
2. For each ready node:
   a. Dispatch to type-specific handler
   b. Wait for completion
   c. Update state
3. Check completion criteria
4. Repeat until done
```

### `src/solace_agent_mesh/workflow/workflow_execution_context.py`

State management classes (~120 lines):

| Class | Purpose |
|-------|---------|
| `WorkflowExecutionState` | Pydantic model for execution state |
| `WorkflowExecutionContext` | Context object for tracking execution |

**WorkflowExecutionState fields:**
- `completed_nodes`: Node → artifact mapping
- `pending_nodes`: Currently executing nodes
- `node_outputs`: Cached outputs for template resolution
- `skipped_nodes`: Nodes skipped by conditionals
- `error_state`: Error tracking
- `loop_iterations`: Loop iteration counts
- `retry_counts`: Node retry counts

### `src/solace_agent_mesh/workflow/flow_control/conditional.py`

Conditional expression evaluation (~120 lines):

| Function | Purpose |
|----------|---------|
| `evaluate_condition()` | Safely evaluate condition expression |
| `_apply_template_aliases()` | Convert Argo syntax to SAM syntax |

Uses `simpleeval` for sandboxed expression evaluation.

### `src/solace_agent_mesh/workflow/utils.py`

Utility functions (~55 lines):
- Duration parsing (e.g., "30s", "5m")
- Template resolution helpers

## Key Concepts

### Node State Machine

```
PENDING → RUNNING → COMPLETED
                 ↘ FAILED
                 ↘ SKIPPED
```

### Template Resolution

Templates in node inputs are resolved from previous node outputs:

```yaml
input:
  query: "{{workflow.input.search_term}}"  # From workflow input
  data: "{{step1.output.results}}"         # From previous node
```

### Conditional Execution

```yaml
- id: branch
  type: conditional
  condition: "'{{step1.output.status}}' == 'success'"
  true_branch: success_handler
  false_branch: error_handler
```

The condition expression is evaluated using `simpleeval`:
- Template variables are resolved to their values
- Expression is safely evaluated
- Only the matching branch is marked ready

### Agent Node Execution

Agent nodes invoke agents via the AgentCaller:
1. Resolve input templates
2. Create input artifact
3. Send A2A message with StructuredInvocationRequest
4. Wait for StructuredInvocationResult
5. Store output in node_outputs

