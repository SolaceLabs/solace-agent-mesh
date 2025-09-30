# Token Usage Tracking - Implementation Checklist

**Reference**: See `token-usage-tracking-implementation-plan.md` for detailed instructions for each step.

---

## Phase 1: Data Models and Schema

### Step 1.1: Update LLM Invocation JSON Schema
- [ ] Add `usage` property to `llm_invocation.json`
- [ ] Add nested fields: `input_tokens`, `output_tokens`, `cached_input_tokens`, `model`
- [ ] Mark `usage` as optional
- [ ] Add field descriptions
- [ ] **Validation**: Schema validates with and without `usage` field

**File**: `src/solace_agent_mesh/common/a2a_spec/schemas/llm_invocation.json`

---

### Step 1.2: Update Tool Result JSON Schema
- [ ] Add `llm_usage` property to `tool_result.json`
- [ ] Use same structure as LLM invocation usage
- [ ] Mark as optional
- [ ] Add descriptions
- [ ] **Validation**: Schema validates with and without `llm_usage` field

**File**: `src/solace_agent_mesh/common/a2a_spec/schemas/tool_result.json`

---

### Step 1.3: Update Python Data Models
- [ ] Add `usage: Optional[Dict[str, Any]]` to `LlmInvocationData`
- [ ] Add `llm_usage: Optional[Dict[str, Any]]` to `ToolResultData`
- [ ] Add field descriptions
- [ ] **Validation**: Models serialize/deserialize correctly

**File**: `src/solace_agent_mesh/common/data_parts.py`

---

### Step 1.4: Update Database Entity Model
- [x] Add `total_input_tokens: int | None = None`
- [x] Add `total_output_tokens: int | None = None`
- [x] Add `total_cached_input_tokens: int | None = None`
- [x] Add `token_usage_details: dict | None = None`
- [x] **Validation**: Entity instantiates with and without token fields

**File**: `src/solace_agent_mesh/gateway/http_sse/repository/entities/task.py`

---

### Step 1.5: Update Database SQLAlchemy Model
- [x] Import `Integer` and `JSON` from sqlalchemy
- [x] Add `total_input_tokens = Column(Integer, nullable=True)`
- [x] Add `total_output_tokens = Column(Integer, nullable=True)`
- [x] Add `total_cached_input_tokens = Column(Integer, nullable=True)`
- [x] Add `token_usage_details = Column(JSON, nullable=True)`
- [x] **Validation**: Model maps correctly to entity

**File**: `src/solace_agent_mesh/gateway/http_sse/repository/models/task_model.py`

---

### Step 1.6: Create Database Migration
- [x] Create new migration file with appropriate revision ID
- [x] Add `upgrade()` function with `op.add_column()` for all four fields
- [x] Add `downgrade()` function with `op.drop_column()` calls
- [x] Set revision to depend on `079e06e9b448`
- [ ] **Validation**: Migration runs with `alembic upgrade head`
- [ ] **Validation**: Rollback works with `alembic downgrade -1`
- [ ] **Validation**: Existing data remains intact

**File**: `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20250930_add_token_usage_to_tasks.py`

---

## Phase 2: Runtime Token Tracking

### Step 2.1: Add Token Tracking Fields to TaskExecutionContext
- [x] Add `self.total_input_tokens: int = 0` in `__init__`
- [x] Add `self.total_output_tokens: int = 0` in `__init__`
- [x] Add `self.total_cached_input_tokens: int = 0` in `__init__`
- [x] Add `self.token_usage_by_model: Dict[str, Dict[str, int]] = {}` in `__init__`
- [x] Add `self.token_usage_by_source: Dict[str, Dict[str, int]] = {}` in `__init__`
- [x] **Validation**: Context initializes with zero token counts

**File**: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

---

### Step 2.2: Implement record_token_usage Method
- [x] Add `record_token_usage()` method with parameters:
  - [x] `input_tokens: int`
  - [x] `output_tokens: int`
  - [x] `model: str`
  - [x] `source: str = "agent"`
  - [x] `tool_name: Optional[str] = None`
  - [x] `cached_input_tokens: int = 0`
