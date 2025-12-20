# Prescriptive Workflows - Test Plan

This document outlines a comprehensive test strategy for the Prescriptive Workflows feature.

## Current State

### Existing Test Coverage (In This Branch)

**Declarative Tests:**
| File | Coverage | Status |
|------|----------|--------|
| `tests/integration/scenarios_declarative/test_data/workflows/test_simple_two_node_workflow.yaml` | Linear 2-node workflow (step_1 → step_2) | Exists |
| `tests/integration/scenarios_declarative/test_data/workflows/test_workflow_with_structured_input.yaml` | Structured input schema validation | Exists |

**Test Infrastructure (conftest.py):**
- `TestSimpleWorkflowApp` fixture - Simple 2-node workflow
- `TestStructuredWorkflowApp` fixture - Workflow with structured schemas
- `test_simple_workflow_app` / `test_simple_workflow_component` fixtures

### What Existing Tests Cover
1. Basic linear workflow execution (2 nodes in sequence)
2. Input artifact passing to workflow
3. Result embed parsing (`«result:artifact=... status=success»`)
4. `_notify_artifact_save` tool integration
5. Structured input with JSON schema
6. Node-to-node data flow via artifacts

### What Existing Tests Do NOT Cover
- Control flow nodes (conditional, switch, loop, map)
- Template resolution logic
- Error handling / node failures
- Implicit parallelism
- Workflow as tool invocation
- Visualization events
- Schema validation retry logic
- Exit handlers

### Not Related
- `tests/integration/apis/persistence/test_end_to_end_workflows.py` tests *persistence* workflows (user conversations), not prescriptive workflows

### Recommendation: Keep vs Remove Existing Tests

**Keep the existing declarative tests** because:
1. They test the core happy path (linear workflow, structured input)
2. They follow the established declarative test pattern used elsewhere
3. They're well-structured and document the expected LLM interaction sequence
4. The LLM mock setup is already figured out (fenced blocks + result embeds)

**Enhance rather than replace:**
1. Add more declarative tests for control flow nodes
2. Add unit tests for the logic that doesn't need full integration (template resolution, conditional evaluation, DAG logic)
3. Use programmatic tests for edge cases that are awkward in YAML

## Test Categories

### 1. Unit Tests (Behavior-Focused)

Location: `tests/unit/workflow/`

**Philosophy:** Unit tests should test **behavior, not implementation**. Each test should:
- Construct real input data (not mocks)
- Call the function
- Assert on the output

If you need to mock more than 1-2 things, it's probably an integration test. Avoid testing that "line X calls function Y with argument Z" - test that the function produces correct output for given input.

#### 1.1 Template Resolution (`test_template_resolution.py`)

Tests for `DAGExecutor.resolve_value()` and `_resolve_template()` - pure functions.

```python
# Example test style - construct real state, call function, check output
def test_resolve_workflow_input():
    state = WorkflowExecutionState(
        execution_id="test",
        workflow_name="test",
        node_outputs={"workflow_input": {"output": {"x": 42}}}
    )
    result = executor.resolve_value("{{workflow.input.x}}", state)
    assert result == 42
```

| Test | Input → Output | Priority |
|------|----------------|----------|
| `test_resolve_workflow_input` | `{{workflow.input.x}}` → value from workflow input | High |
| `test_resolve_node_output` | `{{node.output.field}}` → value from completed node | High |
| `test_resolve_nested_path` | `{{node.output.a.b.c}}` → deeply nested value | High |
| `test_resolve_missing_node_raises` | `{{missing.output.x}}` → clear error message | High |
| `test_resolve_literal_passthrough` | `"hello"` → `"hello"` unchanged | Medium |
| `test_coalesce_operator` | `{"coalesce": [null, "fallback"]}` → `"fallback"` | Medium |
| `test_concat_operator` | `{"concat": ["a", "b"]}` → `"ab"` | Medium |

#### 1.2 Conditional Evaluation (`test_conditional_evaluation.py`)

Tests for `evaluate_condition()` - pure function.

| Test | Input → Output | Priority |
|------|----------------|----------|
| `test_string_equality` | `"'success' == 'success'"` with state → `True` | High |
| `test_numeric_comparison` | `"{{node.output.count}} > 10"` with count=15 → `True` | High |
| `test_string_contains` | `"'error' in '{{node.output.msg}}'"` → boolean | High |
| `test_argo_item_alias` | `"{{item}} == 'x'"` → resolves `{{_map_item}}` | Medium |
| `test_argo_parameters_alias` | `"{{workflow.parameters.x}}"` → resolves `{{workflow.input.x}}` | Medium |
| `test_missing_node_raises` | Reference to non-existent node → `ConditionalEvaluationError` | Medium |

