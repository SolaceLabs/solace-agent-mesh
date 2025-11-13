# Prescriptive Workflows - Detailed Design Document

**Document Version:** 1.0
**Date:** 2025-11-13
**Status:** Proposed

## 1. Introduction

### 1.1. Purpose

This document provides a detailed implementation plan for the Prescriptive Workflows feature, building upon the approved architecture documents (Parts 1-3). It outlines the specific code changes, new components, and module structure required to deliver the Minimum Viable Product (MVP).

### 1.2. Scope

This design document focuses on the implementation details for the MVP. It does not include test plans, performance benchmarks, or a visual designer, which will be addressed in subsequent phases.

## 2. High-Level Design Recap

The Prescriptive Workflows feature is built on the **"Workflows as Agents"** principle. From an external client's perspective, a workflow is indistinguishable from a regular agent. It is discovered, invoked, and communicates using the standard A2A protocol.

The architecture is composed of three main parts:
1.  **`WorkflowApp`**: The application entry point that handles configuration, validation, and initialization.
2.  **`WorkflowExecutorComponent`**: The core orchestration engine that executes the workflow DAG, calls persona agents, and manages state.
3.  **`WorkflowNodeHandler`**: An extension to the `SamAgentComponent` that allows a regular agent to act as a "persona" within a workflow, handling schema validation and retry logic.

State is managed via a `WorkflowExecutionState` model persisted in the ADK Session Service, and communication relies on the A2A protocol, extended with two new `DataPart` types.

## 3. Component Breakdown & Implementation Plan

This section details the new and modified components required to implement the feature.

### 3.1. A2A Protocol and Data Model Extensions

New Pydantic models and JSON schemas are required to facilitate communication between the workflow executor and persona agents.

-   **New Files**:
    -   `src/solace_agent_mesh/common/a2a_spec/schemas/workflow_node_request.json`: JSON Schema for the `WorkflowNodeRequestData` part.
    -   `src/solace_agent_mesh/common/a2a_spec/schemas/workflow_node_result.json`: JSON Schema for the `WorkflowNodeResultData` part.

-   **Modified Files**:
    -   `src/solace_agent_mesh/common/data_parts.py`:
        -   Add `WorkflowNodeRequestData(BaseModel)`: Contains `workflow_name`, `node_id`, and optional `input_schema`/`output_schema` overrides.
        -   Add `WorkflowNodeResultData(BaseModel)`: Contains `status` ('success'/'failure'), `artifact_name`, `artifact_version`, and optional `error_message`.
    -   `src/solace_agent_mesh/common/a2a/__init__.py`: Export the new `WorkflowNodeRequestData` and `WorkflowNodeResultData` models.

### 3.2. Workflow Application (`WorkflowApp`)

A new application class will be created to handle workflow-specific configuration and setup.

-   **New Files**:
    -   `src/solace_agent_mesh/workflow/app.py`: Will contain the `WorkflowApp` class and its Pydantic configuration models (`WorkflowAppConfig`, `WorkflowDefinition`, `WorkflowNode`, etc.).

-   **Responsibilities**:
    -   Extends `solace_ai_connector.flow.app.App`.
    -   Defines and validates the entire workflow configuration via a `WorkflowAppConfig` Pydantic model. This model will include the `workflow` definition, which contains the list of `nodes` and their properties.
    -   Programmatically creates a single `WorkflowExecutorComponent` instance, passing the validated configuration.
    -   Automatically generates the required Solace topic subscriptions for the workflow to receive requests and persona responses.
    -   Auto-populates the workflow's `AgentCard` with the `input_schema` and `output_schema` from the workflow definition.

### 3.3. Workflow Executor (`WorkflowExecutorComponent`)

This is the core orchestration engine. It will be a new component type, living in its own module.

