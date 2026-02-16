# Stateless Agent Checkpointing at Peer-Call Boundaries

**Jira**: DATAGO-125517 (Story under Epic DATAGO-122424)
**Branch**: `ed/DATAGO-125517/stateless-agent-checkpointing`

## 1. Problem Statement

When a SAM agent dispatches work to one or more peer agents (sub-agents), the calling agent blocks — it holds the full `TaskExecutionContext` in RAM while waiting for responses. This creates two operational constraints:

1. **No horizontal scaling**: The same process instance that dispatched the peer calls must receive the responses. Broker consumer groups or load-balanced replicas cannot be used because any other instance would lack the in-memory task state.
2. **No crash recovery**: If the agent process restarts while waiting for a peer response, the task state is lost. The caller's timeout eventually fires, but the user receives only a timeout error — the work done by the peer is discarded.

Both problems stem from the same root cause: task coordination state is held exclusively in RAM.

## 2. Goal and Non-Goals

### Goal

At the point where an agent pauses for peer responses (the "checkpoint boundary"), persist all task state to a database so that **any instance** of the same agent can receive the peer response and continue processing.

### Non-Goals

- **Statelessness during active processing**: While the agent is running LLM turns or executing local tools, it holds state in RAM as today. A crash during active processing is handled by existing caller-side timeouts (the caller retries or reports an error). This is acceptable because active processing is short-lived compared to the potentially long wait for peer responses.
- **Distributed lock-free coordination**: We rely on the database for atomic operations (claim, counter increment) rather than implementing a distributed consensus protocol.

## 3. Design Principles

| Principle | Rationale |
|-----------|-----------|
| **DB writes only at checkpoint boundary** | Zero overhead for tasks that don't call peers. No per-turn DB writes. |
| **Single database** | Reuses the existing ADK session database (SQLAlchemy/PostgreSQL). No new infrastructure. |
| **Dual-path response handling** | Responses check in-memory state first (fast path, pre-checkpoint) and fall back to DB (post-checkpoint). This handles the race where a peer responds before the checkpoint completes. |
| **Opt-in feature flag** | Controlled by `stateless_checkpointing: true` in agent config. Default is off. Requires `session_service: sql`. |
| **Broker ACK at checkpoint** | The original broker message is ACK'd only after the checkpoint write succeeds. Before that, un-ACK'd messages provide at-least-once delivery if the process crashes during active processing. |

## 4. Architecture Overview

### 4.1 Lifecycle of a Peer Call (Before This Change)

```
User Request → Broker → Agent Instance A
  │
  ├── ADK Runner processes LLM turns, dispatches peer calls
  ├── Runner exits with is_paused=True
  ├── Task state stays in active_tasks (RAM)
  ├── Peer sub-task IDs stored in cache service (with TTL for timeout)
  │
  ├── ... waiting for peer responses ...
  │
  ├── Peer response arrives on same instance A (required)
  ├── Claim from active_tasks (dict.pop under lock)
  ├── Record in parallel_tool_calls counter
  ├── When all complete → retrigger ADK Runner
  └── Final response → Broker → User
```

### 4.2 Lifecycle of a Peer Call (After This Change)

```
User Request → Broker → Agent Instance A
  │
  ├── ADK Runner processes LLM turns, dispatches peer calls
  ├── Runner exits with is_paused=True
  │
  ├── ═══ CHECKPOINT BOUNDARY ═══
  │   ├── 1. Serialize TaskExecutionContext → checkpoint dict
  │   ├── 2. Write to DB: paused_task + peer_sub_tasks + parallel_invocations
  │   ├── 3. ACK the original broker message
  │   ├── 4. Remove from in-memory active_tasks
  │   └── 5. Remove cache service timeout entries
  │
  ├── ... waiting for peer responses ...
  │
  ├── Peer response arrives on ANY instance (A, B, C...)
  │   ├── Try in-memory claim first → miss (task not in active_tasks)
  │   ├── Fall back to DB: atomic claim_peer_sub_task (DELETE row)
  │   ├── Record result in DB: record_parallel_result (atomic counter++)
  │   ├── If completed < total → done, wait for more
  │   └── If completed == total:
  │       ├── Restore TaskExecutionContext from DB
  │       ├── Get accumulated results from DB
  │       ├── Add to active_tasks (back in RAM)
  │       ├── Clean up all DB records
  │       └── Retrigger ADK Runner with results
  │
  └── Final response → Broker → User
```

### 4.3 Key Invariants

