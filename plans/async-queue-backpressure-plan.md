# Async Queue Backpressure & Event Loss Prevention Plan

**Created:** 2026-02-24  
**Status:** Draft  
**Priority:** High (Critical for production reliability)

## Executive Summary

The async write queue in `PersistentSSEEventBuffer` currently drops events silently when full, with no mechanism to identify affected tasks or protect critical events. This can result in:
- Tasks appearing stuck "running" forever if the final completion event is dropped
- Users experiencing data loss without any indication
- No way to detect or recover from overload conditions

This plan proposes three complementary solutions to address these issues.

---

## Problem Analysis

### Current Behavior

When the async write queue reaches capacity (default 1000 items):

1. **Events are dropped** via `put_nowait()` → `queue.Full` exception (line 677)
2. **Global counter incremented**: `_dropped_events_count += 1`
3. **Warning logged** but no further action
4. **`buffer_event()` returns `False`** but callers don't check this

```python
# Current problematic code path
except queue.Full:
    with self._dropped_events_lock:
        self._dropped_events_count += 1  # Only global count!
    log.warning("...Event dropped for task %s...")
    return False  # Callers ignore this!
```

### Impact Assessment

| Scenario | Impact | Severity |
|----------|--------|----------|
| Streaming event dropped | Minor UI glitch | Low |
| Progress update dropped | User misses status | Medium |
| Final response dropped | Task stuck "running" forever | **Critical** |
| All events for task dropped | Complete data loss | **Critical** |

### Why This Matters

**Scenario: High load during peak hours**
1. Database becomes slow (network, disk I/O)
2. Async queue fills up over ~10 seconds
3. New events start dropping
4. User's task completion event gets dropped
5. UI shows "running..." indefinitely
6. User refreshes, sees task still "running"
7. User abandons session or submits duplicate requests
8. No alerts, no metrics, no recovery

---

## Proposed Solutions

### Phase 1: Per-Task Event Loss Tracking (Week 1)

**Goal:** Track which tasks lost events and expose this information to UI.

#### 1.1 Add Per-Task Dropped Event Tracking

```python
# New fields in PersistentSSEEventBuffer
self._task_dropped_events: Dict[str, int] = {}  # task_id -> count

# Modified _buffer_event_to_db
except queue.Full:
    with self._dropped_events_lock:
        self._dropped_events_count += 1
        self._task_dropped_events[task_id] = self._task_dropped_events.get(task_id, 0) + 1
```

#### 1.2 Add `has_event_loss` Flag to Task Metadata

```python
# New method
def mark_task_event_loss(self, task_id: str) -> None:
    """Mark that a task has experienced event loss in the database."""
    # Update tasks table to set has_event_loss = True

# Check on drop
def get_tasks_with_event_loss(self) -> Set[str]:
    """Return task IDs that have experienced event loss."""
    with self._dropped_events_lock:
        return set(self._task_dropped_events.keys())
```

#### 1.3 Database Schema Change

```sql
-- Migration: Add has_event_loss column to tasks table
ALTER TABLE tasks ADD COLUMN has_event_loss BOOLEAN DEFAULT FALSE;
```

#### 1.4 API Response Enhancement

```python
# In task response DTO
class TaskResponse:
    has_event_loss: bool = False
    event_loss_count: Optional[int] = None
```

#### 1.5 UI Warning

When `has_event_loss` is True, show user warning:
> "⚠️ Some streaming events may have been lost. The final result should be complete."

---

### Phase 2: Critical Event Protection (Week 2)

**Goal:** Never drop task completion or final response events.

#### 2.1 Define Critical Event Types

```python
CRITICAL_EVENT_TYPES = {
    "task_complete",
    "task_failed",
    "final_response",
    "error",
}
```

#### 2.2 Implement Blocking Put for Critical Events

```python
def _buffer_event_to_db(
    self,
    task_id: str,
    event_type: str,
    event_data: Dict[str, Any],
    session_id: str,
    user_id: str,
    is_critical: bool = False,  # NEW PARAMETER
) -> bool:
    # ...
    
    try:
        if is_critical:
            # For critical events, block with timeout rather than drop
            self._async_write_queue.put(write_request, timeout=2.0)
            log.info(
                "%s Critical event %s for task %s queued successfully",
                self.log_identifier, event_type, task_id
            )
        else:
            self._async_write_queue.put_nowait(write_request)
        return True
        
    except queue.Full:
        if is_critical:
            # Critical event STILL couldn't be queued - this is very bad
            log.error(
                "%s CRITICAL: Failed to queue critical event %s for task %s after timeout!",
                self.log_identifier, event_type, task_id
            )
            # Fall through to synchronous write as last resort
            return self._write_event_to_db_sync_fallback(...)
        else:
            # Normal event dropped
            self._track_dropped_event(task_id)
            return False
```

