# Prescriptive Workflows - Test Plan

This document outlines the test coverage for the Prescriptive Workflows feature.

## Test Categories

### 1. Unit Tests (Behavior-Focused)

Location: `tests/unit/workflow/`

**Philosophy:** Unit tests focus on **behavior, not implementation**. Each test:
- Constructs real input data (not mocks)
- Calls the function
- Asserts on the output

#### 1.1 Template Resolution (`test_template_resolution.py`) — 27 tests

Tests for `DAGExecutor.resolve_value()` and `_resolve_template()`.

| Test Category | Description |
|---------------|-------------|
| Workflow input resolution | `{{workflow.input.x}}` → value from workflow input |
| Node output resolution | `{{node.output.field}}` → value from completed node |
| Nested path resolution | `{{node.output.a.b.c}}` → deeply nested value |
| Missing node handling | `{{missing.output.x}}` → clear error message |
| Literal passthrough | `"hello"` → `"hello"` unchanged |
| Coalesce operator | `{"coalesce": [null, "fallback"]}` → `"fallback"` |
| Special variables | `{{_map_item}}`, `{{_loop_iteration}}` resolution |

#### 1.2 Conditional Evaluation (`test_conditional_evaluation.py`) — 27 tests

Tests for `evaluate_condition()`.

| Test Category | Description |
|---------------|-------------|
| String equality | `"'success' == 'success'"` with state → `True` |
| Numeric comparison | `"{{node.output.count}} > 10"` with count=15 → `True` |
| String contains | `"'error' in '{{node.output.msg}}'"` → boolean |
| Boolean operators | `&&`, `\|\|` combinations |
| Argo aliases | `{{item}}` → `{{_map_item}}`, `{{workflow.parameters}}` → `{{workflow.input}}` |
| Error handling | Reference to non-existent node → `ConditionalEvaluationError` |

#### 1.3 DAG Logic (`test_dag_logic.py`) — 17 tests

Tests for DAG traversal logic.

| Test Category | Description |
|---------------|-------------|
| Initial nodes | Nodes with empty `depends_on` start first |
| Dependency completion | Node ready when all dependencies complete |
| Skip propagation | Skipped parent → children marked skipped |
| Branch activation | Conditional result activates one branch, skips other |
| Completion detection | Workflow completion state detection |

#### 1.4 Workflow Model Validation (`test_workflow_models.py`) — 22 tests

Tests for Pydantic model validation.

| Test Category | Description |
|---------------|-------------|
| Valid workflow parsing | Valid YAML dict → WorkflowDefinition |
| Invalid references | `depends_on: ["nonexistent"]` → ValidationError |
| Required fields | Missing required fields → ValidationError |
| Node type validation | Each node type validates correctly |
| Alias support | Both snake_case and camelCase accepted |

#### 1.5 Utility Functions (`test_utils.py`) — 23 tests

Tests for workflow utility functions.

| Test Category | Description |
|---------------|-------------|
| Duration parsing | `"5s"`, `"1m"`, `"1h"` → seconds |
| Path extraction | Template path parsing |
| Helper functions | Various utility function tests |

**Total Unit Tests: 116**

---

### 2. Integration Tests — Declarative

Location: `tests/integration/scenarios_declarative/test_data/workflows/`

These tests use YAML fixtures with mock LLM responses.

| Test File | Description |
|-----------|-------------|
| `test_simple_two_node_workflow.yaml` | Linear 2-node workflow (step_1 → step_2) |
| `test_workflow_with_structured_input.yaml` | Structured input schema validation |
| `test_conditional_workflow_true_branch.yaml` | Conditional node takes true branch |
| `test_conditional_workflow_false_branch.yaml` | Conditional node takes false branch |
| `test_loop_workflow.yaml` | Loop node iterates until condition met |
| `test_map_workflow.yaml` | Map node iterates over array |
| `test_switch_workflow_create_case.yaml` | Switch node selects matching case |
| `test_switch_workflow_default_case.yaml` | Switch node falls through to default |

**Total Declarative Tests: 8**

---

### 3. Integration Tests — Programmatic

Location: `tests/integration/scenarios_programmatic/`

#### 3.1 Workflow Error Handling (`test_workflow_errors.py`) — 13 tests