1. **Each peer response is processed exactly once**: The `claim_peer_sub_task()` operation is an atomic `DELETE ... WHERE sub_task_id = ?` with row-level locking (`SELECT ... FOR UPDATE`). If two instances race, only one gets the row.
2. **The parallel completion counter is atomic**: `record_parallel_result()` uses `SELECT ... FOR UPDATE` → increment → commit. Only the instance that increments to `total` triggers the restore.
3. **No orphaned state**: `cleanup_task()` deletes all three tables for a task in a single transaction after restoration.
4. **Graceful degradation**: If the checkpoint write fails, the task remains in RAM and operates on the pre-existing in-memory path.

## 5. Database Schema

Three new tables, all in the existing ADK session database.

### 5.1 `agent_paused_tasks`

The serialized task state. One row per paused task.

| Column | Type | Notes |
|--------|------|-------|
| `logical_task_id` | String, **PK** | Unique task identifier |
| `agent_name` | String, indexed | Which agent owns this checkpoint |
| `a2a_context` | Text (JSON) | Session ID, user ID, agent name, etc. |
| `effective_session_id` | String | For ADK session lookup on resume |
| `user_id` | String | For ADK session lookup on resume |
| `current_invocation_id` | String | ADK invocation to resume |
| `produced_artifacts` | Text (JSON) | Artifacts produced before pause |
| `artifact_signals_to_return` | Text (JSON) | Artifact embeds to include in response |
| `response_buffer` | Text | Accumulated text from prior turns |
| `flags` | Text (JSON) | Agent flags (e.g., deep_research_sent) |
| `security_context` | Text (JSON) | Platform trust token (SAM JWT) — see §8.4 |
| `token_usage` | Text (JSON) | Token counters by model and source |
| `checkpointed_at` | Float | Epoch timestamp |

### 5.2 `agent_peer_sub_tasks`

Pending peer calls. One row per dispatched peer call. Claimed (deleted) when the peer responds.

| Column | Type | Notes |
|--------|------|-------|
| `sub_task_id` | String, **PK** | Correlation ID for the peer call |
| `logical_task_id` | String, **FK** → agent_paused_tasks | Groups sub-tasks by parent |
| `invocation_id` | String, indexed | Groups parallel calls within an invocation |
| `correlation_data` | Text (JSON) | function_call_id, peer_tool_name, peer_agent_name, etc. |
| `timeout_deadline` | Float, indexed | Absolute epoch time for expiry |
| `created_at` | Float | When the checkpoint was written |

### 5.3 `agent_parallel_invocations`

Completion tracking for parallel peer calls. One row per invocation that dispatched multiple peers.

| Column | Type | Notes |
|--------|------|-------|
| `logical_task_id` | String, **compound PK**, **FK** → agent_paused_tasks | |
| `invocation_id` | String, **compound PK** | |
| `total_expected` | Integer | How many peer calls were dispatched |
| `completed_count` | Integer | Atomically incremented per response |
| `results` | Text (JSON) | Accumulated result array |

### ER Diagram

```
agent_paused_tasks (1) ──── (*) agent_peer_sub_tasks
       │
       └──── (*) agent_parallel_invocations
```

Foreign keys use `ON DELETE CASCADE`, and `cleanup_task()` also performs explicit deletes for SQLite compatibility.

## 6. Serialization

### 6.1 `TaskExecutionContext.to_checkpoint_dict()`

Called under the context lock. Returns a plain dict containing all checkpoint-worthy fields:

**Included** (persisted to DB):
- `task_id`, `a2a_context`, `current_invocation_id`
- `run_based_response_buffer` (accumulated agent text)
- `produced_artifacts`, `artifact_signals_to_return`
- `flags`, `security_context`
- Token usage (totals + breakdowns by model and source)
- `active_peer_sub_tasks` (used to populate `agent_peer_sub_tasks` table)
- `parallel_tool_calls` (used to populate `agent_parallel_invocations` table)