-   **New Files**:
    -   `src/solace_agent_mesh/workflow/component.py`: Contains the main `WorkflowExecutorComponent` class.
    -   `src/solace_agent_mesh/workflow/dag_executor.py`: Contains the `DAGExecutor` class, responsible for graph traversal logic.
    -   `src/solace_agent_mesh/workflow/persona_caller.py`: Contains the `PersonaCaller` class for invoking persona agents.
    -   `src/solace_agent_mesh/workflow/workflow_execution_context.py`: Defines the `WorkflowExecutionContext` class for in-memory tracking.
    -   `src/solace_agent_mesh/workflow/protocol/event_handlers.py`: Contains handlers for incoming Solace messages.

-   **`WorkflowExecutorComponent` Responsibilities**:
    -   Extends `SamComponentBase`.
    -   `__init__`: Initializes the `DAGExecutor`, `PersonaCaller`, and an agent registry.
    -   `process_event`: The main event loop entry point, routing messages to specific handlers.
    -   `handle_task_request`: Initiates a new workflow run. Creates a `WorkflowExecutionContext` and a `WorkflowExecutionState`, saves the state to the session service, and starts the `DAGExecutor`.
    -   `handle_persona_response`: Correlates an incoming response from a persona agent to the correct node and informs the `DAGExecutor` of the node's completion.
    -   `handle_cancel_request`: Propagates a `tasks/cancel` request to all active persona calls for a given workflow instance.
    -   `handle_cache_expiry_event`: Handles node timeouts triggered by the cache service.
    -   `finalize_workflow_*`: Implements the final success or failure logic, publishing the final `Task` object to the client.

### 3.4. Agent Workflow Support (`WorkflowNodeHandler`)

To enable a standard `SamAgentComponent` to act as a persona, a new handler will be created and integrated.

-   **New Files**:
    -   `src/solace_agent_mesh/agent/sac/workflow_support/handler.py`: Contains the `WorkflowNodeHandler` class.
    -   `src/solace_agent_mesh/agent/sac/workflow_support/validator.py`: Contains schema validation helper functions.

-   **Modified Files**:
    -   `src/solace_agent_mesh/agent/sac/component.py`:
        -   In `__init__`, instantiate `self.workflow_handler = WorkflowNodeHandler(self)`.
    -   `src/solace_agent_mesh/agent/protocol/event_handlers.py`:
        -   In `handle_a2a_request`, add logic to call `self.workflow_handler.extract_workflow_context(message)`. If it returns data, delegate execution to `self.workflow_handler.execute_workflow_node(...)`. Otherwise, proceed with normal agent execution.
    -   `src/solace_agent_mesh/agent/adk/callbacks.py`:
        -   `inject_dynamic_instructions_callback` will be modified to accept and inject additional instructions when the agent is running in workflow mode.

-   **`WorkflowNodeHandler` Responsibilities**:
    -   `extract_workflow_context`: Parses the `WorkflowNodeRequestData` from an incoming `A2AMessage`.
    -   `execute_workflow_node`: The main entry point when an agent is called as a persona.
    -   `_validate_input`: Validates the incoming message against the `input_schema`. It will be designed to prioritize validating the content of the first `FilePart` if a schema is active.
    -   `_inject_workflow_instructions`: Creates and registers a `before_model_callback` to inject instructions into the LLM prompt regarding the required output format (JSON schema and `«result:...»` embed).
    -   `_finalize_workflow_node_execution`: Implemented as an `after_model_callback`, this will parse the `«result:...»` embed from the LLM's final output, validate the specified artifact against the `output_schema`, and trigger the retry loop if validation fails.
    -   `_return_workflow_result`: Constructs and sends the final `WorkflowNodeResultData` in a `Task` object back to the workflow executor's response topic.

### 3.5. Flow Control

Flow control logic will be implemented within the `DAGExecutor`.

-   **New Files**:
    -   `src/solace_agent_mesh/workflow/flow_control/conditional.py`: Contains the `evaluate_condition` logic using a safe evaluation library.

