# PR 5c: Workflow Runtime - Advanced Node Types

## Overview

This PR completes the DAG executor with advanced node types: switch (multi-way branching), loop (while iteration), and map (parallel for-each). It also includes the AgentCaller for A2A communication with agents.

## Branch Information

- **Branch Name:** `pr/workflows-5c-advanced-nodes`
- **Target:** `pr/workflows-5b-dag-core`

## Files Changed

### `src/solace_agent_mesh/workflow/dag_executor.py` (lines ~700-1382)

Advanced node execution methods:

| Method | Purpose |
|--------|---------|
| `_execute_switch_node()` | Multi-way branching (first match wins) |
| `_execute_loop_node()` | While-loop iteration |
| `_execute_map_node()` | Parallel for-each iteration |
| `_launch_map_iterations()` | Launch map iterations with concurrency |
| `_skip_branch()` | Mark unexecuted branches as skipped |
| `resolve_value()` | Resolve template expressions |
| `handle_node_completion()` | Process node completion, trigger next nodes |
| `_finalize_map_node()` | Aggregate map results |

### `src/solace_agent_mesh/workflow/agent_caller.py`

Agent invocation via A2A (~370 lines):

| Method | Purpose |
|--------|---------|
| `call_agent()` | Main entry point for agent invocation |
| `_resolve_node_input()` | Resolve input templates |
| `_construct_agent_message()` | Build A2A message |
| `_create_input_artifact()` | Store input as artifact |
| `_publish_agent_request()` | Send message via broker |

## Key Concepts

### Switch Node Execution

Multi-way branching evaluates cases in order:

```yaml
- id: router
  type: switch
  cases:
    - when: "'{{step1.output.type}}' == 'urgent'"
      then: urgent_handler
    - when: "'{{step1.output.type}}' == 'normal'"
      then: normal_handler
  default: fallback_handler
```

```
1. Evaluate each case condition in order
2. First matching case wins
3. Non-matching branches are marked SKIPPED
4. If no match, use default (or skip all)
```

### Loop Node Execution

While-loop with "do-while" semantics:

```yaml
- id: retry_loop
  type: loop
  node: retry_attempt
  condition: "'{{retry_attempt.output.status}}' != 'success'"
  max_iterations: 5
  delay: "5s"
```

```
1. First iteration runs unconditionally
2. After each iteration, evaluate condition
3. Continue while condition is true
4. Apply delay between iterations
5. Stop at max_iterations
```

**Iteration tracking:**
- `_loop_iteration`: Current iteration index
- Results from each iteration update node outputs

### Map Node Execution

Parallel for-each with concurrency control:

```yaml
- id: process_items
  type: map
  items: "{{step1.output.items}}"
  node: process_single
  concurrency_limit: 3
  max_items: 100
```

```
1. Resolve items array from template
2. Initialize map state (pending, active, completed)
3. Launch iterations up to concurrency_limit
4. As iterations complete, launch more
5. When all complete, aggregate results
```

**Iteration context:**
- `_map_item`: Current item being processed
- `_map_index`: Index of current item
- Each iteration gets unique node ID: `process_items_0`, `process_items_1`, etc.

### Value Resolution

The `resolve_value()` method handles:

1. **Simple templates**: `"{{step1.output.field}}"`
2. **Nested paths**: `"{{step1.output.data.items[0].name}}"`
3. **Special variables**:
   - `workflow.input.*`: Workflow input data
   - `_map_item`: Current map iteration item
   - `_map_index`: Current map iteration index
   - `_loop_iteration`: Current loop iteration

### Node Completion Handling

`handle_node_completion()` processes agent responses:

1. Match response to node via correlation ID
2. Extract result from `StructuredInvocationResult`
3. Store output in `node_outputs`
4. Mark node as completed
5. For map nodes: aggregate results, check if all done
6. For loop nodes: re-evaluate condition, continue or stop
7. Trigger `execute_workflow()` to process next nodes

### Agent Caller Flow

```
1. Resolve input templates
2. Get schemas from agent card
3. Create input artifact
4. Build A2A message with:
   - StructuredInvocationRequest data part
   - FilePart referencing input artifact
5. Publish to agent request topic
6. Track correlation ID
```

