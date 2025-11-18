# Prescriptive Workflows - Implementation Checklist

**Status:** In Progress
**Based on:** Implementation Plan v1.0

This document tracks the progress of the Prescriptive Workflows feature implementation.

---

## Phase 1: Foundation & Data Structures

- [ ] **Step 1: Directory Structure & Schemas**
    - [ ] Create directory `src/solace_agent_mesh/workflow/`
    - [ ] Create subdirectories `src/solace_agent_mesh/workflow/flow_control/` and `src/solace_agent_mesh/workflow/protocol/`
    - [ ] Create directory `src/solace_agent_mesh/agent/sac/workflow_support/`
    - [ ] Create JSON Schema `src/solace_agent_mesh/common/a2a_spec/schemas/workflow_node_request.json`
    - [ ] Create JSON Schema `src/solace_agent_mesh/common/a2a_spec/schemas/workflow_node_result.json`

- [ ] **Step 2: A2A Data Models**
    - [ ] Modify `src/solace_agent_mesh/common/data_parts.py` to include `WorkflowNodeRequestData` and `WorkflowNodeResultData`
    - [ ] Update `src/solace_agent_mesh/common/a2a/__init__.py` to export new models

## Phase 2: Workflow Configuration & Application

- [ ] **Step 3: Workflow Configuration Models**
    - [ ] Create `src/solace_agent_mesh/workflow/app.py`
    - [ ] Define `WorkflowNode` base class and specific node types (`AgentNode`, `ConditionalNode`, `ForkNode`, `LoopNode`)
    - [ ] Define `WorkflowDefinition` class
    - [ ] Define `WorkflowAppConfig` class

- [ ] **Step 4: WorkflowApp Implementation**
    - [ ] Implement `WorkflowApp` class in `src/solace_agent_mesh/workflow/app.py`
    - [ ] Implement `__init__` with config validation
    - [ ] Implement schema auto-population logic
    - [ ] Implement `_generate_subscriptions`
    - [ ] Implement component instantiation logic

## Phase 3: Core Workflow Components

- [ ] **Step 5: Execution Context & State**
    - [ ] Create `src/solace_agent_mesh/workflow/workflow_execution_context.py`
    - [ ] Define `WorkflowExecutionState` Pydantic model
    - [ ] Define `WorkflowExecutionContext` class

- [ ] **Step 6: Persona Caller**
    - [ ] Create `src/solace_agent_mesh/workflow/persona_caller.py`
    - [ ] Implement `PersonaCaller` class
    - [ ] Implement `call_persona` method
    - [ ] Implement sub-task ID generation and tracking
    - [ ] Implement timeout tracking

## Phase 4: DAG Execution Engine

- [ ] **Step 7: DAG Executor (Base & Sequential)**
    - [ ] Create `src/solace_agent_mesh/workflow/dag_executor.py`
    - [ ] Implement `DAGExecutor` initialization and dependency graph building
    - [ ] Implement `validate_dag`
    - [ ] Implement `get_next_nodes`
    - [ ] Implement `execute_workflow` loop
    - [ ] Implement `_execute_agent_node`
    - [ ] Implement input mapping resolution

- [ ] **Step 8: Flow Control Logic**
    - [ ] Create `src/solace_agent_mesh/workflow/flow_control/conditional.py`
    - [ ] Update `DAGExecutor` with `_execute_conditional_node`
    - [ ] Update `DAGExecutor` with `_execute_fork_node`
    - [ ] Update `DAGExecutor` with `_execute_loop_node`

## Phase 5: Workflow Executor Component

- [ ] **Step 9: WorkflowExecutorComponent**
    - [ ] Create `src/solace_agent_mesh/workflow/component.py`
    - [ ] Implement `WorkflowExecutorComponent` class
    - [ ] Implement initialization
    - [ ] Implement `process_event`
    - [ ] Implement `handle_task_request`
    - [ ] Implement `handle_persona_response`
    - [ ] Implement `handle_cancel_request`
    - [ ] Implement `handle_cache_expiry_event`
    - [ ] Implement state persistence

## Phase 6: Agent Integration (Persona Support)

- [ ] **Step 10: Workflow Node Handler**
    - [ ] Create `src/solace_agent_mesh/agent/sac/workflow_support/validator.py`
    - [ ] Create `src/solace_agent_mesh/agent/sac/workflow_support/handler.py`
    - [ ] Implement `WorkflowNodeHandler` class
    - [ ] Implement `extract_workflow_context`
    - [ ] Implement `execute_workflow_node`
    - [ ] Implement `_inject_workflow_instructions`
    - [ ] Implement `_finalize_workflow_node_execution`

- [ ] **Step 11: SamAgentComponent Integration**
    - [ ] Modify `src/solace_agent_mesh/agent/sac/component.py` to initialize handler
    - [ ] Modify `src/solace_agent_mesh/agent/protocol/event_handlers.py` to delegate to handler
    - [ ] Ensure configuration passing

## Phase 7: Cleanup & Finalization

- [ ] **Step 12: Final Polish**
    - [ ] Review error handling and logging
    - [ ] Ensure resource cleanup
    - [ ] Verify `WorkflowApp` exposure
