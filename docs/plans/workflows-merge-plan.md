# Prescriptive Workflows Feature - Incremental Merge Strategy

## Feature Overview

The `ed/prescriptive-workflows` branch introduces a comprehensive "Prescriptive Workflows" feature that enables defining and executing structured, deterministic workflows as an alternative to purely agent-driven orchestration.

**Stats:** 107 files changed, ~30,000 lines added

---

## High-Level Components Identified

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

### 2. **Agent Workflow Support** (~1,700 lines)
Location: `src/solace_agent_mesh/agent/`

| File | Lines | Purpose |
|------|-------|---------|
| `sac/workflow_support/handler.py` | 1163 | WorkflowNodeHandler - enables agents to act as workflow nodes |
| `sac/workflow_support/validator.py` | 29 | Schema validation |
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

### 4. **Frontend Visualization V2** (~6,500 lines) - ONLY V2
Location: `client/webui/frontend/src/lib/components/activities/FlowChart/v2/`

| File | Lines | Purpose |
|------|-------|---------|
| `FlowChartPanelV2.tsx` | 177 | Main panel component |
| `WorkflowRendererV2.tsx` | 358 | SVG workflow renderer |
| `EdgeLayerV2.tsx` | 172 | Edge/connection rendering |
| `NodeDetailsCard.tsx` | 1006 | Node details sidebar |
| `utils/layoutEngine.ts` | 1448 | Layout algorithm |
| `utils/nodeDetailsHelper.ts` | 416 | Node details extraction |
| `utils/types.ts` | 125 | TypeScript types |
| **Node components:** | |
| `nodes/AgentNodeV2.tsx` | 289 | Agent node rendering |
| `nodes/WorkflowGroupV2.tsx` | 373 | Group/container rendering |
| `nodes/MapNodeV2.tsx` | 175 | Map node rendering |
| `nodes/LoopNodeV2.tsx` | 159 | Loop node rendering |
| `nodes/ConditionalNodeV2.tsx` | 63 | Conditional rendering |
| `nodes/SwitchNodeV2.tsx` | 70 | Switch node rendering |

### 5. ~~**Frontend V1 Modifications**~~ - WILL BE REMOVED
The V1 visualization code will not be included. Only V2 will ship.

Files to remove/not include:
- `layout/BlockBuilder.ts`
- `layout/LayoutBlock.ts`
- `taskToFlowData.ts` (V1 version)
- `taskToFlowData.helpers.ts` (V1 version)
- V1-specific custom nodes

### 6. **Supporting Frontend Changes** (~700 lines)
| File | Purpose |
|------|---------|
| `FlowChartPanel.tsx` | Modified to use V2 only |
| `taskVisualizerProcessor.ts` | Process workflow visualization data |
| `VisualizerStepCard.tsx` | Step card component |
| `types/activities.ts` | New activity types |
| `providers/ChatProvider.tsx` | Provider updates |
| `providers/TaskProvider.tsx` | Provider updates |

### 7. **Documentation** - TO BE REWRITTEN
All existing design docs will be removed and replaced with focused PR-specific documentation.

### 8. **Examples** (~3,000 lines)
| File | Purpose |
|------|---------|
| `examples/agents/simple_workflow_test.yaml` | Basic workflow |
| `examples/agents/workflow_example.yaml` | Full example |
| `examples/agents/all_node_types_workflow.yaml` | All node types |
| `examples/agents/jira_bug_triage_workflow.yaml` | Real-world example |

### 9. **Tests** (~350 lines)
| File | Purpose |
|------|---------|
| `tests/integration/conftest.py` | Test fixtures |
| `tests/integration/scenarios_declarative/test_data/workflows/*.yaml` | Test workflows |

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
                   │ Frontend V2    │
                   │ Visualization  │
                   └────────────────┘
```

---

## Merge Strategy: Feature Branch Approach

### Branching Model

```
main ◄─────────────────────────────────────── Final merge (after all reviews complete)
  │
  └── feature/prescriptive-workflows ◄────── Intermediate branch (all PRs merge here)
         │
         ├── PR 1: Foundation
         ├── PR 2: Workflow Models
         ├── PR 3: Agent Support
         ├── PR 4: Workflow Tool
         ├── PR 5: Runtime Core
         ├── PR 6: Frontend Layout
         ├── PR 7: Frontend V2 Viz
         └── PR 8: Integration
