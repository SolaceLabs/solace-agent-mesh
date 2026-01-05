# PR 1: Foundation - Data Models & Constants

## Overview

This PR introduces the foundational data models and utilities required by the Workflows feature. These are shared across all workflow components and define the contract for workflow-related A2A communication.

## Branch Information

- **Branch Name:** `pr/workflows-1-foundation`
- **Target:** `feature/prescriptive-workflows`

## Files Changed

### `src/solace_agent_mesh/common/data_parts.py`

New Pydantic models for workflow messages:

| Model | Purpose |
|-------|---------|
| `StructuredInvocationRequest` | Request for schema-validated agent invocation |
| `StructuredInvocationResult` | Response from schema-validated agent execution |
| `ArtifactRef` | Reference to an artifact (name + version) |
| `WorkflowExecutionStartData` | Signals workflow execution start |
| `WorkflowNodeExecutionStartData` | Signals node execution start (with node-type-specific fields) |
| `WorkflowNodeExecutionResultData` | Signals node execution completion |
| `WorkflowMapProgressData` | Progress updates for map node iterations |
| `WorkflowExecutionResultData` | Signals workflow execution completion |
| `SwitchCaseInfo` | Case information for switch nodes |

### `src/solace_agent_mesh/common/constants.py`

New constants:
- `EXTENSION_URI_SCHEMAS` - URI for schema extension in agent cards
- `EXTENSION_URI_AGENT_TYPE` - URI for agent type extension

### `src/solace_agent_mesh/common/a2a/types.py`

New type definitions:
- `SchemasExtensionParams` - Parameters for schema extension in agent cards

### `src/solace_agent_mesh/common/a2a/__init__.py`

Re-exports:
- `StructuredInvocationRequest`
- `StructuredInvocationResult`

### `src/solace_agent_mesh/common/agent_card_utils.py`

New utility:
- `get_schemas_from_agent_card()` - Extract input/output schemas from agent card extensions

## Key Concepts

### Structured Invocation Pattern

The `StructuredInvocationRequest` and `StructuredInvocationResult` models enable a "function call" pattern for agents:

1. Caller sends `StructuredInvocationRequest` with input data and optional schemas
2. Agent validates input, executes, validates output
3. Agent returns `StructuredInvocationResult` with artifact reference or error

This pattern is used by workflows but is generic enough for any programmatic caller.

### Workflow Visualization Events

The `WorkflowNode*` data models provide real-time execution visibility:

- Start events include node type, input artifact, and type-specific metadata
- Result events include status, output artifact, and error details
- Map progress events track iteration progress

