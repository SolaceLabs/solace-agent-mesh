# Prescriptive Workflows - TODO Items

## Code TODOs

### 1. Workflow Cancellation Logic
**File:** `src/solace_agent_mesh/workflow/protocol/event_handlers.py:319-390`

**Status:** ✅ Implemented

**Description:** The `handle_cancel_request()` function is now fully implemented with:
- Signal cancellation to workflow context via `workflow_context.cancel()`
- Cancel any active agent sub-tasks by sending CancelTaskRequest to each agent
- Finalize the workflow as cancelled via `finalize_workflow_cancelled()`
- Clean up resources and ACK the original message
- Cancellation checks in `dag_executor.py` (`execute_workflow` and `handle_node_completion`)

**Test Coverage:** `test_workflow_cancellation` in `tests/integration/scenarios_programmatic/test_workflow_errors.py`

---

### 2. Map State Storage - Design Review
**File:** `src/solace_agent_mesh/workflow/dag_executor.py:905-908`

**Status:** ✅ Resolved - Intentional Design

**Description:** The implementation stores map node state in the `metadata` field of `WorkflowExecutionState`. This is the correct approach because:
- The `metadata` field is designed for node-specific extensible state (`Dict[str, Any]`)
- Namespaced keys (`map_state_{node.id}`) avoid collisions
- No schema changes required for new node types that need state
- Clean separation: `metadata` holds node state, `active_branches` tracks executing sub-tasks

The exploratory comment has been cleaned up to reflect this as an intentional design choice.

---

## Testing TODOs
- [x] Add test coverage for workflow cancellation
- [ ] Add integration tests for map node state persistence
- [ ] Review test coverage for all node types

---

## Documentation TODOs
- [x] Document workflow cancellation behavior (implemented in code - sends CancelTaskRequest to agents, finalizes workflow with cancelled state)
- [x] Document map node state management design decision (comment updated in code)
