# Prescriptive Workflows - Implementation Plan

**Status:** Draft
**Based on:** Detailed Design Document v1.0

This document outlines the step-by-step implementation plan for the Prescriptive Workflows feature. It breaks down the development into logical phases, starting from the core data structures and moving towards the orchestration engine and agent integration.

---

## Phase 1: Foundation & Data Structures

### Step 1: Directory Structure & Schemas
Create the necessary directory structure for the new workflow module and add the JSON schemas for the new A2A data parts.

1.  Create directory `src/solace_agent_mesh/workflow/`.
2.  Create subdirectories `src/solace_agent_mesh/workflow/flow_control/` and `src/solace_agent_mesh/workflow/protocol/`.
3.  Create directory `src/solace_agent_mesh/agent/sac/workflow_support/`.
4.  Create JSON Schema `src/solace_agent_mesh/common/a2a_spec/schemas/workflow_node_request.json` defining the structure for sending context to a persona agent.
5.  Create JSON Schema `src/solace_agent_mesh/common/a2a_spec/schemas/workflow_node_result.json` defining the structure for the persona agent's response.

### Step 2: A2A Data Models
Implement the Pydantic models for the new data parts to enable type-safe communication.

1.  Modify `src/solace_agent_mesh/common/data_parts.py` to include `WorkflowNodeRequestData` and `WorkflowNodeResultData` classes, inheriting from `BaseModel`.
2.  Update `src/solace_agent_mesh/common/a2a/__init__.py` to export these new models.

---

## Phase 2: Workflow Configuration & Application

### Step 3: Workflow Configuration Models
Define the Pydantic models that represent the workflow definition (YAML) structure.

1.  Create `src/solace_agent_mesh/workflow/app.py`.
2.  Define `WorkflowNode` base class and specific node types: `AgentNode`, `ConditionalNode`, `ForkNode`, `LoopNode`.
3.  Define `WorkflowDefinition` class to hold the list of nodes, input/output schemas, and mappings.
4.  Define `WorkflowAppConfig` class inheriting from `SamAgentAppConfig` to validate the application-level configuration.

### Step 4: WorkflowApp Implementation
Implement the application class that bootstraps the workflow executor.

1.  Implement `WorkflowApp` class in `src/solace_agent_mesh/workflow/app.py`.
2.  Implement `__init__` to parse and validate the `WorkflowAppConfig`.
3.  Implement logic to auto-populate the `AgentCard` schemas based on the workflow definition.
4.  Implement `_generate_subscriptions` to create the necessary Solace topic subscriptions (Discovery, Request, Response, Status).
5.  Implement logic to instantiate the `WorkflowExecutorComponent` with the validated config.

---

## Phase 3: Core Workflow Components

### Step 5: Execution Context & State
Implement the classes responsible for tracking the runtime state of a workflow.

1.  Create `src/solace_agent_mesh/workflow/workflow_execution_context.py`.
2.  Define `WorkflowExecutionState` Pydantic model for persistence (current node, completed nodes, outputs, errors).
3.  Define `WorkflowExecutionContext` class for in-memory tracking of active tasks, locks, and A2A context.

### Step 6: Persona Caller
Implement the component responsible for communicating with persona agents.

1.  Create `src/solace_agent_mesh/workflow/persona_caller.py`.
2.  Implement `PersonaCaller` class.
3.  Implement `call_persona` method to construct `WorkflowNodeRequestData` and publish the A2A message.
4.  Implement logic to generate unique sub-task IDs and track them in the execution context.
5.  Implement timeout tracking using the cache service.

---

## Phase 4: DAG Execution Engine

### Step 7: DAG Executor (Base & Sequential)
Implement the core graph traversal logic.

1.  Create `src/solace_agent_mesh/workflow/dag_executor.py`.
2.  Implement `DAGExecutor` class initialization (build dependency graph).
3.  Implement `validate_dag` to check for cycles and invalid references.
4.  Implement `get_next_nodes` to determine which nodes are ready to execute based on dependencies.
5.  Implement `execute_workflow` loop to drive the execution.
6.  Implement `_execute_agent_node` to delegate to `PersonaCaller`.
7.  Implement input mapping resolution (resolving `{{node.output}}` references).

### Step 8: Flow Control Logic
Implement the logic for non-sequential nodes.

1.  Create `src/solace_agent_mesh/workflow/flow_control/conditional.py` and implement safe expression evaluation.
2.  Update `DAGExecutor` to implement `_execute_conditional_node` (branch selection).
3.  Update `DAGExecutor` to implement `_execute_fork_node` (parallel execution and result merging).
4.  Update `DAGExecutor` to implement `_execute_loop_node` (iteration logic).

---

## Phase 5: Workflow Executor Component

### Step 9: WorkflowExecutorComponent
Implement the main component that ties everything together.

1.  Create `src/solace_agent_mesh/workflow/component.py`.
2.  Implement `WorkflowExecutorComponent` class inheriting from `SamComponentBase`.
3.  Implement initialization of `DAGExecutor`, `PersonaCaller`, and services.
4.  Implement `process_event` to route messages.
5.  Implement `handle_task_request` to start new workflow instances.
6.  Implement `handle_persona_response` to process results from agents and update the DAG state.
7.  Implement `handle_cancel_request` to handle workflow cancellation.
8.  Implement `handle_cache_expiry_event` to handle node timeouts.
9.  Implement state persistence using the Session Service.

---

## Phase 6: Agent Integration (Persona Support)

### Step 10: Workflow Node Handler
Implement the logic that allows a standard agent to act as a workflow node.

1.  Create `src/solace_agent_mesh/agent/sac/workflow_support/validator.py` for schema validation logic.
2.  Create `src/solace_agent_mesh/agent/sac/workflow_support/handler.py`.
3.  Implement `WorkflowNodeHandler` class.
4.  Implement `extract_workflow_context` to detect workflow requests.
5.  Implement `execute_workflow_node` to handle validation and execution.
6.  Implement `_inject_workflow_instructions` to modify the system prompt.
7.  Implement `_finalize_workflow_node_execution` to validate output artifacts and handle retries.

### Step 11: SamAgentComponent Integration
Hook the handler into the existing agent component.

1.  Modify `src/solace_agent_mesh/agent/sac/component.py` to initialize `WorkflowNodeHandler`.
2.  Modify `src/solace_agent_mesh/agent/protocol/event_handlers.py` in `handle_a2a_request` to check for workflow context and delegate to the handler if present.
3.  Ensure `SamAgentComponent` passes necessary configuration (schemas) to the handler.

---

## Phase 7: Cleanup & Finalization

### Step 12: Final Polish
1.  Review all error handling and logging.
2.  Ensure proper cleanup of resources in `cleanup` methods.
3.  Verify that `WorkflowApp` correctly exposes the component to the framework.