```

**Benefits of this approach:**
- PRs can be reviewed independently without needing to be functional in isolation
- Reviewers focus on specific code sections without full context overhead
- Feature branch acts as integration point - we know the whole thing works there
- No risk of breaking main with partial merges
- Once all PRs are reviewed and merged to feature branch, single final merge to main

**Feature Flag:** Runtime config flag `workflows: { enabled: true/false }` will be required before final merge to main.

---

## Proposed PR Breakdown (Revised - 10 PRs)

### PR 1: Foundation - Data Models & Constants
**Scope:** ~300 lines | **Review Focus:** Data structures, type definitions

**Files:**
- `src/solace_agent_mesh/common/data_parts.py` - New workflow data parts
- `src/solace_agent_mesh/common/constants.py` - New constants
- `src/solace_agent_mesh/common/a2a/` - A2A type additions
- `src/solace_agent_mesh/common/agent_card_utils.py`

**Documentation to include:** Brief overview of the workflow data model and message types.

---

### PR 2: Workflow Definition Models
**Scope:** ~650 lines | **Review Focus:** Pydantic models, YAML schema design

**Files:**
- `src/solace_agent_mesh/workflow/app.py` - Pydantic models for workflow definition
- `src/solace_agent_mesh/workflow/__init__.py`

**Documentation to include:** Workflow YAML syntax reference, node type descriptions.

---

### PR 3: Agent Workflow Node Support
**Scope:** ~1,400 lines | **Review Focus:** How agents participate as workflow nodes

**Files:**
- `src/solace_agent_mesh/agent/sac/workflow_support/` (new package)
  - `handler.py` - WorkflowNodeHandler
  - `validator.py` - Schema validation
- `src/solace_agent_mesh/agent/sac/component.py` (modifications)
- `src/solace_agent_mesh/agent/sac/app.py` (modifications)

**Documentation to include:** How to configure an agent to participate in workflows.

---

### PR 4: Workflow Tool for Agents
**Scope:** ~500 lines | **Review Focus:** ADK tool implementation

**Files:**
- `src/solace_agent_mesh/agent/tools/workflow_tool.py`

**Documentation to include:** How agents can invoke workflows as tools.

---

### PR 5a: Workflow Runtime - Orchestrator Component
**Scope:** ~1,100 lines | **Review Focus:** Component lifecycle, message routing, agent card

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

### PR 6: Frontend V2 - Layout & Types
**Scope:** ~2,100 lines | **Review Focus:** Layout algorithm, type definitions

**Files:**
- `client/webui/frontend/src/lib/components/activities/FlowChart/v2/utils/layoutEngine.ts`
- `client/webui/frontend/src/lib/components/activities/FlowChart/v2/utils/types.ts`
- `client/webui/frontend/src/lib/components/activities/FlowChart/v2/utils/nodeDetailsHelper.ts`
- `client/webui/frontend/src/lib/types/activities.ts`

**Documentation to include:** How the layout algorithm works.

---

### PR 7: Frontend V2 - Components
**Scope:** ~2,900 lines | **Review Focus:** React components, SVG rendering

**Files:**
- `client/webui/frontend/src/lib/components/activities/FlowChart/v2/`
  - `FlowChartPanelV2.tsx`
  - `WorkflowRendererV2.tsx`
  - `EdgeLayerV2.tsx`
  - `NodeDetailsCard.tsx`
  - `nodes/*.tsx` (all node components)
  - `index.ts`

**Documentation to include:** Component architecture, how to add new node types.

---

### PR 8: Integration, Examples & Tests
**Scope:** ~3,500 lines | **Review Focus:** Integration points, examples, tests

**Files:**
- `client/webui/frontend/src/lib/components/activities/FlowChartPanel.tsx`
- `client/webui/frontend/src/lib/components/activities/taskVisualizerProcessor.ts`
- `client/webui/frontend/src/lib/components/activities/VisualizerStepCard.tsx`
- `client/webui/frontend/src/lib/providers/*.tsx`
- `src/solace_agent_mesh/gateway/http_sse/component.py`
- `examples/agents/*.yaml` (workflow examples)
- `tests/integration/` (test fixtures and workflows)

**Documentation to include:** Getting started guide, example walkthrough.

---

## Work Remaining Before PRs

1. **Feature Flag Implementation** - Add runtime config for enabling/disabling workflows
2. **V1 Code Removal** - Remove V1 visualization code, keep only V2
3. **Documentation Rewrite** - Remove existing design docs, write focused PR-specific docs
4. **Code Cleanup** - Review for debug code, TODOs, rough edges
5. **Test Coverage** - Add/improve test coverage for each PR section

---

## PR Review Parallelization

PRs can be reviewed in parallel tracks:

**Backend Track:** PRs 1-4, 5a, 5b, 5c (can be sequential but reviewed by backend experts)
**Frontend Track:** PRs 6, 7 (can be reviewed by frontend experts in parallel with backend)
**Integration Track:** PR 8 (depends on both tracks completing)

```
Timeline Visualization:

Backend:   [PR1] → [PR2] → [PR3] → [PR4] → [5a] → [5b] → [5c] ─┐
                                                                 ├─→ [PR8]
Frontend:                                   [PR6] ─────→ [PR7] ─┘
```

---

## Summary Table

| PR | Name | Lines | Dependencies | Reviewer Expertise |
|----|------|-------|--------------|-------------------|
| 1 | Foundation | ~300 | None | Backend |
| 2 | Workflow Models | ~650 | PR 1 | Backend |
| 3 | Agent Node Support | ~1,400 | PR 1, 2 | Backend |
| 4 | Workflow Tool | ~500 | PR 1, 2 | Backend |
| 5a | Orchestrator Component | ~1,100 | PR 1-4 | Backend |
| 5b | DAG Executor Core | ~700 | PR 5a | Backend |
| 5c | Advanced Nodes | ~700 | PR 5b | Backend |
| 6 | Frontend Layout | ~2,100 | None | Frontend |
| 7 | Frontend Components | ~2,900 | PR 6 | Frontend |
| 8 | Integration | ~3,500 | All above | Full-stack |

**Total:** ~13,850 lines (excluding removed V1 code and docs)
