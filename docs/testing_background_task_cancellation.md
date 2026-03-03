# Testing Background Task Cancellation - Practical Guide

## Overview

This guide provides step-by-step instructions for testing the background task cancellation fix in a controlled environment.

## Test Strategy

We'll artificially set very short timeouts to trigger cancellation quickly, then verify the agent receives and processes the cancellation.

---

## Test 1: Quick Timeout Test (Recommended First Test)

### Setup

1. **Configure short timeout for testing**

Create a test configuration file or modify your gateway config:

```yaml
# configs/gateways/webui_test.yaml
background_tasks:
  enabled: true
  default_timeout_ms: 30000  # 30 seconds (normally 3600000 = 1 hour)
  monitor_interval_ms: 10000  # 10 seconds (normally 300000 = 5 minutes)
```

2. **Start the gateway with test config**

```bash
# In staging/test environment
sam run --config configs/gateways/webui_test.yaml
```

### Execute Test

**Step 1: Create a background task**

```bash
# Using curl or the WebUI, create a background task
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "TestAgent",
    "message": "Do something that takes a while",
    "background_execution_enabled": true,
    "max_execution_time_ms": 30000
  }'
```

**Step 2: Note the task ID**

Response will include: `{"task_id": "task-abc123"}`

**Step 3: Wait 40 seconds** (past the 30-second timeout)

**Step 4: Check the logs**

```bash
# Gateway logs - should show cancellation sent
grep "Cancelling timed-out task" logs/gateway.log
grep "Sent cancellation request to agent" logs/gateway.log

# Expected output:
# [BackgroundTaskMonitor] Task task-abc123 exceeded timeout: 35000ms since last activity (timeout: 30000ms)
# [BackgroundTaskMonitor] Sent cancellation request to agent 'TestAgent' for task task-abc123
# [BackgroundTaskMonitor] Marked task task-abc123 as timed out
```

**Step 5: Check agent logs**

```bash
# Agent logs - should show cancellation received
grep "task-abc123" logs/agent.log | grep -i cancel

# Expected output:
# [TestAgent] Received cancellation request for task task-abc123
# [TestAgent] Stopping task execution
# [TestAgent] Task task-abc123 cancelled successfully
```

**Step 6: Verify database**

```bash
# Check task status in database
psql -d webui_gateway -c "SELECT id, status, agent_name, end_time FROM tasks WHERE id = 'task-abc123';"

# Expected:
#     id      | status  | agent_name | end_time
# ------------+---------+------------+----------
# task-abc123 | timeout | TestAgent  | 1707840123456
```

**Step 7: Verify no more events**

```bash
# Check that agent stopped generating events
# Count events before and after cancellation
psql -d webui_gateway -c "
  SELECT COUNT(*) as event_count, 
         MAX(created_time) as last_event_time
  FROM task_events 
  WHERE task_id = 'task-abc123';
"

# The last_event_time should be around the cancellation time
# No new events should appear after cancellation
```

### Success Criteria

✅ Gateway logs show cancellation sent
✅ Agent logs show cancellation received
✅ Task status = "timeout" in database
✅ Agent stopped generating events
✅ No queue overflow warnings

---

## Test 2: Multiple Concurrent Timeouts

### Setup

Same as Test 1, but create multiple background tasks.

### Execute

```bash
# Create 5 background tasks
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/v1/tasks \
    -H "Content-Type: application/json" \
    -d "{
      \"agent_name\": \"TestAgent$i\",
      \"message\": \"Task $i\",
      \"background_execution_enabled\": true,
      \"max_execution_time_ms\": 30000
    }"
  sleep 1
done
```

### Verify

```bash
# After 40 seconds, check all were cancelled
psql -d webui_gateway -c "
  SELECT id, status, agent_name 
  FROM tasks 
  WHERE status = 'timeout' 
    AND start_time > NOW() - INTERVAL '2 minutes'
  ORDER BY start_time DESC;
"

# Should show 5 tasks with status='timeout'
```

---

## Test 3: Agent Cancellation Response Test

### Purpose
Verify that agents properly handle cancellation messages.

### Setup Agent Mock

Create a test agent that logs cancellation:

```python
# test_agent.py
import asyncio
from solace_agent_mesh.agent import Agent

class TestAgent(Agent):
    async def handle_task(self, task):
        try:
            # Simulate long-running work
            for i in range(100):
                await asyncio.sleep(1)
                self.log.info(f"Working... {i}/100")
        except asyncio.CancelledError:
            self.log.info(f"Task {task.id} was cancelled!")
            raise
    
    async def handle_cancellation(self, task_id):
        self.log.info(f"Received cancellation for task {task_id}")
        # Cancel the running task
        # ... cancellation logic ...
        return {"status": "cancelled"}
```

### Execute

1. Start the test agent
2. Create a background task with 30-second timeout
3. Wait for timeout
4. Check agent logs for cancellation handling

### Expected Agent Logs

```
[TestAgent] Starting task task-xyz789
[TestAgent] Working... 1/100
[TestAgent] Working... 2/100
...
[TestAgent] Working... 30/100
[TestAgent] Received cancellation for task task-xyz789
[TestAgent] Task task-xyz789 was cancelled!
[TestAgent] Cleanup completed for task task-xyz789
```

---

## Test 4: Production-Like Load Test

### Setup

```yaml
# Use more realistic timeouts but still shorter than production
background_tasks:
  default_timeout_ms: 300000  # 5 minutes (vs 1 hour in prod)
  monitor_interval_ms: 60000   # 1 minute (vs 5 minutes in prod)
```

### Execute

```bash
# Create 20 background tasks
for i in {1..20}; do
  curl -X POST http://localhost:8000/api/v1/tasks \
    -H "Content-Type: application/json" \
    -d "{
      \"agent_name\": \"Agent$((i % 5))\",
      \"message\": \"Load test task $i\",
      \"background_execution_enabled\": true,
      \"max_execution_time_ms\": 300000
    }"
  sleep 2
done
```

### Monitor

```bash
# Watch queue depths in real-time
watch -n 5 'grep "queue.*full\|queue.*%\|Queue depth" logs/gateway.log | tail -20'

# Monitor active task count
watch -n 10 'psql -d webui_gateway -t -c "SELECT COUNT(*) FROM tasks WHERE status NOT IN (\"completed\", \"failed\", \"cancelled\", \"timeout\") OR (status IS NULL AND end_time IS NULL);"'
```

### Success Criteria

✅ Queue depth stays < 80% throughout test
✅ Active task count decreases as timeouts occur
✅ All timed-out tasks receive cancellations
✅ No system unresponsiveness

---

## Test 5: Legacy Task Handling (No agent_name)

### Purpose
Verify graceful handling of tasks created before the fix.

### Setup

Manually insert a task without agent_name:

```sql
INSERT INTO tasks (
  id, user_id, agent_name, start_time, status, 
  last_activity_time, background_execution_enabled, 
  max_execution_time_ms
) VALUES (
  'legacy-task-123',
  'test_user',
  NULL,  -- No agent_name
  EXTRACT(EPOCH FROM NOW() - INTERVAL '2 hours') * 1000,
  'running',
  EXTRACT(EPOCH FROM NOW() - INTERVAL '2 hours') * 1000,
  true,
  3600000
);
```

### Verify

```bash
# Wait for monitor to run
sleep 70

# Check logs
grep "legacy-task-123" logs/gateway.log

# Expected:
# [BackgroundTaskMonitor] Task legacy-task-123 has no agent_name, cannot send cancellation to agent
# [BackgroundTaskMonitor] Marked task legacy-task-123 as timed out
```

### Success Criteria

✅ Task marked as "timeout" in database
✅ Warning logged about missing agent_name
✅ No crash or exception
✅ Monitor continues processing other tasks

---

## Automated Test Script

