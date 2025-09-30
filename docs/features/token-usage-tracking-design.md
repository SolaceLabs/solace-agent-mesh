# Token Usage Tracking - Detailed Design

## Document Overview
This document provides the detailed technical design for implementing comprehensive token usage tracking throughout the Solace Agent Mesh system. It describes the data models, component interactions, data flow, and architectural decisions needed to capture, aggregate, and persist token consumption data from LLM calls.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Models](#data-models)
3. [Component Design](#component-design)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [API Contracts](#api-contracts)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Testing Strategy](#testing-strategy)

---

## 1. Architecture Overview

### 1.1 System Context

Token usage tracking spans three major layers of the system:

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Layer (SAC)                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   LiteLLM    │───▶│  Callbacks   │───▶│TaskExecution │  │
│  │   Wrapper    │    │              │    │   Context    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         │ (usage_metadata)   │ (record_token_    │          │
│         │                    │  usage())          │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Status Update Events (A2A Protocol)          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Gateway Layer (HTTP/SSE)                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ TaskLogger   │───▶│ TaskRepo     │───▶│  Database    │  │
│  │  Service     │    │              │    │  (SQLite/    │  │
│  │              │    │              │    │   Postgres)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Key Design Principles

1. **Non-Intrusive**: Token tracking should not impact the core agent execution flow
2. **Fail-Safe**: Errors in token tracking must not cause task failures
3. **Accurate**: Token counts must match provider-reported values
4. **Efficient**: Minimal overhead for tracking and aggregation
5. **Extensible**: Support for future token types (reasoning, audio, etc.)

---

## 2. Data Models

### 2.1 Runtime Token Usage Model (In-Memory)

**Location**: `TaskExecutionContext` in `task_execution_context.py`

```python
class TaskExecutionContext:
    # Token usage tracking fields
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_input_tokens: int = 0
    
    # Breakdown by model
    token_usage_by_model: Dict[str, Dict[str, int]] = {}
    # Structure: {
    #   "gpt-4o": {
    #     "input_tokens": 1500,
    #     "output_tokens": 800,
    #     "cached_input_tokens": 200
    #   }
    # }
    
    # Breakdown by source (agent vs tool)
    token_usage_by_source: Dict[str, Dict[str, int]] = {}
    # Structure: {
    #   "agent": {...},
    #   "tool:extract_content_from_artifact": {...}
    # }
```

**Thread Safety**: All token tracking operations use `task_context.lock` to ensure thread-safe updates.

### 2.2 Event-Level Token Usage Model (A2A Protocol)

**Location**: `data_parts.py` and JSON schemas

```python
# Extended LlmInvocationData
class LlmInvocationData(BaseModel):
    type: Literal["llm_invocation"]
    request: Dict[str, Any]
    usage: Optional[Dict[str, Any]] = None  # NEW FIELD
    # usage structure: {
    #   "input_tokens": int,
    #   "output_tokens": int,
    #   "cached_input_tokens": int (optional),
    #   "model": str
    # }

# Extended ToolResultData
class ToolResultData(BaseModel):
    type: Literal["tool_result"]
    tool_name: str
    result_data: Any
    function_call_id: str
    llm_usage: Optional[Dict[str, Any]] = None  # NEW FIELD
    # Same structure as LlmInvocationData.usage
```

### 2.3 Persistent Storage Model (Database)

**Location**: `task.py` (entity) and `task_model.py` (SQLAlchemy model)

```python
# Entity
class Task(BaseModel):
    id: str
    user_id: str
    start_time: int
    end_time: int | None = None
    status: str | None = None
    initial_request_text: str | None = None
    
    # NEW: Token usage fields
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_cached_input_tokens: int | None = None
    token_usage_details: dict | None = None
    # token_usage_details structure: {
    #   "total_tokens": int,
    #   "by_model": {
    #     "gpt-4o": {"input_tokens": ..., "output_tokens": ..., "cached_input_tokens": ...}
    #   },
    #   "by_source": {
    #     "agent": {...},
    #     "tool:tool_name": {...}
    #   }
    # }
```

---

## 3. Component Design

### 3.1 Token Capture Layer (LiteLLM Wrapper)

**Component**: `lite_llm.py`

**Responsibility**: Extract raw token usage from LLM provider responses

**Key Points**:
- LiteLLM already extracts `usage_metadata` from provider responses
- Contains: `prompt_token_count`, `candidates_token_count`, `total_token_count`
- Provider-specific fields (e.g., `prompt_tokens_details.cached_tokens`) are available but require explicit extraction

**Design Decision**: 
- Use existing `usage_metadata` structure from LiteLLM
- Map to our standardized field names in callbacks
- Handle provider-specific fields (like cached tokens) with defensive checks

### 3.2 Token Recording Layer (Callbacks)

**Component**: `callbacks.py`

**Responsibility**: Intercept LLM responses and record token usage

**Key Callbacks**:

1. **`solace_llm_invocation_callback` (before_model)**
   - Stores model name in `callback_context.state["model_name"]` for later use
   - No token data available yet

2. **`solace_llm_response_callback` (after_model)**
   - Extracts `usage_metadata` from `LlmResponse`
   - Retrieves model name from callback state
   - Calls `task_context.record_token_usage()`
   - Adds `usage` field to the status update event payload

**Design Pattern**: Observer pattern - callbacks observe LLM lifecycle events

### 3.3 Token Aggregation Layer (TaskExecutionContext)

**Component**: `task_execution_context.py`

**Responsibility**: Accumulate token usage across multiple LLM calls within a task

**Key Methods**:

```python
def record_token_usage(
    self,
    input_tokens: int,
    output_tokens: int,
    model: str,
    source: str = "agent",
    tool_name: Optional[str] = None,
    cached_input_tokens: int = 0,
) -> None:
    """
    Thread-safe method to record token usage from a single LLM call.
    Updates totals and breakdowns atomically.
    """

def get_token_usage_summary(self) -> Dict[str, Any]:
    """
    Returns a complete summary of token usage for the task.
    Called during task finalization.
    """
```

**Thread Safety Strategy**:
- All updates protected by `self.lock`
- Atomic read-modify-write operations
- No external state dependencies

### 3.4 Token Persistence Layer (TaskLoggerService)

**Component**: `task_logger_service.py`

**Responsibility**: Extract token usage from final task metadata and persist to database

**Integration Point**: 
- Triggered when a final `Task` response is logged
- Extracts `token_usage` from `task.metadata`
- Updates the task record with token totals and details

**Design Decision**:
- Token usage is stored as part of task finalization, not as separate events
- This ensures atomic updates and simplifies querying

---

## 4. Data Flow

### 4.1 Agent LLM Call Flow

```
1. Agent makes LLM call
   └─▶ LiteLLM.generate_content_async()
       └─▶ Provider API call
           └─▶ Response with usage_metadata

2. solace_llm_response_callback() triggered
   ├─▶ Extract usage_metadata
   ├─▶ Get model name from callback_context.state
   ├─▶ task_context.record_token_usage(
   │       input_tokens=usage.prompt_token_count,
   │       output_tokens=usage.candidates_token_count,
   │       model=model_name,
   │       source="agent",
   │       cached_input_tokens=cached_tokens
   │   )
   └─▶ Publish status update with usage data

3. TaskExecutionContext updates
   ├─▶ Increment total_input_tokens
   ├─▶ Increment total_output_tokens
   ├─▶ Increment total_cached_input_tokens
   ├─▶ Update token_usage_by_model[model_name]
   └─▶ Update token_usage_by_source["agent"]

4. Task finalization (finalize_task_success)
   ├─▶ task_context.get_token_usage_summary()
   ├─▶ Add to final_task_metadata["token_usage"]
   └─▶ Publish final Task response

5. Gateway receives final Task
   ├─▶ TaskLoggerService.log_event()
   ├─▶ Extract metadata["token_usage"]
   ├─▶ TaskRepository.save_task() with token fields
   └─▶ Database persistence
```

### 4.2 Tool LLM Call Flow

```
1. Tool makes LLM call (e.g., extract_content_from_artifact)
   └─▶ Similar to agent flow, but with source="tool"

2. Tool callback records usage
   ├─▶ task_context.record_token_usage(
   │       ...,
   │       source="tool",
   │       tool_name="extract_content_from_artifact"
   │   )
   └─▶ Publish ToolResultData with llm_usage field

3. Aggregation continues as normal
   └─▶ token_usage_by_source["tool:extract_content_from_artifact"]
```

**Note**: Tool LLM tracking is a Phase 2 enhancement. Initial implementation focuses on agent-level tracking.

---

## 5. Database Schema

### 5.1 Schema Changes

**Table**: `tasks`

**New Columns**:
```sql
-- Aggregated totals for efficient querying
total_input_tokens INTEGER NULL,
total_output_tokens INTEGER NULL,
total_cached_input_tokens INTEGER NULL,

-- Detailed breakdown as JSON
token_usage_details JSON NULL
```

**Indexes** (Future optimization):
```sql
-- For cost analysis queries
CREATE INDEX idx_tasks_total_tokens 
ON tasks(total_input_tokens + total_output_tokens);

-- For filtering by token usage
CREATE INDEX idx_tasks_input_tokens ON tasks(total_input_tokens);
CREATE INDEX idx_tasks_output_tokens ON tasks(total_output_tokens);
```

### 5.2 Migration Strategy

**File**: `alembic/versions/YYYYMMDD_<hash>_add_token_usage_to_tasks.py`

**Approach**:
1. Add columns as nullable (backwards compatible)
2. No default values (NULL for existing tasks)
3. No data migration needed (historical tasks remain without token data)

**Rollback**:
- Simple column drops
- No data loss (token data is supplementary)

---

## 6. API Contracts

### 6.1 Internal API (TaskExecutionContext)

```python
# Recording token usage
task_context.record_token_usage(
    input_tokens: int,           # Required
    output_tokens: int,          # Required
    model: str,                  # Required
    source: str = "agent",       # "agent" or "tool"
    tool_name: Optional[str] = None,  # Required if source="tool"
    cached_input_tokens: int = 0      # Optional
) -> None

# Retrieving summary
summary = task_context.get_token_usage_summary()
# Returns: {
#   "total_input_tokens": int,
#   "total_output_tokens": int,
#   "total_cached_input_tokens": int,
#   "total_tokens": int,
#   "by_model": {...},
#   "by_source": {...}
# }
```

### 6.2 A2A Protocol Extensions

**LLM Invocation Event** (`llm_invocation.json`):
```json
{
  "type": "llm_invocation",
  "request": {...},
  "usage": {
    "input_tokens": 1500,
    "output_tokens": 800,
    "cached_input_tokens": 200,
    "model": "gpt-4o"
  }
}
```

**Tool Result Event** (`tool_result.json`):
```json
{
  "type": "tool_result",
  "tool_name": "extract_content",
  "result_data": {...},
  "function_call_id": "call_123",
  "llm_usage": {
    "input_tokens": 500,
    "output_tokens": 200,
    "model": "gpt-4o-mini"
  }
}
```

**Final Task Response**:
```json
{
  "id": "task_123",
  "status": {...},
  "metadata": {
    "agent_name": "research_agent",
    "token_usage": {
      "total_input_tokens": 2500,
      "total_output_tokens": 1200,
      "total_cached_input_tokens": 300,
      "total_tokens": 3700,
      "by_model": {
        "gpt-4o": {
          "input_tokens": 2000,
          "output_tokens": 1000,
          "cached_input_tokens": 300
        },
        "gpt-4o-mini": {
          "input_tokens": 500,
          "output_tokens": 200,
          "cached_input_tokens": 0
        }
      },
      "by_source": {
        "agent": {
          "input_tokens": 2000,
          "output_tokens": 1000,
          "cached_input_tokens": 300
        },
        "tool:extract_content_from_artifact": {
          "input_tokens": 500,
          "output_tokens": 200,
          "cached_input_tokens": 0
        }
      }
    }
  }
}
```

### 6.3 Database API (TaskRepository)

No changes to method signatures. Existing methods handle new fields automatically:

```python
# Saving task with token usage
task = Task(
    id="task_123",
    user_id="user_456",
    start_time=now_epoch_ms(),
    total_input_tokens=2500,
    total_output_tokens=1200,
    total_cached_input_tokens=300,
    token_usage_details={...}
)
repo.save_task(task)

# Querying tasks (future enhancement)
tasks = repo.search(
    user_id="user_456",
    # Future: min_total_tokens=1000
)
```

---

## 7. Error Handling

### 7.1 Error Scenarios and Mitigation

| Scenario | Impact | Mitigation Strategy |
|----------|--------|---------------------|
| Provider doesn't return usage_metadata | No token data recorded | Log warning, continue task execution normally |
| Cached token field missing | Incomplete token breakdown | Default to 0, log debug message |
| Model name unavailable | Cannot attribute to model | Use "unknown" as model name, log warning |
| TaskExecutionContext not found | Cannot record usage | Log error, skip recording (non-fatal) |
| Database save fails | Token data not persisted | Log error, task still completes successfully |
| JSON serialization error | token_usage_details not saved | Save totals only, log error with details |

### 7.2 Defensive Programming Patterns

```python
# Example: Safe extraction of cached tokens
cached_tokens = 0
if hasattr(usage, 'prompt_tokens_details') and usage.prompt_tokens_details:
    cached_tokens = getattr(usage.prompt_tokens_details, 'cached_tokens', 0)

# Example: Safe model name retrieval
model_name = callback_context.state.get("model_name") or \
             host_component.model_config or \
             "unknown"

# Example: Safe task context access
with host_component.active_tasks_lock:
    task_context = host_component.active_tasks.get(logical_task_id)

if not task_context:
    log.warning("Cannot record token usage: task context not found")
    return  # Continue without recording
```

### 7.3 Logging Strategy

- **DEBUG**: Token counts for each LLM call
- **INFO**: Task-level token summaries
- **WARNING**: Missing expected fields, fallback to defaults
- **ERROR**: Unexpected failures in token tracking (never fail the task)

---

## 8. Performance Considerations

### 8.1 Memory Overhead

**Per-Task Memory Impact**:
- Base fields: ~48 bytes (3 integers + 2 dict references)
- `token_usage_by_model`: ~100-500 bytes (depends on # of models used)
- `token_usage_by_source`: ~100-500 bytes (depends on # of tools used)
- **Total per task**: ~250-1000 bytes

**Assessment**: Negligible for typical workloads (< 1KB per task)

### 8.2 CPU Overhead

**Per LLM Call**:
- Dictionary lookups: O(1)
- Integer additions: O(1)
- Lock acquisition: ~microseconds
- **Total**: < 1ms per LLM call

**Assessment**: Negligible compared to LLM call latency (100ms-10s)

### 8.3 Database Impact

**Write Operations**:
- Token fields added to existing task update (no extra queries)
- JSON column for details (single write)

**Read Operations**:
- No impact on existing queries (new columns are nullable)
- Future indexes can optimize token-based queries

**Assessment**: No measurable impact on database performance

### 8.4 Network Impact

**Status Update Events**:
- Additional ~100-200 bytes per LLM response event
- Negligible compared to typical event payload sizes (1-10KB)

**Assessment**: No significant network overhead

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Component**: `TaskExecutionContext`
- Test `record_token_usage()` with various inputs
- Test `get_token_usage_summary()` output format
- Test thread safety with concurrent updates
- Test edge cases (zero tokens, missing fields)

**Component**: Callbacks
- Mock `LlmResponse` with usage_metadata
- Verify `record_token_usage()` is called with correct parameters
- Test handling of missing usage_metadata
- Test cached token extraction

**Component**: `TaskRepository`
- Test saving tasks with token usage fields
- Test saving tasks without token usage (backwards compatibility)
- Test querying tasks (existing behavior unchanged)

### 9.2 Integration Tests

**Scenario 1**: Single LLM call task
- Execute simple task with one LLM call
- Verify token usage in final task metadata
- Verify database persistence

**Scenario 2**: Multi-turn conversation
- Execute task with multiple LLM calls
- Verify cumulative token counts
- Verify breakdown by model (if multiple models used)

**Scenario 3**: Task with tool LLM calls (Phase 2)
- Execute task where tool makes LLM call
- Verify token usage attributed to tool
- Verify breakdown by source

**Scenario 4**: Provider without usage_metadata
- Mock provider that doesn't return usage data
- Verify task completes successfully
- Verify token fields are NULL in database

### 9.3 End-to-End Tests

**Test Case**: Complete task lifecycle
1. Submit task via gateway
2. Agent executes with multiple LLM calls
3. Task completes successfully
4. Query task from database
5. Verify token usage fields are populated correctly
6. Verify token counts match sum of individual LLM calls

### 9.4 Performance Tests

**Load Test**: 100 concurrent tasks
- Measure memory usage growth
- Measure task completion time (should be unchanged)
- Measure database write latency (should be unchanged)

**Stress Test**: Task with 50+ LLM calls
- Verify token aggregation remains accurate
- Verify no memory leaks
- Verify lock contention is minimal

---

## 10. Phased Implementation Approach

### Phase 1: Core Infrastructure (MVP)
**Scope**: Agent-level token tracking only
- Add fields to `TaskExecutionContext`
- Implement `record_token_usage()` and `get_token_usage_summary()`
- Update `solace_llm_response_callback()`
- Add token usage to final task metadata
- Database schema migration
- Update `TaskLoggerService` to persist token data

**Deliverable**: Token usage tracked and stored for all agent LLM calls

### Phase 2: Tool LLM Tracking
**Scope**: Extend to tool-originated LLM calls
- Identify tools that make LLM calls
- Add tool-specific callbacks or wrappers
- Update `record_token_usage()` calls with `source="tool"`
- Verify breakdown by source in final metadata

**Deliverable**: Complete token attribution (agent vs tool)

### Phase 3: Enhanced Reporting
**Scope**: Query and analysis capabilities
- Add database indexes for token-based queries
- Extend repository with token filtering methods
- Add API endpoints for token usage reports
- Dashboard visualizations (if applicable)

**Deliverable**: Token usage analytics and reporting

### Phase 4: Advanced Features
**Scope**: Cost calculation, quotas, alerts
- Integrate pricing data (per model)
- Calculate costs from token counts
- Implement token usage quotas
- Add alerting for high usage

**Deliverable**: Complete cost management system

---

## 11. Open Design Questions

### 11.1 Resolved Questions
- **Q**: Should we track tokens per LLM call or only aggregated?
  - **A**: Aggregate at task level, but include in status events for observability

- **Q**: How to handle provider-specific token types?
  - **A**: Use optional fields, default to 0 if not available

- **Q**: Should token tracking be configurable (on/off)?
  - **A**: No, always enabled. Minimal overhead and high value.

### 11.2 Deferred Questions (Future Work)
- Should we expose token usage in public APIs?
- Should we implement token-based rate limiting?
- Should we track token usage per user/organization?
- Should we implement cost calculation (tokens → dollars)?

---

## 12. References

### 12.1 Related Documents
- `docs/features/token-usage-tracking.md` - Feature requirements
- `../sam-info-docs/litellm-token-counts-from-sdk.md` - LiteLLM token handling

### 12.2 Code References
- `src/solace_agent_mesh/agent/adk/models/lite_llm.py` - LLM wrapper
- `src/solace_agent_mesh/agent/adk/callbacks.py` - Callback system
- `src/solace_agent_mesh/agent/sac/task_execution_context.py` - Task state
- `src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py` - Persistence

### 12.3 External References
- [LiteLLM Usage Tracking](https://docs.litellm.ai/docs/completion/usage)
- [OpenAI Token Counting](https://platform.openai.com/docs/guides/token-counting)
- [Anthropic Prompt Caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-09-30 | AI Assistant | Initial detailed design |
