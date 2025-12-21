# Prescriptive Workflows Feature - Incremental Merge Strategy

## Feature Overview

The `ed/prescriptive-workflows` branch introduces a comprehensive "Prescriptive Workflows" feature that enables defining and executing structured, deterministic workflows as an alternative to purely agent-driven orchestration.

**Stats:** 107 files changed, ~30,000 lines added

---

## High-Level Components

### 1. **Core Workflow Runtime** (~4,100 lines)
Location: `src/solace_agent_mesh/workflow/`

| File | Lines | Purpose |
|------|-------|---------|
| `app.py` | 619 | Workflow definition models (Pydantic), node types, configuration |
| `component.py` | 1087 | WorkflowExecutorComponent - main orchestrator |
| `dag_executor.py` | 1382 | DAG execution engine, dependency resolution |
| `agent_caller.py` | 373 | Agent invocation via A2A protocol |
| `workflow_execution_context.py` | 120 | Execution state management |
| `flow_control/conditional.py` | 119 | Condition evaluation (simpleeval) |
| `protocol/event_handlers.py` | 345 | A2A message handling |
| `utils.py` | 55 | Utility functions |

**Node Types Supported:**
- `AgentNode` - Invoke an agent
- `ConditionalNode` - Binary branching (if/else)
- `SwitchNode` - Multi-way branching
- `LoopNode` - While-loop iteration
- `MapNode` - Parallel for-each iteration

**dag_executor.py breakdown (1382 lines):**
- Lines 1-200: Classes, dependency graph building, validation
- Lines 200-500: `execute_workflow()`, `execute_node()`, `_execute_agent_node()`
- Lines 500-850: `_execute_conditional_node()`, `_execute_switch_node()`, `_execute_loop_node()`
- Lines 850-1100: `_execute_map_node()`, `_launch_map_iterations()`, `resolve_value()`
- Lines 1100-1382: `handle_node_completion()`, finalization

**component.py breakdown (1087 lines):**
- Lines 1-180: Setup, message handling, initialization
- Lines 180-480: Agent card generation, Mermaid diagram
- Lines 480-700: Event publishing, exit handlers
- Lines 700-1087: Workflow finalization, output construction, cleanup

### 2. **Structured Invocation Support** (~1,700 lines)
Location: `src/solace_agent_mesh/agent/`

| File | Lines | Purpose |
|------|-------|---------|
| `sac/structured_invocation/handler.py` | 1163 | StructuredInvocationHandler - enables agents to be invoked with schema validation |
| `sac/structured_invocation/validator.py` | 29 | Schema validation |
| `tools/workflow_tool.py` | 453 | ADK Tool for invoking workflows from agents |
| `sac/component.py` | +125 | Modifications to SamAgentComponent |

### 3. **Common/Shared Components** (~300 lines)
Location: `src/solace_agent_mesh/common/`

| File | Changes | Purpose |
|------|---------|---------|
| `data_parts.py` | +246 | New data models for workflow messages |
| `constants.py` | +6 | New constants |
| `a2a/__init__.py` | +6 | A2A type additions |
| `a2a/types.py` | +9 | A2A types |
| `agent_card_utils.py` | +35 | Agent card utilities |

### 4. **Frontend Visualization** (~6,500 lines)
Location: `client/webui/frontend/src/lib/components/activities/FlowChart/`

| File | Lines | Purpose |
|------|-------|---------|
| `FlowChartPanel.tsx` | 177 | Main panel component |
| `WorkflowRenderer.tsx` | 358 | SVG workflow renderer |
| `EdgeLayer.tsx` | 172 | Edge/connection rendering |
| `NodeDetailsCard.tsx` | 1006 | Node details sidebar |
| `utils/layoutEngine.ts` | 1448 | Layout algorithm |
| `utils/nodeDetailsHelper.ts` | 416 | Node details extraction |
| `utils/types.ts` | 125 | TypeScript types |
| **Node components:** | |
| `nodes/AgentNode.tsx` | 289 | Agent node rendering |
| `nodes/WorkflowGroup.tsx` | 373 | Group/container rendering |
| `nodes/MapNode.tsx` | 175 | Map node rendering |
| `nodes/LoopNode.tsx` | 159 | Loop node rendering |
| `nodes/ConditionalNode.tsx` | 63 | Conditional rendering |
| `nodes/SwitchNode.tsx` | 70 | Switch node rendering |