#### 1.3 DAG Logic (`test_dag_logic.py`)

Tests for DAG traversal logic - can test with constructed node lists.

| Test | Input → Output | Priority |
|------|----------------|----------|
| `test_initial_nodes_have_no_dependencies` | Node list → nodes with empty `depends_on` | High |
| `test_node_ready_when_dependencies_complete` | Completed deps + pending node → node is ready | High |
| `test_skipped_node_propagates_to_children` | Parent skipped → children marked skipped | High |
| `test_conditional_only_activates_one_branch` | Condition result → one branch active, other skipped | Medium |

#### 1.4 Workflow Model Validation (`test_workflow_models.py`)

Tests for Pydantic model validation - pure construction/validation.

| Test | Input → Output | Priority |
|------|----------------|----------|
| `test_valid_workflow_parses` | Valid YAML dict → WorkflowDefinition | High |
| `test_invalid_node_reference_rejected` | `depends_on: ["nonexistent"]` → ValidationError | High |
| `test_conditional_requires_true_branch` | ConditionalNode without `true_branch` → ValidationError | High |
| `test_map_node_requires_item_source` | MapNode without items/withParam → ValidationError | Medium |

**Total: ~20 focused behavior tests**

#### What NOT to Unit Test

These components require too much infrastructure and should be **integration tests**:

| Component | Why Not Unit Test |
|-----------|-------------------|
| `AgentCaller.call_agent()` | Requires broker, artifact service, message correlation |
| `WorkflowExecutorComponent` | Full component lifecycle with messaging |
| `StructuredInvocationHandler.execute_*()` | Requires ADK agent, artifact service |
| Result embed parsing in context | Coupled to message handling flow |

### 2. Integration Tests

Location: `tests/integration/scenarios_programmatic/workflow/`

#### 2.1 Simple Workflow Execution

**Existing declarative test:** `test_simple_two_node_workflow.yaml` ✅

Uses `TestSimpleWorkflowApp` fixture with mock LLM responses.

| Test | Description | Priority | Status |
|------|-------------|----------|--------|
| `test_linear_two_node_workflow` | step_1 → step_2 executes in order | High | ✅ Exists (declarative) |
| `test_workflow_input_passed_to_first_node` | Input data reaches first node | High | ✅ Exists (declarative) |
| `test_node_output_passed_to_next_node` | Output flows between nodes | High | ✅ Exists (declarative) |
| `test_workflow_output_mapping` | Final output mapped correctly | High | Needed |
| `test_workflow_agent_card_published` | Workflow appears as agent | High | Needed |
| `test_workflow_invocable_via_a2a` | Workflow responds to A2A requests | High | ✅ Implicit (declarative) |

#### 2.2 Structured Schema Workflow

**Existing declarative test:** `test_workflow_with_structured_input.yaml` ✅

Uses `TestStructuredWorkflowApp` fixture.

| Test | Description | Priority | Status |
|------|-------------|----------|--------|
| `test_input_schema_validation_pass` | Valid input accepted | High | ✅ Exists (declarative) |
| `test_input_schema_validation_fail` | Invalid input rejected with error | High | Needed |
| `test_output_schema_validation_pass` | Valid output accepted | High | ✅ Exists (declarative) |
| `test_output_schema_validation_retry` | Invalid output triggers retry | Medium | Needed |
| `test_schema_override_per_node` | Node-level schema overrides work | Medium | ✅ Exists (declarative) |
| `test_structured_data_artifact_flow` | JSON artifacts flow between nodes | High | ✅ Exists (declarative) |

#### 2.3 Conditional Workflow (`test_conditional_workflow.py`)

Requires new workflow fixture with conditional nodes.

| Test | Description | Priority |
|------|-------------|----------|
| `test_conditional_true_branch_taken` | Condition true → true_branch executes | High |
| `test_conditional_false_branch_taken` | Condition false → false_branch executes | High |
| `test_conditional_false_branch_optional` | Missing false_branch skipped gracefully | Medium |
| `test_conditional_untaken_branch_skipped` | Untaken branch nodes marked skipped | High |
| `test_switch_node_first_match_wins` | First matching case selected | High |
| `test_switch_node_default_fallback` | No match → default branch | Medium |
| `test_switch_all_except_selected_skipped` | Non-selected branches skipped | Medium |
| `test_agent_node_when_clause` | `when` clause skips node if false | Medium |

#### 2.4 Loop Workflow (`test_loop_workflow.py`)

Requires new workflow fixture with loop nodes.

