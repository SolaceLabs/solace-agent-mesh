# Background Task Cancellation Fix - Implementation & Test Plan

## Overview

This document describes the fix for properly cancelling timed-out background tasks in the solace-chat production environment. The issue was that background tasks would timeout but continue generating events, leading to queue overflow and system unresponsiveness.

## Problem Statement

### Root Cause
1. **801 active tasks** accumulated in the database
2. Background tasks timed out but were only marked as "timeout" in the database
3. **No cancellation messages were sent to agents**, so they continued processing
4. Agents kept generating events (status updates, logs, visualizations)
5. Events filled 200-message queues faster than they could be consumed
6. System became unresponsive due to queue overflow

### Missing Piece
The `BackgroundTaskMonitor` was missing the `agent_name` field needed to send cancellation requests to agents.

## Solution

### Changes Made

#### 1. Database Migration
**File:** `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20260213_add_agent_name_to_tasks.py`

- Added `agent_name` column to `tasks` table
- Added index on `agent_name` for efficient queries
- Column is nullable to support existing tasks

#### 2. Data Model Updates
**Files:**
- `src/solace_agent_mesh/gateway/http_sse/repository/entities/task.py`
- `src/solace_agent_mesh/gateway/http_sse/repository/models/task_model.py`

Added `agent_name: str | None = None` field to Task entity and TaskModel.

#### 3. Task Repository Updates
**File:** `src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py`

Updated `save_task()` method to handle `agent_name` in both create and update operations.

#### 4. Task Logger Service Updates
**File:** `src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py`

- Extract `agent_name` from message metadata during task creation
- Store `agent_name` in task record
- Supports both `agent_name` and `workflow_name` metadata fields

#### 5. Background Task Monitor Fix (CRITICAL)
**File:** `src/solace_agent_mesh/gateway/http_sse/services/background_task_monitor.py`

**Before:**
```python
# Update task status in database
task.status = "timeout"
task.end_time = current_time
repo.save_task(db, task)

# Note: We can't easily cancel the actual agent task from here
# without knowing the agent name.
```

**After:**
```python
# Update task status in database
task.status = "timeout"
task.end_time = current_time
repo.save_task(db, task)

# Actually send cancel message to the agent
if task.agent_name:
    await self.task_service.cancel_task(
        agent_name=task.agent_name,
        task_id=task.id,
        client_id="background_task_monitor",
        user_id=task.user_id or "system"
    )
    log.info(f"Sent cancellation to agent '{task.agent_name}'")
else:
    log.warning(f"Task {task.id} has no agent_name, cannot cancel")
```

## Testing Strategy

### Unit Tests
**File:** `tests/gateway/http_sse/services/test_background_task_monitor_cancellation.py`

Test cases:
1. ✅ Cancel timed-out task WITH agent_name - verifies cancellation is sent
2. ✅ Cancel timed-out task WITHOUT agent_name - verifies graceful handling
3. ✅ Multiple timed-out tasks - verifies batch processing
4. ✅ Task within timeout - verifies no false positives
5. ✅ Cancellation failure - verifies error handling
6. ✅ Custom timeout per task - verifies timeout calculation

**Run tests:**
```bash
pytest tests/gateway/http_sse/services/test_background_task_monitor_cancellation.py -v
```

### Integration Test Plan

#### Test 1: End-to-End Background Task Timeout
**Objective:** Verify that a background task times out and receives cancellation

**Steps:**
1. Start a background task with 5-minute timeout
2. Let it run for 6 minutes without activity
3. Wait for background task monitor to run (5-minute interval)
4. Verify:
   - Task status changed to "timeout" in database
   - Cancellation message sent to agent (check logs)
   - Agent stops generating events
   - No queue overflow warnings

**Expected Result:**
```
[BackgroundTaskMonitor] Task task-123 exceeded timeout: 360000ms since last activity (timeout: 300000ms)
[BackgroundTaskMonitor] Sent cancellation request to agent 'TestAgent' for task task-123
[BackgroundTaskMonitor] Marked task task-123 as timed out
```

#### Test 2: Legacy Task Without Agent Name
**Objective:** Verify graceful handling of tasks created before the fix