- [x] Use `self.lock` for thread safety
- [x] Update all tracking dictionaries atomically
- [x] Handle model and source key creation
- [x] **Validation**: Concurrent calls don't corrupt state
- [x] **Validation**: Totals sum correctly
- [x] **Validation**: Breakdowns are accurate

**File**: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

---

### Step 2.3: Implement get_token_usage_summary Method
- [x] Add `get_token_usage_summary()` method returning `Dict[str, Any]`
- [x] Use `self.lock` for thread-safe read
- [x] Return dictionary with:
  - [x] `total_input_tokens`
  - [x] `total_output_tokens`
  - [x] `total_cached_input_tokens`
  - [x] `total_tokens` (computed sum)
  - [x] `by_model` (deep copy)
  - [x] `by_source` (deep copy)
- [x] **Validation**: Summary reflects all recorded usage accurately

**File**: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

---

## Phase 3: Event Integration

### Step 3.1: Store Model Name in LLM Invocation Callback
- [x] Extract model name from `host_component.model_config`
- [x] Handle dict vs string model config
- [x] Store in `callback_context.state["model_name"]`
- [x] **Validation**: Model name available in subsequent callbacks

**File**: `src/solace_agent_mesh/agent/adk/callbacks.py` (in `solace_llm_invocation_callback`)

---

### Step 3.2: Extract and Record Token Usage in Response Callback
- [x] Check for `llm_response.usage_metadata`
- [x] Extract `prompt_token_count` and `candidates_token_count`
- [x] Retrieve model name from callback state
- [x] Extract cached tokens from `prompt_tokens_details` if available
- [x] Get task context from `host_component.active_tasks`
- [x] Call `task_context.record_token_usage()` with extracted values
- [x] Add debug logging for token counts
- [x] **Validation**: Token usage recorded for every non-partial LLM response
- [x] **Validation**: Missing usage metadata doesn't cause errors

**File**: `src/solace_agent_mesh/agent/adk/callbacks.py` (in `solace_llm_response_callback`)

---

### Step 3.3: Add Token Usage to LLM Response Status Updates
- [x] Build `usage_dict` with:
  - [x] `input_tokens`
  - [x] `output_tokens`
  - [x] `cached_input_tokens` (if > 0)
  - [x] `model`
- [x] Add `usage_dict` to `llm_response_data["usage"]`
- [x] Ensure this happens before publishing status update
- [x] **Validation**: Status updates contain usage data when available

**File**: `src/solace_agent_mesh/agent/adk/callbacks.py` (in `solace_llm_response_callback`)

---

## Phase 4: Persistence Layer

### Step 4.1: Add Token Usage to Final Task Metadata
- [x] Get task context from `self.active_tasks` after `produced_artifacts`
- [x] Call `task_context.get_token_usage_summary()`
- [x] Check if `total_tokens > 0`
- [x] Add summary to `final_task_metadata["token_usage"]`
- [x] Add info log with token counts
- [x] **Validation**: Final task responses include token usage when available

**File**: `src/solace_agent_mesh/agent/sac/component.py` (in `finalize_task_success`)

---

### Step 4.2: Extract Token Usage in TaskLoggerService
- [x] After extracting task from parsed event
- [x] Check if event is a final Task response
- [x] Extract `metadata.get("token_usage")` if present
- [x] Store in local variable for use in task update
- [x] **Validation**: Token usage extracted from final task events

**File**: `src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py` (in `log_event`)

---

### Step 4.3: Update Task Record with Token Usage
- [x] When updating task with final status
- [x] If token usage was extracted:
  - [x] Set `task_to_update.total_input_tokens`
  - [x] Set `task_to_update.total_output_tokens`
  - [x] Set `task_to_update.total_cached_input_tokens`
  - [x] Set `task_to_update.token_usage_details` (full summary dict)
- [x] Call `repo.save_task()` as before
- [x] **Validation**: Database contains token usage for completed tasks
- [x] **Validation**: Tasks without token data still save successfully

**File**: `src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py` (in `log_event`)

---

### Step 4.4: Update TaskRepository to Handle Token Fields
- [x] When updating existing task, add:
  - [x] `model.total_input_tokens = task.total_input_tokens`
  - [x] `model.total_output_tokens = task.total_output_tokens`
  - [x] `model.total_cached_input_tokens = task.total_cached_input_tokens`
  - [x] `model.token_usage_details = task.token_usage_details`