### 5. **Supporting Frontend Changes** (~700 lines)
| File | Purpose |
|------|---------|
| `index.ts` | Activity component exports |
| `taskVisualizerProcessor.ts` | Process workflow visualization data |
| `VisualizerStepCard.tsx` | Step card component |
| `types/activities.ts` | New activity types |
| `providers/ChatProvider.tsx` | Provider updates |
| `providers/TaskProvider.tsx` | Provider updates |

### 7. **Documentation** - TO BE REWRITTEN
All existing design docs will be removed and replaced with focused PR-specific documentation.

### 8. **Examples** (~1,700 lines)
| File | Purpose |
|------|---------|
| `examples/agents/all_node_types_workflow.yaml` | Comprehensive example with all node types |
| `examples/agents/jira_bug_triage_workflow.yaml` | Real-world bug triage example |

### 9. **Tests** (~4,300 lines)
| File | Purpose |
|------|---------|
| `tests/unit/workflow/*.py` | Unit tests for pure functions (~1,770 lines) |
| `tests/integration/scenarios_programmatic/test_workflow_errors.py` | Integration tests (~2,000 lines) |
| `tests/integration/scenarios_declarative/test_data/workflows/*.yaml` | Declarative test workflows (~550 lines) |

---

## Dependency Analysis

```
                    ┌──────────────────┐
                    │  data_parts.py   │ (Foundation)
                    │  constants.py    │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌──────────────┐  ┌───────────────┐
    │ workflow/   │  │ agent/sac/   │  │ workflow_tool │
    │ app.py      │  │ workflow_    │  │ .py           │
    │ (models)    │  │ support/     │  │               │
    └──────┬──────┘  └──────┬───────┘  └───────┬───────┘
           │                │                  │
           └────────────────┼──────────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │ workflow/      │
                   │ component.py   │
                   │ dag_executor   │
                   └────────┬───────┘
                            │
                            ▼
                   ┌────────────────┐
                   │ Frontend       │
                   │ Visualization  │
                   └────────────────┘
```

---

## Merge Strategy: Stacked PRs Approach

### Branching Model

Each PR builds on the previous one, creating a stack where the final branch contains all changes:

```
main
  │
  └── feature/prescriptive-workflows (base branch, created from main)
         │
         └── pr/workflows-1-foundation
                │
                └── pr/workflows-2-models
                       │
                       └── pr/workflows-3-agent-support
                              │
                              └── pr/workflows-4-workflow-tool
                                     │
                                     └── pr/workflows-5a-orchestrator
                                            │
                                            └── pr/workflows-5b-dag-core
                                                   │
                                                   └── pr/workflows-5c-advanced-nodes
                                                          │
                                                          └── pr/workflows-6-integration
                                                                 │
                                                                 └── pr/workflows-7-frontend (LAST)
```

**How stacked PRs work:**
- PR 1 targets `feature/prescriptive-workflows`
- PR 2 targets PR 1's branch (shows only PR 2's changes in diff)
- When PR 1 merges, PR 2 auto-retargets to `feature/prescriptive-workflows`
- Final branch (`pr/workflows-7-frontend`) contains all changes

**Benefits of this approach:**
- Each PR shows only its incremental changes (clean, focused diff)
- Reviewers focus on specific code sections without full context overhead
- The full branch is always available for testing
- Frontend reviewer (PR 7) can test full workflow execution since all backend is in place
- Once all PRs are reviewed and merged to feature branch, single final merge to main

**Note:** No feature flag is required - workflows and structured agents must be explicitly configured to be used, which acts as an implicit feature flag.

---

## Proposed PR Breakdown (9 PRs)

### PR 1: Foundation - Data Models & Constants
**Scope:** ~300 lines | **Review Focus:** Data structures, type definitions
**Target:** `feature/prescriptive-workflows`

**Files:**
- `src/solace_agent_mesh/common/data_parts.py` - New workflow data parts
- `src/solace_agent_mesh/common/constants.py` - New constants
- `src/solace_agent_mesh/common/a2a/` - A2A type additions
- `src/solace_agent_mesh/common/agent_card_utils.py`

**Documentation to include:** Brief overview of the workflow data model and message types.