| Test | Description | Priority |
|------|-------------|----------|
| `test_loop_executes_while_condition_true` | Loop repeats until condition false | High |
| `test_loop_first_iteration_always_runs` | Condition checked after first run | High |
| `test_loop_max_iterations_enforced` | Loop stops at max_iterations | High |
| `test_loop_delay_between_iterations` | Delay applied between iterations | Low |
| `test_loop_inner_node_output_available` | Inner node output accessible for condition | Medium |

#### 2.5 Map Workflow (`test_map_workflow.py`)

Requires new workflow fixture with map nodes.

| Test | Description | Priority |
|------|-------------|----------|
| `test_map_iterates_over_array` | Each item processed | High |
| `test_map_item_variable_available` | `{{_map_item}}` resolved in inner node | High |
| `test_map_index_variable_available` | `{{_map_index}}` resolved | Medium |
| `test_map_results_aggregated` | Results collected in order | High |
| `test_map_max_items_enforced` | Array exceeding limit rejected | Medium |
| `test_map_concurrency_limit` | Concurrency limit respected | Medium |
| `test_map_empty_array_completes` | Empty array → empty results | Medium |
| `test_map_with_param_syntax` | Argo `withParam` syntax works | Low |

#### 2.6 Error Handling (`test_workflow_errors.py`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_node_failure_fails_workflow` | Agent error → workflow fails | High |
| `test_error_state_populated` | Error details in workflow state | High |
| `test_fail_fast_stops_new_nodes` | No new nodes scheduled after failure | Medium |
| `test_timeout_handling` | Node timeout → failure | Medium |
| `test_missing_agent_error` | Non-existent agent → clear error | Medium |
| `test_template_resolution_error` | Invalid template → clear error | Medium |

#### 2.7 Workflow as Tool (`test_workflow_tool.py`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_workflow_appears_as_tool` | Workflow registered as tool | High |
| `test_agent_invokes_workflow_tool` | Agent can call workflow | High |
| `test_workflow_tool_returns_result` | Workflow output returned to agent | High |
| `test_workflow_tool_parameter_mode` | Parameters passed directly | Medium |
| `test_workflow_tool_artifact_mode` | Input artifact reference works | Medium |

#### 2.8 Visualization Events (`test_workflow_events.py`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_workflow_execution_start_event` | Start event published | High |
| `test_workflow_node_start_event` | Node start events published | High |
| `test_workflow_node_result_event` | Node result events published | High |
| `test_map_progress_event` | Map progress updates published | Medium |
| `test_events_include_sub_task_id` | Events correlate to sub-tasks | High |
| `test_conditional_node_metadata` | Condition result in metadata | Medium |

### 3. Frontend Tests ⏸️ DEFERRED

> **Deferred:** Frontend team is setting up test environment. Will revisit to avoid incompatible tests.

Location: `client/webui/frontend/src/lib/components/activities/FlowChart/__tests__/`

#### 3.1 Task Visualizer Processor (`taskVisualizerProcessor.test.ts`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_workflow_execution_start_creates_step` | Start event → VisualizerStep | High |
| `test_workflow_node_start_creates_child` | Node start → child step | High |
| `test_workflow_node_result_updates_status` | Node result → status update | High |
| `test_nested_agent_events_parented` | Agent events under workflow node | High |
| `test_map_progress_updates` | Map progress reflected | Medium |

#### 3.2 Layout Engine (`layoutEngine.test.ts`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_linear_workflow_layout` | Sequential nodes positioned vertically | High |
| `test_parallel_branches_layout` | Parallel nodes positioned horizontally | High |
| `test_nested_workflow_layout` | Nested items grouped | Medium |
| `test_edge_calculation` | Edges connect parent to child | High |
| `test_collapsed_node_dimensions` | Collapsed nodes smaller | Medium |

#### 3.3 Node Components (`nodes/*.test.tsx`)

| Test | Description | Priority |
|------|-------------|----------|
| `test_workflow_group_renders` | WorkflowGroup container renders | Medium |
| `test_conditional_node_shows_branches` | Both branches displayed | Medium |
| `test_map_node_shows_progress` | Iteration count visible | Medium |
| `test_node_status_styling` | Status colors applied | Low |

### 4. End-to-End Tests ⏸️ DEFERRED

> **Deferred:** Depends on frontend test environment.

Location: `tests/e2e/workflow/` (new directory)

These require a running system with real broker and may be slower.

| Test | Description | Priority |
|------|-------------|----------|
| `test_full_workflow_via_webui` | Submit workflow via WebUI, see results | Low |
| `test_workflow_progress_visualization` | Real-time updates in UI | Low |
| `test_workflow_error_display` | Errors shown in UI | Low |