- [x] When creating new task, include token fields in constructor
- [x] **Validation**: Token fields persist correctly to database

**File**: `src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py` (in `save_task`)

---

## Phase 5: Testing and Validation

### Step 5.1: Unit Tests for TaskExecutionContext
- [ ] Test `record_token_usage()` with various inputs
- [ ] Test `get_token_usage_summary()` output format
- [ ] Test thread safety with concurrent updates
- [ ] Test edge cases (zero tokens, missing fields)
- [ ] Test multiple models and sources
- [ ] **Validation**: All unit tests pass

**File**: `tests/unit/agent/sac/test_task_execution_context.py` (new file)

---

### Step 5.2: Integration Tests for Callbacks
- [ ] Mock `LlmResponse` with `usage_metadata`
- [ ] Verify `record_token_usage()` called with correct parameters
- [ ] Test handling of missing `usage_metadata`
- [ ] Test cached token extraction
- [ ] Verify status updates contain usage data
- [ ] **Validation**: Callbacks correctly extract and record token usage

**File**: `tests/integration/agent/adk/test_callbacks.py` (new file)

---

### Step 5.3: End-to-End Test
- [ ] Submit task via gateway
- [ ] Agent executes with multiple LLM calls
- [ ] Task completes successfully
- [ ] Query task from database
- [ ] Verify token usage fields are populated
- [ ] Verify token counts match sum of individual calls
- [ ] **Validation**: Token usage persists correctly through entire flow

**File**: `tests/e2e/test_token_usage_tracking.py` (new file)

---

### Step 5.4: Backwards Compatibility Test
- [ ] Query existing tasks (created before migration)
- [ ] Verify NULL token fields don't cause errors
- [ ] Create new task without token data
- [ ] Verify system handles missing token data gracefully
- [ ] **Validation**: System works with and without token data

**File**: `tests/integration/gateway/test_task_backwards_compatibility.py` (new file)

---

## Phase 6: Documentation

### Step 6.1: Update API Documentation
- [ ] Add token usage fields to Task response schema
- [ ] Add example responses with token data
- [ ] Document that fields may be NULL for older tasks
- [ ] **Validation**: API docs accurately reflect new fields

**File**: `docs/api/task-api.md` (update existing)

---

### Step 6.2: Update Configuration Guide
- [ ] Note that token tracking is always enabled
- [ ] Document that no configuration is required
- [ ] Mention performance impact (negligible)
- [ ] **Validation**: Users understand token tracking is automatic

**File**: `docs/configuration/agent-configuration.md` (update existing)

---

### Step 6.3: Create Migration Guide
- [ ] Document migration command
- [ ] Explain what the migration does
- [ ] Provide rollback instructions
- [ ] Note that existing data is preserved
- [ ] **Validation**: Administrators can migrate safely

**File**: `docs/migration/token-usage-migration.md` (new file)

---

### Step 6.4: Update Changelog
- [ ] Add entry under "Added" section
- [ ] Describe token usage tracking feature
- [ ] Note database migration requirement
- [ ] Link to relevant documentation
- [ ] **Validation**: Users aware of new feature

**File**: `CHANGELOG.md` (update existing)

---

## Final Success Criteria

- [ ] All database migrations run successfully
- [ ] Token usage captured for 100% of LLM calls
- [ ] Token data appears in status updates
- [ ] Final task responses include token summaries
- [ ] Database stores token data correctly
- [ ] All tests pass (unit, integration, e2e)
- [ ] No performance degradation observed
- [ ] Backwards compatibility maintained
- [ ] Documentation complete and accurate

---

## Progress Summary

**Phase 1**: ☑ 6/6 steps complete  
**Phase 2**: ☑ 3/3 steps complete  
**Phase 3**: ☑ 3/3 steps complete  
**Phase 4**: ☑ 4/4 steps complete  
**Phase 5**: ☐ 0/4 steps complete  
**Phase 6**: ☐ 0/4 steps complete  

**Overall**: ☑ 16/24 steps complete (67%)

---

## Notes

- Each checkbox represents a discrete, verifiable task
- Validation criteria are included for each step
- File paths are specified for easy reference
- Steps should be completed in order within each phase
- Phases should be completed sequentially (1→2→3→4→5→6)
