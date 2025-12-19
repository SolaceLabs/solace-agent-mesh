# Prescriptive Workflows - TODO Items

## Code TODOs

### 1. Workflow Cancellation Logic
**File:** `src/solace_agent_mesh/workflow/protocol/event_handlers.py:329-332`

**Status:** Not Implemented

**Description:** The `handle_cancel_request()` function is currently a stub with no implementation.

**Options:**
- Implement proper cancellation logic (stop DAG execution, clean up resources, notify agents)
- Remove the function if cancellation is not a planned feature for the initial release
- Document that cancellation is deferred to a future release

**Code:**
```python
def handle_cancel_request(component: "WorkflowExecutorComponent", task_id: str):
    """Handle workflow cancellation request."""
    # TODO: Implement cancellation logic
    pass
```

---

### 2. Map State Storage - Design Review
**File:** `src/solace_agent_mesh/workflow/dag_executor.py:915-922`

**Status:** Working but flagged as "hacky"

**Description:** The current implementation stores map node state in the `metadata` field of `WorkflowExecutionState` to avoid schema changes. The comment suggests this was considered a workaround during development.

**Options:**
- Keep as-is if it's working well (metadata field is designed for extensibility)
- Refactor to use a more explicit schema if map nodes deserve first-class state tracking
- Document this as the intended design pattern for node-specific state

**Code:**
```python
# Lines 915-922
# The existing structure expects a list of branches.
# Let's adapt: active_branches[node.id] will hold the list of *active* sub-tasks.
# But we need to store the *pending* state somewhere.
# We can store the map_state in a special metadata field or abuse active_branches.
# Let's use a list of dicts where the first element is the metadata/state.
# This is a bit hacky but avoids schema changes.
# Better: Use `metadata` field in WorkflowExecutionState for map state.
workflow_state.metadata[f"map_state_{node.id}"] = map_state
```

**Decision needed:** Is this acceptable or should it be refactored before merge?

---

## Testing TODOs
- [ ] Add test coverage for workflow cancellation (if implemented)
- [ ] Add integration tests for map node state persistence
- [ ] Review test coverage for all node types

---

## Documentation TODOs
- [ ] Document workflow cancellation behavior (or explicitly note it's not supported)
- [ ] Document map node state management design decision
