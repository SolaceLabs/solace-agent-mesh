# PR 3: Structured Invocation Support

## Overview

This PR enables agents to be invoked with schema-validated input/output, functioning as a "structured function call" pattern. This is used by workflows and other programmatic callers that need predictable, validated responses from agents.

## Branch Information

- **Branch Name:** `pr/workflows-3-agent-support`
- **Target:** `pr/workflows-2-models`

## Files Changed

### `src/solace_agent_mesh/agent/sac/structured_invocation/handler.py`

The `StructuredInvocationHandler` class (~1,100 lines) provides:

| Method | Purpose |
|--------|---------|
| `extract_structured_invocation_context()` | Detect if message is a structured invocation |
| `execute_structured_invocation()` | Main entry point for structured execution |
| `_extract_input_data()` | Extract input from message parts |
| `_execute_with_output_validation()` | Run agent and validate output |
| `_parse_result_embed()` | Extract result artifact from agent output |
| `_return_structured_result()` | Send StructuredInvocationResult response |

#### Key Features

- **Input extraction**: Handles text input, JSON/YAML/CSV file parts, and artifact URIs
- **Schema validation**: Validates input before execution, output after
- **Output retry**: Re-prompts agent if output fails validation (configurable retries)
- **Result embed pattern**: Agents signal completion via `«result:artifact=output.json»` embed
- **Error handling**: Catches exceptions and returns structured failure result

### `src/solace_agent_mesh/agent/sac/structured_invocation/validator.py`

Simple JSON Schema validation using `jsonschema` library:

```python
def validate_against_schema(data: Any, schema: Dict[str, Any]) -> Optional[List[str]]:
    """Validate data against JSON schema. Returns error list or None."""
```

### `src/solace_agent_mesh/agent/sac/component.py` (modifications)

Integration of structured invocation into the agent component:

- Check incoming messages for `StructuredInvocationRequest` data part
- Route to handler if detected
- Fall back to normal agent processing otherwise

### `src/solace_agent_mesh/agent/sac/app.py` (modifications)

New configuration fields:

- `input_schema`: Default input schema for agent
- `output_schema`: Default output schema for agent
- `validation_max_retries`: Max retries on output validation failure

## Key Concepts

### Structured Invocation Flow

```
1. Caller sends A2A message with StructuredInvocationRequest data part
2. Agent extracts invocation context
3. Agent validates input against schema
4. Agent executes with structured prompt
5. Agent validates output against schema
6. If output invalid, retry with correction prompt (up to max_retries)
7. Agent returns StructuredInvocationResult with artifact reference
```

### Result Embed Pattern

Agents signal their structured output via a special embed format:

```
«result:artifact=output.json status=success»
```

The handler parses this to locate the output artifact for validation.

### Schema Override Hierarchy

1. Schema in `StructuredInvocationRequest` (highest priority)
2. Schema in agent card extensions
3. Schema in agent configuration
4. Default text schema (fallback)