#### 2.3 Add Synchronous Fallback for Critical Events

```python
def _write_event_to_db_sync_fallback(
    self,
    task_id: str,
    event_type: str,
    event_data: Dict[str, Any],
    session_id: str,
    user_id: str,
    created_time: int,
) -> bool:
    """
    Last resort: Write critical event synchronously.
    
    This blocks the caller but guarantees the event is written.
    Only used when queue is full AND blocking put times out.
    """
    log.warning(
        "%s Using synchronous fallback for critical event (queue overloaded)",
        self.log_identifier
    )
    return self._write_event_to_db_sync(
        task_id, event_type, event_data, session_id, user_id, created_time
    )
```

#### 2.4 Update Callers to Mark Critical Events

```python
# In SSEManager or gateway component
def send_final_response(self, task_id: str, response_data: Dict) -> None:
    self._persistent_buffer.buffer_event(
        task_id=task_id,
        event_type="final_response",
        event_data=response_data,
        is_critical=True,  # Never drop this!
    )
```

---

### Phase 3: Backpressure & Circuit Breaker (Week 3)

**Goal:** Prevent system from accepting more load than it can handle.

#### 3.1 Queue Health Monitoring

```python
def get_queue_health(self) -> QueueHealthStatus:
    """
    Get current queue health status.
    
    Returns:
        QueueHealthStatus with level (healthy, warning, critical) and metrics
    """
    current_size = self._async_write_queue.qsize()
    max_size = self._async_write_queue_size
    utilization = current_size / max_size
    
    if utilization < 0.5:
        level = "healthy"
    elif utilization < 0.8:
        level = "warning"
    else:
        level = "critical"
    
    return QueueHealthStatus(
        level=level,
        utilization=utilization,
        current_size=current_size,
        max_size=max_size,
        dropped_events=self._dropped_events_count,
    )
```

#### 3.2 Circuit Breaker Pattern

```python
class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Rejecting new tasks
    HALF_OPEN = "half_open"  # Testing if recovered

class AsyncQueueCircuitBreaker:
    def __init__(
        self,
        buffer: PersistentSSEEventBuffer,
        open_threshold: float = 0.9,  # Open when 90% full
        close_threshold: float = 0.5,  # Close when back to 50%
    ):
        self.buffer = buffer
        self.state = CircuitBreakerState.CLOSED
        self.open_threshold = open_threshold
        self.close_threshold = close_threshold
    
    def can_accept_new_task(self) -> bool:
        """Check if system can accept a new task."""
        if self.state == CircuitBreakerState.OPEN:
            # Check if we can transition to half-open
            health = self.buffer.get_queue_health()
            if health.utilization < self.close_threshold:
                self.state = CircuitBreakerState.HALF_OPEN
                return True  # Allow one request to test
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            # After half-open success, transition to closed
            health = self.buffer.get_queue_health()
            if health.utilization < self.close_threshold:
                self.state = CircuitBreakerState.CLOSED
            else:
                self.state = CircuitBreakerState.OPEN
                return False
        
        # CLOSED state - check if we need to open
        health = self.buffer.get_queue_health()
        if health.utilization >= self.open_threshold:
            self.state = CircuitBreakerState.OPEN
            log.warning(
                "[CircuitBreaker] OPENED - queue at %.1f%% capacity",
                health.utilization * 100
            )
            return False
        
        return True
```

#### 3.3 Integrate with Task Submission

```python
# In sessions.py or task submission endpoint
@router.post("/sessions/{session_id}/chat-tasks")
async def submit_task(...):
    # Check circuit breaker before accepting new task
    if not circuit_breaker.can_accept_new_task():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "service_overloaded",
                "message": "System is currently experiencing high load. Please try again shortly.",
                "retry_after": 5,  # seconds
            }
        )
    # ... proceed with task submission
```

#### 3.4 Expose Health Endpoint

```python
@router.get("/health/queue")
async def get_queue_health():
    """Get async write queue health status."""
    stats = buffer.get_async_queue_stats()
    health = buffer.get_queue_health()
    
    return {
        "status": health.level,
        "queue": {
            "current_size": stats["queue_size"],
            "max_size": stats["max_queue_size"],
            "utilization_percent": health.utilization * 100,
        },
        "events": {
            "dropped_total": stats["dropped_events"],
            "failed_writes_total": stats["failed_writes"],
        },
        "worker_alive": stats["worker_alive"],
    }
```

---

## Implementation Order

| Phase | Deliverable | Effort | Risk Reduction |
|-------|-------------|--------|----------------|
| 1.1-1.2 | Per-task tracking | 1 day | Medium |
| 1.3-1.5 | DB schema + UI | 2 days | Medium |
| 2.1-2.2 | Critical event protection | 1 day | **High** |
| 2.3-2.4 | Sync fallback + callers | 1 day | **High** |
| 3.1-3.2 | Health monitoring + circuit breaker | 2 days | High |
| 3.3-3.4 | Integration + endpoint | 1 day | Medium |