```bash
#!/bin/bash
# test_background_cancellation.sh

set -e

echo "=== Background Task Cancellation Test ==="
echo ""

# Configuration
GATEWAY_URL="http://localhost:8000"
TIMEOUT_MS=30000
MONITOR_INTERVAL_MS=10000

echo "1. Creating background task with ${TIMEOUT_MS}ms timeout..."
RESPONSE=$(curl -s -X POST ${GATEWAY_URL}/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_name\": \"TestAgent\",
    \"message\": \"Test task for cancellation\",
    \"background_execution_enabled\": true,
    \"max_execution_time_ms\": ${TIMEOUT_MS}
  }")

TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
echo "   Task created: $TASK_ID"
echo ""

echo "2. Waiting for timeout (${TIMEOUT_MS}ms + ${MONITOR_INTERVAL_MS}ms)..."
WAIT_TIME=$((TIMEOUT_MS / 1000 + MONITOR_INTERVAL_MS / 1000 + 5))
sleep $WAIT_TIME
echo ""

echo "3. Checking task status..."
STATUS=$(psql -d webui_gateway -t -c "SELECT status FROM tasks WHERE id = '$TASK_ID';")
echo "   Status: $STATUS"
echo ""

echo "4. Checking for cancellation in logs..."
if grep -q "Sent cancellation request to agent.*$TASK_ID" logs/gateway.log; then
  echo "   ✅ Cancellation sent to agent"
else
  echo "   ❌ Cancellation NOT found in logs"
  exit 1
fi
echo ""

echo "5. Checking agent received cancellation..."
if grep -q "Received cancellation.*$TASK_ID" logs/agent.log; then
  echo "   ✅ Agent received cancellation"
else
  echo "   ⚠️  Agent cancellation not found (check agent logs manually)"
fi
echo ""

if [ "$STATUS" = " timeout" ]; then
  echo "✅ TEST PASSED: Task properly timed out and cancelled"
  exit 0
else
  echo "❌ TEST FAILED: Task status is '$STATUS', expected 'timeout'"
  exit 1
fi
```

---

## Monitoring During Tests

### Key Metrics to Watch

1. **Queue Depths**
```bash
# Real-time queue monitoring
tail -f logs/gateway.log | grep -E "queue.*full|queue.*%|Queue depth"
```

2. **Active Task Count**
```bash
# Every 10 seconds
watch -n 10 'psql -d webui_gateway -t -c "SELECT COUNT(*) as active_tasks FROM tasks WHERE status NOT IN (\"completed\", \"failed\", \"cancelled\", \"timeout\");"'
```

3. **Cancellation Success Rate**
```bash
# After test completes
psql -d webui_gateway -c "
  SELECT 
    COUNT(*) FILTER (WHERE status = 'timeout') as timed_out,
    COUNT(*) FILTER (WHERE status = 'timeout' AND agent_name IS NOT NULL) as with_agent_name,
    COUNT(*) FILTER (WHERE status = 'timeout' AND agent_name IS NULL) as without_agent_name
  FROM tasks
  WHERE start_time > EXTRACT(EPOCH FROM NOW() - INTERVAL '1 hour') * 1000;
"
```

4. **Event Generation After Cancellation**
```bash
# Check if events stopped after cancellation
psql -d webui_gateway -c "
  SELECT 
    t.id,
    t.end_time as cancelled_at,
    MAX(e.created_time) as last_event,
    (MAX(e.created_time) - t.end_time) as events_after_cancel_ms
  FROM tasks t
  JOIN task_events e ON t.id = e.task_id
  WHERE t.status = 'timeout'
    AND t.end_time IS NOT NULL
  GROUP BY t.id, t.end_time
  HAVING MAX(e.created_time) > t.end_time;
"
# Should return 0 rows (no events after cancellation)
```

---

## Troubleshooting

### Issue: Cancellation not sent

**Check:**
1. Is `agent_name` populated in the task?
   ```sql
   SELECT id, agent_name FROM tasks WHERE id = 'task-xxx';
   ```
2. Is the monitor running?
   ```bash
   grep "Background task monitor timer triggered" logs/gateway.log
   ```

### Issue: Agent not receiving cancellation

**Check:**
1. Agent is subscribed to cancellation topic
2. Broker connectivity
3. Agent logs for any errors

### Issue: Task not timing out

**Check:**
1. `last_activity_time` is being updated
2. Timeout calculation is correct
3. Monitor interval has passed

---

## Success Checklist

After running all tests, verify:

- [ ] Tasks with agent_name receive cancellations
- [ ] Tasks without agent_name are handled gracefully
- [ ] Agents stop generating events after cancellation
- [ ] Queue depths remain healthy (< 80%)
- [ ] Active task count decreases appropriately
- [ ] No system crashes or exceptions
- [ ] Cancellation success rate > 95%
- [ ] Database correctly updated (status='timeout')

---

## Next Steps After Successful Testing

1. **Restore normal timeouts** in production config
2. **Deploy to staging** for 48-hour soak test
3. **Monitor metrics** continuously
4. **Deploy to production** during low-traffic window
5. **Set up alerts** for queue depth and active tasks