**Steps:**
1. Manually create a task in database without `agent_name`
2. Set `last_activity_time` to trigger timeout
3. Wait for monitor to run
4. Verify:
   - Task marked as "timeout"
   - Warning logged about missing agent_name
   - No crash or exception

**Expected Result:**
```
[BackgroundTaskMonitor] Task task-456 has no agent_name, cannot send cancellation to agent
[BackgroundTaskMonitor] Marked task task-456 as timed out
```

#### Test 3: Production Load Test
**Objective:** Verify fix works under production load

**Steps:**
1. Deploy to staging environment
2. Create 50 background tasks
3. Let 25 of them timeout
4. Monitor for 1 hour
5. Verify:
   - All timed-out tasks receive cancellations
   - Queue sizes remain below 80%
   - No system unresponsiveness
   - Active task count decreases

**Metrics to Monitor:**
- Active task count (should decrease)
- Queue depth (should stay < 160/200)
- Cancellation success rate
- System response time

#### Test 4: Agent Cancellation Response
**Objective:** Verify agents properly handle cancellation

**Steps:**
1. Start a long-running background task
2. Trigger timeout
3. Verify agent:
   - Receives cancellation message
   - Stops processing
   - Sends final status update
   - Cleans up resources

**Check Agent Logs:**
```
[Agent] Received cancellation request for task task-789
[Agent] Stopping task execution
[Agent] Sent final status: cancelled
```

### Manual Testing Checklist

- [ ] Run database migration on test environment
- [ ] Verify migration adds `agent_name` column
- [ ] Create new background task and verify `agent_name` is stored
- [ ] Trigger timeout and verify cancellation is sent
- [ ] Check agent logs for cancellation receipt
- [ ] Verify queue depths remain healthy
- [ ] Test with multiple concurrent timeouts
- [ ] Verify existing tasks (NULL agent_name) don't crash system

### Rollback Plan

If issues occur:

1. **Immediate:** Restart pods to clear queues (temporary relief)
2. **Code Rollback:** Revert to previous version
3. **Database:** Migration can be rolled back safely (column is nullable)

```bash
# Rollback migration
cd src/solace_agent_mesh/gateway/http_sse
alembic downgrade -1
```

## Deployment Plan

### Phase 1: Staging Deployment (Week 1)
1. Deploy to staging environment
2. Run integration tests
3. Monitor for 48 hours
4. Verify no regressions

### Phase 2: Production Deployment (Week 2)
1. Deploy during low-traffic window
2. Monitor queue depths closely
3. Watch for cancellation logs
4. Track active task count

### Phase 3: Monitoring (Ongoing)
1. Set up alerts for:
   - Active task count > 500
   - Queue depth > 80%
   - Cancellation failure rate > 10%
2. Weekly review of timeout statistics

## Success Criteria

✅ **Primary Goals:**
- Timed-out background tasks receive cancellation messages
- Agents stop generating events after cancellation
- Queue overflow incidents eliminated

✅ **Metrics:**
- Active task count stays < 100
- Queue depth stays < 80%
- Zero system unresponsiveness incidents
- Cancellation success rate > 95%

## Related Issues

- **Original Issue:** 801 active tasks causing queue overflow
- **Root Cause:** Background tasks not actually cancelled
- **Impact:** Production system unresponsive, requiring pod restart

## Future Improvements

1. **Stale Task Cleanup Service** (Phase 2)
   - Automatically clean up tasks with no activity for 24h
   - Prevent accumulation of orphaned tasks

2. **Queue Size Increase** (Phase 1)
   - Increase from 200 to 2000-5000
   - Provide buffer during high load

3. **Backpressure Mechanism** (Phase 3)
   - Slow down event generation when queues are full
   - Prevent overflow at the source

4. **Enhanced Monitoring** (Phase 2)
   - Dashboard for task lifecycle metrics
   - Real-time queue depth visualization
   - Alert on anomalies

## References

- [Background Task Monitor Service](src/solace_agent_mesh/gateway/http_sse/services/background_task_monitor.py)
- [Task Logger Service](src/solace_agent_mesh/gateway/http_sse/services/task_logger_service.py)
- [Task Repository](src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py)
- [Unit Tests](tests/gateway/http_sse/services/test_background_task_monitor_cancellation.py)