**Recommended priority:** Phase 2 (Critical Event Protection) first, then Phase 1, then Phase 3.

---

## Testing Strategy

### Unit Tests

```python
class TestQueueOverflow:
    def test_critical_event_not_dropped_when_queue_full(self):
        """Critical events should block, not drop."""
        buffer = create_buffer_with_full_queue()
        result = buffer.buffer_event(..., is_critical=True)
        assert result is True  # Should succeed via blocking
    
    def test_per_task_drop_tracking(self):
        """Dropped events should be tracked per task."""
        buffer.buffer_event(task_id="task-1", ...)  # Drop
        buffer.buffer_event(task_id="task-2", ...)  # Drop
        assert "task-1" in buffer.get_tasks_with_event_loss()
        assert "task-2" in buffer.get_tasks_with_event_loss()
    
    def test_circuit_breaker_opens_at_threshold(self):
        """Circuit breaker should open when queue is 90% full."""
        cb = CircuitBreaker(buffer, open_threshold=0.9)
        fill_queue_to_percent(buffer, 91)
        assert cb.can_accept_new_task() is False
```

### Integration Tests

```python
class TestBackpressureUnderLoad:
    async def test_system_degrades_gracefully_under_load(self):
        """System should return 503 rather than drop events."""
        # Submit 100 concurrent tasks
        # Verify no critical events dropped
        # Verify some tasks receive 503 when overloaded
```

---

## Metrics & Alerting

### New Prometheus Metrics

```python
# Counters
events_dropped_total = Counter('sse_events_dropped_total', 'Events dropped due to queue full')
events_written_total = Counter('sse_events_written_total', 'Events successfully written')
critical_events_sync_fallback_total = Counter('sse_critical_events_sync_fallback', 'Critical events using sync fallback')

# Gauges
queue_utilization = Gauge('sse_queue_utilization', 'Queue utilization (0-1)')
tasks_with_event_loss = Gauge('sse_tasks_with_event_loss', 'Tasks that have lost events')

# Histogram
event_queue_wait_time = Histogram('sse_event_queue_wait_seconds', 'Time event waits in queue')
```

### Alert Rules

```yaml
# Alert when queue approaching capacity
- alert: SSEQueueHighUtilization
  expr: sse_queue_utilization > 0.8
  for: 1m
  labels:
    severity: warning
  annotations:
    summary: "SSE event queue at {{ $value | humanizePercentage }} capacity"

# Alert on any dropped events
- alert: SSEEventsDropped
  expr: increase(sse_events_dropped_total[5m]) > 0
  labels:
    severity: critical
  annotations:
    summary: "SSE events are being dropped ({{ $value }} in last 5 min)"
```

---

## Rollback Plan

If issues arise:
1. Disable circuit breaker via feature flag
2. Increase queue size as temporary measure
3. Revert to previous synchronous behavior as last resort

```python
# Feature flags
ENABLE_CIRCUIT_BREAKER = os.getenv("SSE_ENABLE_CIRCUIT_BREAKER", "true") == "true"
ENABLE_CRITICAL_EVENT_PROTECTION = os.getenv("SSE_CRITICAL_EVENT_PROTECTION", "true") == "true"
ASYNC_QUEUE_SIZE = int(os.getenv("SSE_ASYNC_QUEUE_SIZE", "1000"))
```

---

## Open Questions

1. **Queue size tuning:** What's the right default? 1000 may be too small for high-traffic deployments.

2. **Timeout values:** How long should critical events block before fallback? 2s proposed, but may need tuning.

3. **DB schema migration:** Need to coordinate with existing migrations for `has_event_loss` column.

4. **UI design:** How prominently should we show event loss warnings?

---

## Appendix: Related Code Paths

### Files to Modify

- [`persistent_sse_event_buffer.py`](src/solace_agent_mesh/gateway/http_sse/persistent_sse_event_buffer.py) - Core changes
- [`sse_manager.py`](src/solace_agent_mesh/gateway/http_sse/sse_manager.py) - Mark critical events
- [`task_repository.py`](src/solace_agent_mesh/gateway/http_sse/repository/task_repository.py) - Add `has_event_loss`
- [`sessions.py`](src/solace_agent_mesh/gateway/http_sse/routers/sessions.py) - Circuit breaker integration
- DB migration for `has_event_loss` column

### Existing Test Files

- [`test_persistent_sse_event_buffer.py`](tests/unit/gateway/http_sse/test_persistent_sse_event_buffer.py)
- [`test_slow_db_simulation.py`](tests/stress/scenarios/test_slow_db_simulation.py)