---

### PR 2: Workflow Definition Models
**Scope:** ~650 lines | **Review Focus:** Pydantic models, YAML schema design
**Target:** `pr/workflows-1-foundation`

**Files:**
- `src/solace_agent_mesh/workflow/app.py` - Pydantic models for workflow definition
- `src/solace_agent_mesh/workflow/__init__.py`

**Documentation to include:** Workflow YAML syntax reference, node type descriptions.

---

### PR 3: Structured Invocation Support
**Scope:** ~1,400 lines | **Review Focus:** How agents can be invoked with schema-validated input/output
**Target:** `pr/workflows-2-models`

**Files:**
- `src/solace_agent_mesh/agent/sac/structured_invocation/` (new package)
  - `handler.py` - StructuredInvocationHandler
  - `validator.py` - Schema validation
- `src/solace_agent_mesh/agent/sac/component.py` (modifications)
- `src/solace_agent_mesh/agent/sac/app.py` (modifications)

**Documentation to include:** How to configure an agent for structured invocation (used by workflows and other programmatic callers).

---

### PR 4: Workflow Tool for Agents
**Scope:** ~370 lines | **Review Focus:** ADK tool implementation
**Target:** `pr/workflows-3-agent-support`

**Files:**
- `src/solace_agent_mesh/agent/tools/workflow_tool.py`

**Documentation to include:** How agents can invoke workflows as tools.

---

### PR 5a: Workflow Runtime - Orchestrator Component
**Scope:** ~1,500 lines | **Review Focus:** Component lifecycle, message routing, agent card
**Target:** `pr/workflows-4-workflow-tool`

**Files:**
- `src/solace_agent_mesh/workflow/component.py` - WorkflowExecutorComponent
- `src/solace_agent_mesh/workflow/protocol/event_handlers.py` - A2A message handling

**Key concepts:**
- Component initialization and lifecycle
- Message routing (task requests, agent responses)
- Agent card generation and Mermaid diagram
- Workflow event publishing

**Documentation to include:** How the workflow component fits into SAM architecture.

---

### PR 5b: Workflow Runtime - DAG Executor Core
**Scope:** ~700 lines | **Review Focus:** Dependency graph, basic node execution
**Target:** `pr/workflows-5a-orchestrator`

**Files:**
- `src/solace_agent_mesh/workflow/dag_executor.py` (lines 1-700 approx)
  - `DAGExecutor` class
  - Dependency graph building
  - `execute_workflow()`
  - `execute_node()`
  - `_execute_agent_node()`
  - `_execute_conditional_node()`
- `src/solace_agent_mesh/workflow/workflow_execution_context.py`
- `src/solace_agent_mesh/workflow/flow_control/conditional.py`
- `src/solace_agent_mesh/workflow/utils.py`

**Key concepts:**
- How the DAG is constructed from workflow definition
- Basic node execution flow
- Agent and conditional node execution

**Documentation to include:** DAG execution model, dependency resolution.

---

### PR 5c: Workflow Runtime - Advanced Node Types
**Scope:** ~700 lines | **Review Focus:** Loop, map, switch execution
**Target:** `pr/workflows-5b-dag-core`

**Files:**
- `src/solace_agent_mesh/workflow/dag_executor.py` (lines 700-1382 approx)
  - `_execute_switch_node()`
  - `_execute_loop_node()`
  - `_execute_map_node()`
  - `_launch_map_iterations()`
  - `handle_node_completion()`
  - `_finalize_map_node()`
- `src/solace_agent_mesh/workflow/agent_caller.py`

**Key concepts:**
- Switch (multi-way branching) execution
- Loop (while) iteration
- Map (parallel for-each) iteration with concurrency control
- Node completion handling

**Documentation to include:** How advanced control flow works.

---

### PR 6: Integration, Examples & Tests
**Scope:** ~6,000 lines | **Review Focus:** Examples, unit tests, integration tests
**Target:** `pr/workflows-5c-advanced-nodes`

