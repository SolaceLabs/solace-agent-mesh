# PR 4: Workflow Tool for Agents

## Overview

This PR provides an ADK Tool implementation that allows agents to invoke workflows as tools. This creates a bridge between LLM-driven agent orchestration and prescriptive workflows, enabling agents to call deterministic workflows when needed.

## Branch Information

- **Branch Name:** `pr/workflows-4-workflow-tool`
- **Target:** `pr/workflows-3-agent-support`

## Files Changed

### `src/solace_agent_mesh/agent/tools/workflow_tool.py`

The `WorkflowAgentTool` class (~370 lines) provides:

| Method | Purpose |
|--------|---------|
| `__init__()` | Initialize tool from workflow agent card |
| `_get_declaration()` | Generate ADK FunctionDeclaration from schema |
| `run_async()` | Main execution entry point |
| `_prepare_input_artifact()` | Create input artifact from args |
| `_prepare_a2a_message()` | Construct A2A message for workflow |
| `_submit_task()` | Send message and register for response |
| `_poll_for_result()` | Wait for workflow completion |

#### Key Features

- **Dynamic tool generation**: Tool definition is generated from workflow's input schema
- **Dual-mode invocation**: Supports both direct parameters and artifact reference
- **Long-running execution**: Uses ADK long-running tool pattern
- **Async polling**: Waits for workflow completion via correlation ID

### Tool Discovery Flow

When a workflow publishes its agent card with input/output schemas:

1. `SamAgentComponent` receives agent card via discovery
2. If agent card has schema extension, create `WorkflowAgentTool`
3. Tool is added to agent's available tools
4. LLM can now invoke the workflow via the tool

### Invocation Modes

```python
# Mode 1: Direct parameters
await workflow_process_order(
    customer_id="12345",
    items=["widget", "gadget"]
)

# Mode 2: Artifact reference
await workflow_process_order(
    input_artifact="order_data.json"
)
```

### Message Flow

```
1. Agent LLM decides to call workflow tool
2. Tool validates input against schema
3. Tool creates input artifact
4. Tool sends A2A message to workflow
5. Tool polls for response via correlation ID
6. Tool returns workflow output to agent
```

## Key Concepts

### Tool Naming Convention

Workflow tools are named with prefix `workflow_`:
```
workflow_process_order
workflow_data_pipeline
```

### Correlation for Response Matching

Sub-task correlation IDs link requests to responses:
```
a2a_subtask_<uuid>
```

### Schema-to-ADK Translation

The tool dynamically converts JSON Schema to ADK types:

| JSON Schema Type | ADK Type |
|-----------------|----------|
| `string` | `Type.STRING` |
| `integer` | `Type.INTEGER` |
| `number` | `Type.NUMBER` |
| `boolean` | `Type.BOOLEAN` |
| `array` | `Type.ARRAY` |
| `object` | `Type.OBJECT` |