**Excluded** (non-serializable or transient):
- `cancellation_event` (asyncio.Event — recreated fresh on restore)
- `lock` (threading.Lock — recreated fresh on restore)
- `event_loop` (set to None on restore)
- `_original_solace_message` (broker message reference — ACK'd at checkpoint)
- `streaming_buffer`, `_first_text_seen_in_turn`, `_need_spacing_before_next_text` (transient streaming state — reset on restore)

All dict/list values are shallow-copied to prevent mutation after serialization.

### 6.2 `TaskExecutionContext.from_checkpoint_dict()`

Class method that reconstructs a fresh `TaskExecutionContext`. The constructor creates new non-serializable objects (lock, cancellation_event). Persisted fields are restored from the dict. `active_peer_sub_tasks` and `parallel_tool_calls` are intentionally left empty — they live in separate DB tables and results are injected at retrigger time.

## 7. Component Integration

### 7.1 Configuration

```yaml
agent:
  stateless_checkpointing: true   # Default: false
  session_service: sql             # Required — checkpointing needs a database
  session_db_url: postgresql://...
```

`stateless_checkpointing` is a field on `SamAgentAppConfig` in `app.py`. When enabled, the component initializes a `CheckpointService` using the same SQLAlchemy engine as the ADK `DatabaseSessionService`. Checkpoint tables are created via `CheckpointBase.metadata.create_all()` (idempotent) and also via Alembic migration for production deployments.

### 7.2 Checkpoint Boundary (Write Path)

In `component.py` → `finalize_task_with_cleanup()`, when `is_paused=True`:

1. Get `task_context` from `active_tasks`
2. Call `checkpoint_service.checkpoint_task(task_context, agent_name)` — single DB transaction writes all three tables
3. ACK the original broker message (state is safe in DB)
4. Remove from `active_tasks` (in-memory)
5. Remove cache service timeout entries (DB has `timeout_deadline` now)

If the checkpoint write fails, the task remains in RAM (graceful fallback to pre-existing behavior).

### 7.3 Dual-Path Response Handling (Read Path)

Three methods in `component.py` implement the dual-path pattern:

**`_claim_peer_sub_task_completion(sub_task_id)`**:
1. Try cache service → `active_tasks` → `task_context.claim_sub_task_completion()` (in-memory path)
2. If not found, try `checkpoint_service.claim_peer_sub_task(sub_task_id)` (DB path — atomic DELETE)

**`_get_correlation_data_for_sub_task(sub_task_id)`** (non-destructive, for intermediate status):
1. Try cache service → `active_tasks` → `task_context.active_peer_sub_tasks.get()` (in-memory)
2. If not found, try `checkpoint_service.get_peer_sub_task(sub_task_id)` (DB read)

**`reset_peer_timeout(sub_task_id)`**:
1. Update cache service expiry (in-memory path)
2. Also update `checkpoint_service.reset_timeout_deadline()` (DB path)

### 7.4 Final Peer Response Handling

In `event_handlers.py` → `_handle_final_peer_response()`:

- **In-memory path** (`task_context` found in `active_tasks`): Existing logic unchanged — record result in `parallel_tool_calls`, check if all complete, retrigger.
- **DB path** (`task_context` not found): Call `checkpoint_service.record_parallel_result()` atomically. If `completed < total`, return (wait for more). If `completed == total`, call `_restore_task_from_checkpoint()` helper which restores the context from DB, moves it to `active_tasks`, cleans up DB records, then retrigger.

Peer artifacts are registered on the restored context before retrigger, so artifact signals propagate correctly even on the DB path.

### 7.5 Timeout Handling

Two mechanisms run in parallel:

1. **Cache service expiry** (pre-checkpoint): The existing path fires `handle_cache_expiry_event()` when a cache entry TTL expires. This handles timeouts for tasks that haven't been checkpointed yet or when checkpointing is disabled.

2. **DB timeout sweeper** (post-checkpoint): A timer fires every 10 seconds, calling `_sweep_expired_peer_timeouts()`:
   - Queries `agent_peer_sub_tasks` for rows where `timeout_deadline < now()` AND `agent_name` matches
   - For each expired row, atomically claims it via `claim_peer_sub_task()` (prevents double-processing with normal response path)
   - Dispatches to `_handle_peer_timeout()` which records a timeout result, sends cancellation to the peer, and checks if all parallel calls are complete

The timeout deadline is computed at checkpoint time: `now + timeout_seconds`. This means the effective timeout starts from checkpoint time, not from the original dispatch time. The difference is typically sub-second.

### 7.6 Cancellation

When a cancel request arrives for a task not in `active_tasks`:

1. Look up peer sub-tasks from DB via `get_peer_sub_tasks_for_task()`
2. Send `CancelTaskRequest` to each tracked peer agent
3. Clean up all DB records via `cleanup_task()`

### 7.7 Task Restoration Helper

The `_restore_task_from_checkpoint()` method on the component centralizes the restore-and-cleanup pattern used by both the response handler and the timeout handler:

1. `restore_task()` — fetch serialized state from `agent_paused_tasks`
2. `from_checkpoint_dict()` — reconstruct `TaskExecutionContext`
3. `get_parallel_results()` — fetch accumulated results from `agent_parallel_invocations`
4. Add to `active_tasks` (task is back in RAM)
5. `cleanup_task()` — delete all DB records (task is no longer paused)
6. Return `(task_context, results_to_inject)` for the caller to retrigger

## 8. Concurrency and Atomicity

### 8.1 Row-Level Locking

`claim_peer_sub_task()` and `record_parallel_result()` use `SELECT ... FOR UPDATE` to prevent concurrent claims. This is critical when multiple agent instances receive peer responses simultaneously.

**SQLite note**: SQLite does not support `SELECT ... FOR UPDATE` — it is silently ignored. This is acceptable for development and testing (single process), but production deployments should use PostgreSQL for correctness under concurrent access from multiple instances.

### 8.2 Event Loop Serialization

Within a single agent instance, all async operations (response handling, checkpoint writing, timeout sweeping) run on the same asyncio event loop. This provides natural serialization — the checkpoint write is synchronous and blocks the event loop, preventing response handlers from running concurrently on the same instance.

### 8.3 Race Condition: Response Before Checkpoint

If a peer responds before `finalize_task_with_cleanup()` runs (the checkpoint hasn't been written yet), the response takes the in-memory path — the task is still in `active_tasks`. The checkpoint write either finds fewer pending sub-tasks (some already completed) or is skipped entirely if the task completed. This is safe because the in-memory path is the pre-existing, well-tested code path.

### 8.4 Security: What `security_context` Contains

The `security_context` field in `agent_paused_tasks` stores the `_security_context` dict from `TaskExecutionContext`. In practice, this contains a single key:

- **`auth_token`**: A SAM-signed JWT used for agent-to-agent trust propagation (enterprise only).

This token is **not** an end-user OAuth credential. It is a platform-internal JWT created by SAM's `TrustManager` and set from broker message user properties when `trust_manager` is configured (`event_handlers.py:950-953`). Its purpose is to propagate the caller's identity to peer agents during sub-task dispatch (`component.py:3469-3471`).

**Why this is not a security concern:**

1. **Already propagated before checkpoint**: By the time the checkpoint boundary is reached, the agent has already dispatched all peer calls and attached the `auth_token` to each outgoing broker message. The token in the checkpoint is a copy that was already transmitted over the wire.
2. **Short-lived**: SAM JWTs have expiration claims. A checkpointed token will typically expire within minutes.
3. **Same database**: The checkpoint lives in the same ADK session database that already stores session state. Checkpointing does not expand the trust boundary.
4. **No user credentials**: End-user OAuth flows (e.g., tool authentication) use a completely separate mechanism — the ADK credential service and the gateway's auth state cache. Those credentials never pass through `_security_context`.

**Conclusion**: Persisting `security_context` in the checkpoint does not meaningfully change the security posture. The same token is already in flight on broker messages and the same database already holds session state.

## 9. File Inventory

### New Files

| File | Purpose |
|------|---------|
| `src/solace_agent_mesh/agent/adk/checkpoint_models.py` | SQLAlchemy ORM models for the 3 checkpoint tables |
| `src/solace_agent_mesh/agent/adk/checkpoint_service.py` | `CheckpointService` class — all DB operations |
| `src/solace_agent_mesh/agent/adk/alembic/versions/c9f4a28e71b3_add_agent_checkpoint_tables.py` | Alembic migration (chains after `e2902798564d`) |
| `tests/unit/agent/adk/test_checkpoint_service.py` | 18 unit tests for CheckpointService |
| `tests/unit/agent/sac/test_task_execution_context_checkpoint.py` | 18 unit tests for serialization round-trip |

### Modified Files

| File | Changes |
|------|---------|
| `src/solace_agent_mesh/agent/sac/app.py` | Added `stateless_checkpointing` config field |
| `src/solace_agent_mesh/agent/sac/task_execution_context.py` | Added `to_checkpoint_dict()` and `from_checkpoint_dict()` |
| `src/solace_agent_mesh/agent/sac/component.py` | CheckpointService init, checkpoint boundary, dual-path claim/timeout, restore helper, sweep timer |
| `src/solace_agent_mesh/agent/protocol/event_handlers.py` | DB path in final response handler, DB-aware cancellation |

## 10. Limitations and Future Work

1. **Active processing is not stateless**: Crashes during LLM turns or local tool execution lose the task. This is by design — the checkpoint boundary is only at peer-call pauses.

2. **SQLite not safe for multi-instance**: `SELECT ... FOR UPDATE` is ignored by SQLite. Use PostgreSQL for production deployments with multiple agent instances.

3. **Timeout precision**: Timeout deadlines are computed from checkpoint time, not dispatch time. Tasks get slightly more time than configured (the delta between dispatch and checkpoint, typically sub-second).

4. **Sweep interval**: The timeout sweeper runs every 10 seconds. Expired timeouts may not be detected for up to 10 seconds after their deadline. This is configurable via `TIMEOUT_SWEEP_INTERVAL_SECONDS`.

5. **No partial restoration**: If a task has 5 parallel peer calls and 3 have completed, but the instance crashes before all 5 complete, the completed results are safely in the DB. When the remaining 2 responses arrive, the new instance will pick them up. However, if the remaining peers never respond, the timeout sweeper handles cleanup.
