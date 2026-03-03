# Local Testing Guide: Background Task Cancellation Fix

## Overview
This guide walks you through testing the background task cancellation fix on your local machine with the 20-second timeout configuration.

## Prerequisites
✅ Database migration applied (agent_name column exists)
✅ Configuration updated with test timeouts:
   - `default_timeout_ms: 20000` (20 seconds)
   - `monitor_interval_ms: 5000` (5 seconds)

## Test Setup

### Step 1: Start the Application

In Terminal 1, start the SAM gateway:
```bash
cd /Users/amir.ghasemi/code/samdev/sam
sam run configs/gateways/webui.yaml
```

Wait for the application to start and look for:
```
INFO     Starting BackgroundTaskMonitor with interval 5.0 seconds
INFO     Background task timeout: 20.0 seconds
```

### Step 2: Start Log Monitoring

In Terminal 2, monitor the logs for cancellation events:
```bash
cd /Users/amir.ghasemi/code/samdev/sam
tail -f webui_example.log | grep -E "(BackgroundTaskMonitor|timeout|cancel|agent_name)"
```

### Step 3: Start Database Monitoring

In Terminal 3, watch task status changes in real-time:
```bash
cd /Users/amir.ghasemi/code/samdev/sam
watch -n 2 "sqlite3 webui-gateway.db 'SELECT status, COUNT(*) as count FROM tasks GROUP BY status ORDER BY count DESC;'"
```

## Test Execution

### Test 1: Quick Timeout Test (20 seconds)

**Objective**: Verify that tasks timeout after 20 seconds and agents receive cancellation messages.

**Steps**:

1. **Open the Web UI** at http://localhost:3000

2. **Create a long-running background task**:
   - In the chat interface, enable "Run in background" toggle
   - Send a message that will take longer than 20 seconds, for example:
     ```
     Please analyze this large dataset and provide insights. Take your time to be thorough.
     [Attach a large file or ask for a complex analysis]
     ```

3. **Start the timer**: Note the current time

4. **Monitor Terminal 2** (logs) - After ~20 seconds, you should see:
   ```
   INFO BackgroundTaskMonitor: Found 1 timed out background tasks
   INFO BackgroundTaskMonitor: Sent cancellation to agent '<agent_name>' for task <task_id>
   INFO BackgroundTaskMonitor: Task <task_id> marked as timeout
   ```

5. **Monitor Terminal 3** (database) - You should see:
   - Task count for "running" decrease
   - Task count for "timeout" increase

6. **Verify in database**:
   ```bash
   sqlite3 webui-gateway.db "SELECT id, status, agent_name, created_at, updated_at FROM tasks WHERE status='timeout' ORDER BY updated_at DESC LIMIT 5;"
   ```

**Expected Results**:
- ✅ Task times out after ~20 seconds (not 1 hour)
- ✅ BackgroundTaskMonitor detects the timeout
- ✅ Cancellation message sent to agent (logged with agent_name)
- ✅ Task status updated to "timeout" in database
- ✅ agent_name field populated in database

### Test 2: Verify Agent Receives Cancellation

**Objective**: Confirm the agent actually receives and processes the cancellation message.

**Steps**:

1. **Check agent logs** (if running locally):
   ```bash
   tail -f <agent-log-file> | grep -i cancel
   ```

2. **Look for cancellation handling**:
   - Agent should log receiving the cancellation
   - Agent should stop processing the task
   - No more events should be generated for that task

**Expected Results**:
- ✅ Agent logs show cancellation received
- ✅ Agent stops generating events
- ✅ No queue overflow warnings

### Test 3: Multiple Concurrent Timeouts

**Objective**: Verify the system handles multiple timeouts simultaneously.

**Steps**:

1. **Create 3-5 background tasks** quickly (within a few seconds)
2. **Wait 20 seconds**
3. **Monitor logs** - Should see batch cancellation:
   ```
   INFO BackgroundTaskMonitor: Found 5 timed out background tasks
   INFO BackgroundTaskMonitor: Sent cancellation to agent 'agent1' for task <id1>
   INFO BackgroundTaskMonitor: Sent cancellation to agent 'agent2' for task <id2>
   ...
   ```

