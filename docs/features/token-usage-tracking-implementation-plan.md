# Token Usage Tracking - Implementation Plan

## Document Overview
This document provides a step-by-step implementation plan for adding comprehensive token usage tracking to the Solace Agent Mesh system. It breaks down the work into logical phases with numbered steps that can be referenced during implementation and code review.

## Table of Contents
1. [Phase 1: Data Models and Schema](#phase-1-data-models-and-schema)
2. [Phase 2: Runtime Token Tracking](#phase-2-runtime-token-tracking)
3. [Phase 3: Event Integration](#phase-3-event-integration)
4. [Phase 4: Persistence Layer](#phase-4-persistence-layer)
5. [Phase 5: Testing and Validation](#phase-5-testing-and-validation)
6. [Phase 6: Documentation](#phase-6-documentation)

---

## Phase 1: Data Models and Schema

### Objective
Establish the foundational data structures for token usage tracking across all layers of the system.

### Steps

#### Step 1.1: Update JSON Schemas for A2A Protocol
**File**: `src/solace_agent_mesh/common/a2a_spec/schemas/llm_invocation.json`

**Action**: Add optional `usage` field to the LLM invocation schema.

**Changes**:
- Add `usage` property to the schema with nested structure for `input_tokens`, `output_tokens`, `cached_input_tokens`, and `model`
- Mark `usage` as optional (not in `required` array)
- Add descriptions for each token field

**Validation**: Schema should validate both with and without the `usage` field.

---

#### Step 1.2: Update Tool Result JSON Schema
**File**: `src/solace_agent_mesh/common/a2a_spec/schemas/tool_result.json`

**Action**: Add optional `llm_usage` field to the tool result schema.

**Changes**:
- Add `llm_usage` property with same structure as LLM invocation usage
- Mark as optional
- Add descriptions

**Validation**: Schema should validate tool results with and without LLM usage data.

---

#### Step 1.3: Update Python Data Models
**File**: `src/solace_agent_mesh/common/data_parts.py`

**Action**: Add `usage` and `llm_usage` fields to Pydantic models.

**Changes**:
- Add `usage: Optional[Dict[str, Any]]` field to `LlmInvocationData`
- Add `llm_usage: Optional[Dict[str, Any]]` field to `ToolResultData`
- Add field descriptions matching the JSON schemas

**Validation**: Models should serialize/deserialize correctly with optional fields.

---

#### Step 1.4: Update Database Entity Model
**File**: `src/solace_agent_mesh/gateway/http_sse/repository/entities/task.py`

**Action**: Add token usage fields to the Task entity.

**Changes**:
- Add `total_input_tokens: int | None = None`
- Add `total_output_tokens: int | None = None`
- Add `total_cached_input_tokens: int | None = None`
- Add `token_usage_details: dict | None = None`

**Validation**: Entity should instantiate with and without token fields.

---

#### Step 1.5: Update Database SQLAlchemy Model
**File**: `src/solace_agent_mesh/gateway/http_sse/repository/models/task_model.py`

**Action**: Add token usage columns to the TaskModel.

**Changes**:
- Import `Integer` and `JSON` from sqlalchemy
- Add `total_input_tokens = Column(Integer, nullable=True)`
- Add `total_output_tokens = Column(Integer, nullable=True)`
- Add `total_cached_input_tokens = Column(Integer, nullable=True)`
- Add `token_usage_details = Column(JSON, nullable=True)`

**Validation**: Model should map correctly to entity.

---

#### Step 1.6: Create Database Migration
**File**: `src/solace_agent_mesh/gateway/http_sse/alembic/versions/YYYYMMDD_<hash>_add_token_usage_to_tasks.py`

**Action**: Create Alembic migration to add token usage columns.

**Changes**:
- Create new migration file with appropriate revision ID
- Add `upgrade()` function with `op.add_column()` calls for all four fields
- Add `downgrade()` function with `op.drop_column()` calls
- Set revision to depend on `079e06e9b448`

**Validation**: 
- Migration should run successfully with `alembic upgrade head`
- Rollback should work with `alembic downgrade -1`
- Existing data should remain intact

---

## Phase 2: Runtime Token Tracking

### Objective
Implement in-memory token tracking during task execution.

### Steps

#### Step 2.1: Add Token Tracking Fields to TaskExecutionContext
**File**: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

**Action**: Add token tracking state to the context class.

**Changes in `__init__`**:
- Add `self.total_input_tokens: int = 0`
- Add `self.total_output_tokens: int = 0`
- Add `self.total_cached_input_tokens: int = 0`
- Add `self.token_usage_by_model: Dict[str, Dict[str, int]] = {}`
- Add `self.token_usage_by_source: Dict[str, Dict[str, int]] = {}`

**Validation**: Context should initialize with zero token counts.

---

#### Step 2.2: Implement record_token_usage Method
**File**: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

**Action**: Add method to record token usage from a single LLM call.

**Changes**:
- Add `record_token_usage()` method with parameters:
  - `input_tokens: int`
  - `output_tokens: int`
  - `model: str`
  - `source: str = "agent"`
  - `tool_name: Optional[str] = None`
  - `cached_input_tokens: int = 0`
- Use `self.lock` for thread safety
- Update all tracking dictionaries atomically
- Handle model and source key creation

**Validation**: 
- Concurrent calls should not corrupt state
- Totals should sum correctly
- Breakdowns should be accurate

---

#### Step 2.3: Implement get_token_usage_summary Method
**File**: `src/solace_agent_mesh/agent/sac/task_execution_context.py`

**Action**: Add method to retrieve complete token usage summary.

**Changes**:
- Add `get_token_usage_summary()` method returning `Dict[str, Any]`
- Use `self.lock` for thread-safe read
- Return dictionary with:
  - `total_input_tokens`
  - `total_output_tokens`
  - `total_cached_input_tokens`
  - `total_tokens` (computed sum)
  - `by_model` (deep copy of dict)
  - `by_source` (deep copy of dict)

**Validation**: Summary should reflect all recorded usage accurately.

---

## Phase 3: Event Integration

### Objective
Integrate token tracking into the LLM callback system and status updates.

### Steps

#### Step 3.1: Store Model Name in LLM Invocation Callback
**File**: `src/solace_agent_mesh/agent/adk/callbacks.py`

**Action**: Capture model name for later use in response callback.

**Changes in `solace_llm_invocation_callback`**:
- Extract model name from `host_component.model_config`
- Handle dict vs string model config
- Store in `callback_context.state["model_name"]`

**Validation**: Model name should be available in subsequent callbacks.

---

#### Step 3.2: Extract and Record Token Usage in Response Callback
**File**: `src/solace_agent_mesh/agent/adk/callbacks.py`

**Action**: Extract usage metadata and record in task context.

**Changes in `solace_llm_response_callback`**:
- Check for `llm_response.usage_metadata`
- Extract `prompt_token_count` and `candidates_token_count`
- Retrieve model name from callback state
- Extract cached tokens from `prompt_tokens_details` if available
- Get task context from `host_component.active_tasks`
- Call `task_context.record_token_usage()` with extracted values
- Add debug logging for token counts

**Validation**: 
- Token usage should be recorded for every non-partial LLM response
- Missing usage metadata should not cause errors

---

#### Step 3.3: Add Token Usage to LLM Response Status Updates
**File**: `src/solace_agent_mesh/agent/adk/callbacks.py`

**Action**: Include token usage in the status update payload.

**Changes in `solace_llm_response_callback`**:
- After extracting usage, build `usage_dict` with:
  - `input_tokens`
  - `output_tokens`
  - `cached_input_tokens` (if > 0)
  - `model`
- Add `usage_dict` to `llm_response_data["usage"]`
- Ensure this happens before publishing status update

**Validation**: Status updates should contain usage data when available.

---

## Phase 4: Persistence Layer

### Objective
Save token usage data to the database when tasks complete.

### Steps

#### Step 4.1: Add Token Usage to Final Task Metadata
**File**: `src/solace_agent_mesh/agent/sac/component.py`

**Action**: Include token summary in final task response.

**Changes in `finalize_task_success`**:
- After adding `produced_artifacts` to metadata
- Get task context from `self.active_tasks`
- Call `task_context.get_token_usage_summary()`
- Check if `total_tokens > 0`
- Add summary to `final_task_metadata["token_usage"]`
- Add info log with token counts

**Validation**: Final task responses should include token usage when available.

---

#### Step 4.2: Extract Token Usage in TaskLoggerService
**File**: `src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py`

**Action**: Extract token usage from task metadata when logging.

**Changes in `log_event` method**:
- After extracting task from parsed event
- Check if event is a final Task response
- Extract `metadata.get("token_usage")` if present
- Store in local variable for use in task update

**Validation**: Token usage should be extracted from final task events.

---

#### Step 4.3: Update Task Record with Token Usage
**File**: `src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py`

**Action**: Save token usage to database when finalizing task.

**Changes in `log_event` method**:
- When updating task with final status
- If token usage was extracted:
  - Set `task_to_update.total_input_tokens`
  - Set `task_to_update.total_output_tokens`
  - Set `task_to_update.total_cached_input_tokens`
  - Set `task_to_update.token_usage_details` (full summary dict)
- Call `repo.save_task()` as before

**Validation**: 
- Database should contain token usage for completed tasks
- Tasks without token data should still save successfully

---

#### Step 4.4: Update TaskRepository to Handle Token Fields
**File**: `src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py`

**Action**: Ensure repository handles new token fields.

**Changes in `save_task` method**:
- When updating existing task, add:
  - `model.total_input_tokens = task.total_input_tokens`
  - `model.total_output_tokens = task.total_output_tokens`
  - `model.total_cached_input_tokens = task.total_cached_input_tokens`
  - `model.token_usage_details = task.token_usage_details`
- When creating new task, include token fields in constructor

**Validation**: Token fields should persist correctly to database.

---

## Phase 5: Testing and Validation

### Objective
Ensure token tracking works correctly across all scenarios.

### Steps

#### Step 5.1: Unit Tests for TaskExecutionContext
**File**: `tests/unit/agent/sac/test_task_execution_context.py` (new file)

**Action**: Test token tracking methods in isolation.

**Test Cases**:
- Test `record_token_usage()` with various inputs
- Test `get_token_usage_summary()` output format
- Test thread safety with concurrent updates
- Test edge cases (zero tokens, missing fields)
- Test multiple models and sources

**Validation**: All unit tests should pass.

---

#### Step 5.2: Integration Tests for Callbacks
**File**: `tests/integration/agent/adk/test_callbacks.py` (new file)

**Action**: Test callback integration with mocked LLM responses.

**Test Cases**:
- Mock `LlmResponse` with `usage_metadata`
- Verify `record_token_usage()` is called with correct parameters
- Test handling of missing `usage_metadata`
- Test cached token extraction
- Verify status updates contain usage data

**Validation**: Callbacks should correctly extract and record token usage.

---

#### Step 5.3: End-to-End Test
**File**: `tests/e2e/test_token_usage_tracking.py` (new file)

**Action**: Test complete flow from LLM call to database persistence.

**Test Cases**:
- Submit task via gateway
- Agent executes with multiple LLM calls
- Task completes successfully
- Query task from database
- Verify token usage fields are populated
- Verify token counts match sum of individual calls

**Validation**: Token usage should persist correctly through entire flow.

---

#### Step 5.4: Backwards Compatibility Test
**File**: `tests/integration/gateway/test_task_backwards_compatibility.py` (new file)

**Action**: Ensure existing tasks without token data still work.

**Test Cases**:
- Query existing tasks (created before migration)
- Verify NULL token fields don't cause errors
- Create new task without token data
- Verify system handles missing token data gracefully

**Validation**: System should work with and without token data.

---

## Phase 6: Documentation

### Objective
Document the new feature for users and developers.

### Steps

#### Step 6.1: Update API Documentation
**File**: `docs/api/task-api.md` (update existing)

**Action**: Document new token usage fields in Task API.

**Changes**:
- Add token usage fields to Task response schema
- Add example responses with token data
- Document that fields may be NULL for older tasks

**Validation**: API docs should accurately reflect new fields.

---

#### Step 6.2: Update Configuration Guide
**File**: `docs/configuration/agent-configuration.md` (update existing)

**Action**: Document any configuration related to token tracking.

**Changes**:
- Note that token tracking is always enabled
- Document that no configuration is required
- Mention performance impact (negligible)

**Validation**: Users should understand token tracking is automatic.

---

#### Step 6.3: Create Migration Guide
**File**: `docs/migration/token-usage-migration.md` (new file)

**Action**: Guide administrators through database migration.

**Changes**:
- Document migration command
- Explain what the migration does
- Provide rollback instructions
- Note that existing data is preserved

**Validation**: Administrators should be able to migrate safely.

---

#### Step 6.4: Update Changelog
**File**: `CHANGELOG.md` (update existing)

**Action**: Document the new feature in the changelog.

**Changes**:
- Add entry under "Added" section
- Describe token usage tracking feature
- Note database migration requirement
- Link to relevant documentation

**Validation**: Users should be aware of the new feature.

---

## Implementation Order

The phases should be implemented in the following order:

1. **Phase 1** (Data Models and Schema) - Foundation for everything else
2. **Phase 2** (Runtime Token Tracking) - Core tracking logic
3. **Phase 3** (Event Integration) - Connect tracking to LLM calls
4. **Phase 4** (Persistence Layer) - Save data to database
5. **Phase 5** (Testing and Validation) - Ensure correctness
6. **Phase 6** (Documentation) - Document for users

Within each phase,  steps should be completed in the order listed.

## Rollback Plan

If issues are discovered after deployment:

1. **Immediate**: Rollback database migration using `alembic downgrade -1`
2. **Code**: Revert code changes via git
3. **Data**: Token usage data is supplementary; no data loss occurs on rollback
4. **Testing**: Fix issues and re-test before re-deployment

## Success Criteria

The implementation is complete when:

1. ✅ All database migrations run successfully
2. ✅ Token usage is captured for 100% of LLM calls
3. ✅ Token data appears in status updates
4. ✅ Final task responses include token summaries
5. ✅ Database stores token data correctly
6. ✅ All tests pass (unit, integration, e2e)
7. ✅ No performance degradation observed
8. ✅ Backwards compatibility maintained
9. ✅ Documentation is complete and accurate

## Risk Mitigation

### Risk: Provider Inconsistency
**Mitigation**: Use defensive checks when extracting provider-specific fields (e.g., cached tokens)

### Risk: Thread Safety Issues
**Mitigation**: Use locks consistently in TaskExecutionContext methods

### Risk: Database Migration Failure
**Mitigation**: Test migration on copy of production data before deploying

### Risk: Performance Impact
**Mitigation**: Profile token tracking code to ensure minimal overhead

## Estimated Effort

- **Phase 1**: 4-6 hours (schema and model updates)
- **Phase 2**: 3-4 hours (context tracking logic)
- **Phase 3**: 4-6 hours (callback integration)
- **Phase 4**: 3-4 hours (persistence layer)
- **Phase 5**: 8-10 hours (comprehensive testing)
- **Phase 6**: 3-4 hours (documentation)

**Total**: 25-34 hours

## Dependencies

- Python 3.10+
- SQLAlchemy 2.x
- Alembic (for migrations)
- Pydantic 2.x
- Existing A2A protocol infrastructure
- LiteLLM library (already in use)

## Notes

- Token tracking is designed to be non-intrusive and fail-safe
- Missing token data should never cause task failures
- All token fields are nullable for backwards compatibility
- The feature is always enabled; no configuration toggle is provided
- Token counts are advisory; they should be validated against provider invoices for billing purposes

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-09-30 | AI Assistant | Initial implementation plan |