-   **Implementation within `DAGExecutor`**:
    -   `_execute_conditional_node`: Evaluates the `condition` expression. The DAG traversal logic will naturally skip the un-taken branch as its dependencies will never be met.
    -   `_execute_fork_node`: Concurrently launches all persona calls for the fork branches. It will track the completion of each branch. A failure in one branch will trigger cancellation requests to the others (with a configurable timeout) and fail the entire workflow.
    -   `_execute_loop_node`: Iterates over a list resolved from a value reference. For each item, it will create a lightweight, temporary context containing `_loop_item` and `_loop_index` and execute the loop's body node.

## 4. File and Module Structure

The new feature will be organized under a new `src/solace_agent_mesh/workflow/` directory.

```
src/solace_agent_mesh/
├── agent/
│   ├── sac/
│   │   ├── component.py              # Modified
│   │   └── workflow_support/         # New Directory
│   │       ├── __init__.py
│   │       ├── handler.py
│   │       └── validator.py
│   └── protocol/
│       └── event_handlers.py         # Modified
├── common/
│   ├── data_parts.py                 # Modified
│   ├── a2a/
│   │   ├── __init__.py               # Modified
│   │   └── types.py                  # Modified
│   └── a2a_spec/
│       └── schemas/
│           ├── workflow_node_request.json  # New File
│           └── workflow_node_result.json   # New File
└── workflow/                         # New Directory
    ├── __init__.py
    ├── app.py
    ├── component.py
    ├── dag_executor.py
    ├── persona_caller.py
    ├── workflow_execution_context.py
    ├── protocol/
    │   ├── __init__.py
    │   └── event_handlers.py
    └── flow_control/
        ├── __init__.py
        └── conditional.py
```

## 5. Key Implementation Details

This section confirms design decisions based on our recent discussion.

-   **Error Handling & Resilience**:
    -   **Cancellation**: `WorkflowExecutorComponent.handle_cancel_request` will find the active workflow and dispatch `tasks/cancel` requests to all in-flight persona calls for that instance.
    -   **Timeouts**: `PersonaCaller` will use the `cache_service` to set an expiry key for each sub-task. `WorkflowExecutorComponent.handle_cache_expiry_event` will handle the timeout, failing the workflow. A new `node_cancellation_timeout_seconds` config will be added to `WorkflowAppConfig` for managing fork/join cancellations.

-   **Data Flow & Performance**:
    -   **Large Artifacts**: The MVP will load node outputs into memory for input mapping. This is a known limitation, and support for reference-passing will be considered a future enhancement.
    -   **Loops**: The `_execute_loop_node` logic will create a lightweight, temporary context for each iteration, providing access only to the current loop item and index, avoiding deep-copying the entire workflow state.

-   **Schema Management**:
    -   **Versioning**: The documented operational procedure is that breaking changes to a persona's schema require deploying a new, uniquely named agent.
    -   **FilePart Validation**: The `_validate_input` method in `WorkflowNodeHandler` will be designed to prioritize validating the content of the first `FilePart` in a message when an `input_schema` is active.

## 6. MVP Scope and Limitations

-   **In Scope for MVP**:
    -   All core components: `WorkflowApp`, `WorkflowExecutorComponent`, `WorkflowNodeHandler`.
    -   Flow control: Sequential, Conditional (`if/else`), Parallel (`fork/join`), and Loops (`for-each`).
    -   Input and Output schema validation for persona agents, including the retry loop.
    -   Node timeouts and workflow cancellation.
    -   Composable workflows (workflows calling other workflows).

-   **Out of Scope for MVP**:
    -   `WorkflowExecutorComponent` crash recovery and resumption of in-flight workflows.
    -   A visual workflow designer or editor.
    -   Advanced schema versioning or automated translation between versions.
    -   Performance optimizations for passing very large artifacts between nodes (i.e., reference-passing).
    -   `case/switch` style conditional nodes.