**Files:**
- `src/solace_agent_mesh/gateway/http_sse/component.py` - Gateway workflow event forwarding
- `examples/agents/all_node_types_workflow.yaml` - Comprehensive workflow example
- `examples/agents/jira_bug_triage_workflow.yaml` - Real-world example
- `tests/unit/workflow/*.py` - Unit tests (~1,770 lines, 6 test files)
- `tests/integration/scenarios_programmatic/test_workflow_errors.py` - Integration tests (~2,000 lines)
- `tests/integration/scenarios_declarative/test_data/workflows/*.yaml` - Declarative test workflows (8 files)

**Documentation to include:** Getting started guide, example walkthrough.

---

### PR 7: Frontend - Visualization (LAST)
**Scope:** ~5,700 lines | **Review Focus:** ALL frontend changes - layout algorithm, React components, SVG rendering
**Target:** `pr/workflows-6-integration`

**Why this is last:** The frontend reviewer can pull this branch and test full workflow execution, since all backend components and integration are in place.

**Files:**
- `client/webui/frontend/src/lib/components/activities/index.ts` - Activity component exports
- `client/webui/frontend/src/lib/components/activities/taskVisualizerProcessor.ts` - Event processing
- `client/webui/frontend/src/lib/components/activities/VisualizerStepCard.tsx` - Step card component
- `client/webui/frontend/src/lib/providers/*.tsx` - Provider updates
- `client/webui/frontend/src/lib/types/activities.ts` - Activity types
- `client/webui/frontend/src/lib/components/activities/FlowChart/utils/layoutEngine.ts`
- `client/webui/frontend/src/lib/components/activities/FlowChart/utils/types.ts`
- `client/webui/frontend/src/lib/components/activities/FlowChart/utils/nodeDetailsHelper.ts`
- `client/webui/frontend/src/lib/components/activities/FlowChart/FlowChartPanel.tsx`
- `client/webui/frontend/src/lib/components/activities/FlowChart/WorkflowRenderer.tsx`
- `client/webui/frontend/src/lib/components/activities/FlowChart/EdgeLayer.tsx`
- `client/webui/frontend/src/lib/components/activities/FlowChart/PanZoomCanvas.tsx`
- `client/webui/frontend/src/lib/components/activities/FlowChart/NodeDetailsCard.tsx`
- `client/webui/frontend/src/lib/components/activities/FlowChart/nodes/*.tsx` (all node components)
- `client/webui/frontend/src/lib/components/activities/FlowChart/index.ts`

**Documentation to include:** Layout algorithm explanation, component architecture, how to add new node types.

---

## Work Remaining Before PRs

1. **Documentation** - Create PR summary files for each PR
2. **Code Cleanup** - Review for debug code, TODOs, rough edges
3. **Test Coverage** - Add/improve test coverage for each PR section

---

## PR Review Flow

With stacked PRs, reviews happen sequentially but the full branch is always testable:

```
Timeline Visualization:

[PR1] → [PR2] → [PR3] → [PR4] → [5a] → [5b] → [5c] → [PR6] → [PR7]
  │       │       │       │      │      │      │       │       │
  └───────┴───────┴───────┴──────┴──────┴──────┴───────┴───────┘
                    Backend Runtime                Integration  Frontend
                                                                (testable!)
```

**Key benefit:** PR 7 (Frontend) reviewer can pull the branch and test real workflow execution end-to-end.

---

## Summary Table

| PR | Name | ~Lines | Target Branch | Reviewer Focus |
|----|------|--------|---------------|----------------|
| 1 | Foundation | 300 | `feature/prescriptive-workflows` | Data structures |
| 2 | Workflow Models | 650 | `pr/workflows-1-foundation` | Pydantic models |
| 3 | Structured Invocation | 1,400 | `pr/workflows-2-models` | Agent schema validation |
| 4 | Workflow Tool | 370 | `pr/workflows-3-agent-support` | ADK tool |
| 5a | Orchestrator Component | 1,500 | `pr/workflows-4-workflow-tool` | Component lifecycle |
| 5b | DAG Executor Core | 700 | `pr/workflows-5a-orchestrator` | Dependency graph |
| 5c | Advanced Nodes | 700 | `pr/workflows-5b-dag-core` | Loop/map/switch |
| 6 | Integration & Examples | 6,000 | `pr/workflows-5c-advanced-nodes` | Examples, unit tests, integration tests |
| 7 | Frontend (LAST) | 5,700 | `pr/workflows-6-integration` | ALL frontend changes |

**Total:** ~17,320 lines (excluding docs)