| Test Category | Description |
|---------------|-------------|
| Input validation | Invalid input schema rejected with error |
| Node failures | Agent error propagates to workflow failure |
| Output validation | Output schema validation with retry logic |
| Empty responses | Empty agent response handling |
| Timeout handling | Node timeout scenarios |
| Missing agents | Non-existent agent produces clear error |

**Total Programmatic Integration Tests: 13**

---

### Backend Test Summary

| Category | Count |
|----------|-------|
| Unit Tests | 116 |
| Declarative Integration Tests | 8 |
| Programmatic Integration Tests | 13 |
| **Total Backend Tests** | **137** |

---

### 4. Frontend Tests — DEFERRED

> **Deferred:** Frontend team is setting up test environment. Will revisit to avoid incompatible tests.

Location: `client/webui/frontend/src/lib/components/activities/FlowChart/__tests__/`

#### 4.1 Task Visualizer Processor (`taskVisualizerProcessor.test.ts`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_workflow_execution_start_creates_step` | Start event → VisualizerStep | High |
| `test_workflow_node_start_creates_child` | Node start → child step | High |
| `test_workflow_node_result_updates_status` | Node result → status update | High |
| `test_nested_agent_events_parented` | Agent events under workflow node | High |
| `test_map_progress_updates` | Map progress reflected | Medium |

#### 4.2 Layout Engine (`layoutEngine.test.ts`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_linear_workflow_layout` | Sequential nodes positioned vertically | High |
| `test_parallel_branches_layout` | Parallel nodes positioned horizontally | High |
| `test_nested_workflow_layout` | Nested items grouped | Medium |
| `test_edge_calculation` | Edges connect parent to child | High |
| `test_collapsed_node_dimensions` | Collapsed nodes smaller | Medium |

#### 4.3 Node Components (`nodes/*.test.tsx`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_workflow_group_renders` | WorkflowGroup container renders | Medium |
| `test_conditional_node_shows_branches` | Both branches displayed | Medium |
| `test_map_node_shows_progress` | Iteration count visible | Medium |
| `test_node_status_styling` | Status colors applied | Low |

---

### 5. End-to-End Tests — DEFERRED

> **Deferred:** Depends on frontend test environment.

Location: `tests/e2e/workflow/` (new directory)

These require a running system with real broker and may be slower.

| Test | Description | Priority |
|------|-------------|----------|
| `test_full_workflow_via_webui` | Submit workflow via WebUI, see results | Low |
| `test_workflow_progress_visualization` | Real-time updates in UI | Low |
| `test_workflow_error_display` | Errors shown in UI | Low |

---

## Test Infrastructure

### Mock LLM Response Patterns

For structured invocation tests, LLM responses must include:
1. A tool call to save an artifact
2. The result embed: `«result:artifact=filename.json status=success»`

Example:
```python
llm_responses = [
    # First response: Save artifact with structured output
    ChatCompletionResponse(
        choices=[Choice(
            message=Message(
                role="assistant",
                tool_calls=[ToolCall(
                    id="call_save",
                    type="function",
                    function=ToolCallFunction(
                        name="save_artifact",
                        arguments='{"filename": "output.json", "data": {"status": "processed"}}'
                    )
                )]
            ),
            finish_reason="tool_calls"
        )]
    ),
    # Second response: Result embed marking completion
    ChatCompletionResponse(
        choices=[Choice(
            message=Message(
                role="assistant",
                content="Task completed. «result:artifact=output.json status=success»"
            ),
            finish_reason="stop"
        )]
    )
]
```

---

## Notes

### Testing Philosophy

**Behavior over implementation:** Unit tests verify that functions produce correct outputs for given inputs. Avoid:
- Mocking everything around a single line of code
- Testing that "line X calls function Y with argument Z"
- Creating brittle tests that break when implementation changes

**Good unit test:** Construct real input → call function → assert output
**Bad unit test:** Mock 5 dependencies → call function → assert mock was called correctly

### Test Type Selection

| Type | Use When |
|------|----------|
| Unit tests | Pure functions (template resolution, conditional evaluation, model validation) |
| Declarative tests | Happy path flows (easier to read/maintain) |
| Programmatic tests | Error cases and edge conditions (more control) |