**Expected Results**:
- ✅ All tasks timeout around the same time
- ✅ All cancellations sent successfully
- ✅ Database shows all tasks as "timeout"
- ✅ No errors or exceptions

### Test 4: Task Without agent_name (Backward Compatibility)

**Objective**: Verify the system handles tasks without agent_name gracefully.

**Steps**:

1. **Manually insert a task without agent_name**:
   ```bash
   sqlite3 webui-gateway.db "INSERT INTO tasks (id, user_id, status, created_at, updated_at, is_background_task) VALUES ('test-task-no-agent', 'test-user', 'running', $(date +%s)000, $(date +%s)000, 1);"
   ```

2. **Wait 20 seconds**

3. **Check logs** - Should see warning:
   ```
   WARNING BackgroundTaskMonitor: Task test-task-no-agent has no agent_name, cannot cancel
   ```

**Expected Results**:
- ✅ Task marked as "timeout" in database
- ✅ Warning logged about missing agent_name
- ✅ No crash or exception
- ✅ Other tasks with agent_name still cancelled properly

## Verification Queries

### Check Recent Timeout Tasks
```bash
sqlite3 webui-gateway.db "SELECT id, status, agent_name, datetime(created_at/1000, 'unixepoch') as created, datetime(updated_at/1000, 'unixepoch') as updated FROM tasks WHERE status='timeout' ORDER BY updated_at DESC LIMIT 10;"
```

### Check Task Duration Before Timeout
```bash
sqlite3 webui-gateway.db "SELECT id, agent_name, status, (updated_at - created_at)/1000.0 as duration_seconds FROM tasks WHERE status='timeout' ORDER BY updated_at DESC LIMIT 10;"
```

### Check Tasks by Status
```bash
sqlite3 webui-gateway.db "SELECT status, COUNT(*) as count, GROUP_CONCAT(agent_name) as agents FROM tasks GROUP BY status;"
```

### Check Background Task Monitor Stats
Look in logs for periodic stats:
```bash
grep "BackgroundTaskMonitor stats" webui_example.log | tail -5
```

## Success Criteria

✅ **All tests pass**:
- Tasks timeout after 20 seconds (not 1 hour)
- Cancellation messages sent to agents
- Database updated correctly
- agent_name captured and used
- No errors or crashes
- Backward compatibility maintained

✅ **Performance**:
- Monitor checks every 5 seconds
- No significant CPU/memory impact
- Database queries complete quickly

✅ **Observability**:
- Clear log messages at each step
- Easy to debug issues
- Stats available for monitoring

## Troubleshooting

### Issue: Tasks not timing out
- Check config: `grep -A 5 "background_tasks:" configs/gateways/webui.yaml`
- Verify monitor is running: `grep "BackgroundTaskMonitor" webui_example.log`
- Check task is marked as background: `sqlite3 webui-gateway.db "SELECT id, is_background_task FROM tasks;"`

### Issue: No cancellation messages sent
- Verify agent_name is populated: `sqlite3 webui-gateway.db "SELECT id, agent_name FROM tasks WHERE status='timeout';"`
- Check for errors in logs: `grep -i error webui_example.log | grep -i cancel`
- Verify task_service is initialized: `grep "TaskService" webui_example.log`

### Issue: Agent not receiving cancellation
- Check agent is subscribed to cancellation topic
- Verify broker connectivity
- Check agent logs for incoming messages

## Next Steps

After successful local testing:

1. **Revert test configuration** (or keep for staging):
   ```yaml
   background_tasks:
     default_timeout_ms: 3600000  # Back to 1 hour
     monitor_interval_ms: 300000  # Back to 5 minutes
   ```

2. **Deploy to staging** with test config for validation

3. **Monitor production** metrics after deployment:
   - Task timeout rate
   - Queue depths
   - Active task counts
   - Agent cancellation handling

4. **Gradually increase timeout** if needed based on real-world usage patterns