## Test Infrastructure Requirements

### New Fixtures Needed

1. **Conditional Workflow Fixture** - Workflow with ConditionalNode
2. **Loop Workflow Fixture** - Workflow with LoopNode
3. **Map Workflow Fixture** - Workflow with MapNode
4. **Switch Workflow Fixture** - Workflow with SwitchNode
5. **Nested Workflow Fixture** - Workflow calling another workflow

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

## Implementation Priority

### Phase 1 - Unit Tests for Pure Functions (High Priority) ✅ COMPLETE
These can be written quickly with no infrastructure setup:
1. Template resolution tests (`test_template_resolution.py`) - **27 tests**
2. Conditional evaluation tests (`test_conditional_evaluation.py`) - **27 tests**
3. DAG logic tests (`test_dag_logic.py`) - **17 tests**
4. Workflow model validation tests (`test_workflow_models.py`) - **22 tests**
5. Utility functions tests (`test_utils.py`) - **23 tests**

**Total Phase 1: 116 tests** (all passing)

### Phase 2 - Control Flow Declarative Tests (High Priority) ✅ PARTIALLY COMPLETE
Follow the pattern of existing declarative tests:
1. Conditional workflow (true/false branch) - **2 tests** ✅
2. Map workflow (iterate over array) - **1 test** ✅
3. Switch workflow (multi-way branch) - *deferred (similar to conditional)*
4. Loop workflow (while condition) - *deferred (less common pattern)*

**Total Phase 2: 3 new tests** (all passing)

### Phase 3 - Error Cases (Medium Priority) ✅ COMPLETE
Programmatic tests for scenarios awkward in YAML:
1. Invalid input schema rejection - **2 tests** ✅
2. Node failure handling - **1 test** ✅
3. Empty response handling - **1 test** ✅
4. Successful workflow validation - **1 test** ✅
5. Output schema validation with retry - **1 test** ✅

**Total Phase 3: 6 tests** (all passing)

### Phase 4 - Frontend ⏸️ DEFERRED
> **Deferred:** Frontend team is setting up test environment. Will revisit to avoid incompatible tests.

1. Layout engine tests
2. Task visualizer processor tests

### Phase 5 - E2E ⏸️ DEFERRED
> **Deferred:** Depends on frontend test environment.

1. Full system smoke tests

## Estimated Test Count

### In Scope (Phases 1-3) ✅ COMPLETE

| Category | Existing | Added | Total |
|----------|----------|-------|-------|
| Unit Tests (behavior-focused) | 0 | **116** ✅ | **116** |
| Declarative Integration Tests | 2 | **3** ✅ | **5** |
| Programmatic Integration Tests | 0 | **6** ✅ | **6** |
| **In Scope Total** | **2** | **125** | **127** |

### Deferred (Phases 4-5)

| Category | Needed | Status |
|----------|--------|--------|
| Frontend Tests | ~15 | ⏸️ Deferred |
| E2E Tests | ~3 | ⏸️ Deferred |

**Note:** Fewer tests than original estimate because:
1. Unit tests focus on pure functions with real behavior tests (~20 vs ~45)
2. Declarative tests cover happy paths efficiently
3. Programmatic tests only for edge cases awkward in YAML
4. No "mock everything" boilerplate tests

## Notes

### Testing Philosophy

**Behavior over implementation:** Unit tests should verify that functions produce correct outputs for given inputs. Avoid:
- Mocking everything around a single line of code
- Testing that "line X calls function Y with argument Z"
- Creating brittle tests that break when implementation changes

**Good unit test:** Construct real input → call function → assert output
**Bad unit test:** Mock 5 dependencies → call function → assert mock was called correctly

### Practical Notes

1. **Two declarative tests already exist** - These cover the core happy path and should be kept
2. **Existing fixtures are ready** - `TestSimpleWorkflowApp` and `TestStructuredWorkflowApp` in `conftest.py`
3. **LLM mock pattern established** - The existing tests show the correct pattern:
   - Use fenced code blocks (`«««save_artifact...»»»`) for artifact creation
   - Include result embed (`«result:artifact=... status=success»`) in final response
   - Expect `_notify_artifact_save` tool response in subsequent LLM messages
4. **Test type selection:**
   - **Unit tests:** Pure functions (template resolution, conditional evaluation, model validation)
   - **Declarative tests:** Happy path flows (easier to read/maintain)
   - **Programmatic tests:** Error cases and edge conditions (more control)
5. **Frontend tests** - May need Jest/Vitest setup if not already configured
