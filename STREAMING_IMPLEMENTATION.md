# Claude Code Streaming Implementation

## Overview

Streaming support has been added to provide real-time progress updates during Claude Code execution. When enabled, the tool sends status updates for file operations and tool usage as they happen.

## Streaming Format

Claude Code CLI uses **newline-delimited JSON (NDJSON)** with `--output-format stream-json`. Each line is a JSON event:

```json
{"type":"system","message":...}
{"type":"stream_event","data":{...}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Write","id":"toolu_123","input":{...}}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
{"type":"result","session_id":"...","result":"..."}
```

**Important**: The CLI format differs from the Anthropic API streaming format. The CLI wraps tool uses in complete "assistant" events rather than streaming partial JSON.

## Implementation

### Files Added/Modified:

1. **`streaming_utils.py`** (NEW)
   - `process_claude_stream()` - Main streaming processor, parses CLI format
   - `should_report_tool()` - Filters which tools to report (Write, Edit, Bash, Read, Glob, Grep)
   - `format_tool_completion()` - Formats user-friendly messages

2. **`execute_tool.py`** (MODIFIED)
   - Reads `enable_streaming` from tool_config (defaults to True)
   - Creates status_callback for streaming mode
   - **TODO**: Integrate with SAM's status_update mechanism (currently logs)

3. **`utils.py`** (MODIFIED)
   - Added `stream` and `status_callback` parameters
   - Uses `--output-format stream-json` with `--verbose` flag when streaming
   - Calls `process_claude_stream()` in streaming mode

## Status Updates Sent

### Tool Start
```python
{
    "tool": "Write",
    "tool_id": "toolu_abc123",
    "message": "Using Write..."
}
```

### Tool Complete
```python
{
    "tool": "Write",
    "tool_id": "toolu_abc123",
    "input": {"file_path": "/workspace/app.js", "content": "..."},
    "message": "Created/updated /workspace/app.js"
}
```

## Reportable Tools

The following tools trigger status updates:
- **Write** - File creation/updates
- **Edit** - File modifications
- **Bash** - Command execution
- **Read** - File reads (configurable)
- **Glob** - File pattern matching
- **Grep** - Code searches

## Usage

### Basic Usage (Streaming Enabled by Default)

```python
result = await claude_code_execute(
    prompt="Build a todo app",
    workspace_id="my-project",
    workspace_type="session",
    environment="node"
)
# Streaming is ENABLED BY DEFAULT
# Status updates sent via callback during execution
# Final result returned at end
```

### Disabling Streaming (Optional)

Streaming is controlled via tool configuration, not per-request parameters:

```python
tool_config = {
    "api_key": "...",
    "enable_streaming": False  # Disable streaming if needed
}
```

## SAM Integration ✅

Status updates are now integrated with SAM's status_update mechanism using `AgentProgressUpdateData`:

### Implementation (execute_tool.py:186-229):
```python
def status_callback_impl(event_type: str, event_data: dict):
    """Publish status updates using SAM mechanism if available, otherwise log."""
    # Format message with "Coding tool: " prefix
    message = event_data.get('message', '')
    prefixed_message = f"Coding tool: {message}"

    # Try to publish via SAM status update mechanism
    if a2a_context and host_component:
        progress_data = AgentProgressUpdateData(status_text=prefixed_message)
        status_update_event = a2a.create_data_signal_event(...)
        # Publish asynchronously via host_component
    else:
        # Fall back to logging if SAM context not available (e.g., in tests)
        log.info(f"[Claude Code] {prefixed_message}")
```

**Status Update Format:**
All status updates are prefixed with "Coding tool: " to distinguish them from other agent status updates.

**Fallback Behavior:**
When running in test mode or without SAM context (e.g., mock tool_context), status updates fall back to logging.

## Example Status Update Flow

Actual output from `test_streaming.py`:

```
[Claude Code] Coding tool: Using Read...
[Claude Code] Coding tool: Read /workspace/package.json
[Claude Code] Coding tool: Using Read...
[Claude Code] Coding tool: Read /workspace/app.js
[Claude Code] Coding tool: Using Bash...
[Claude Code] Coding tool: Ran: node app.js
```

Status updates are sent in real-time as Claude Code executes tools, providing immediate feedback during long-running operations. In a real SAM agent context (not test mode), these are sent as `AgentProgressUpdateData` status updates to the user.

## Benefits

1. **User Visibility** - Users see progress in real-time
2. **Selective Updates** - Only meaningful operations reported (not every LLM turn)
3. **Non-Blocking** - Streaming doesn't affect final result structure
4. **Enabled by Default** - Streaming is ON by default, providing immediate feedback
5. **Opt-Out** - Can be disabled via tool_config if needed

## Performance Considerations

- Streaming adds minimal overhead (NDJSON parsing)
- Status callbacks are non-blocking
- Final result is identical to non-streaming mode
- Network traffic slightly higher due to status updates

## Testing

See `test_streaming.py` for examples.

## Next Steps

1. ✅ Implement streaming parser
2. ✅ Add stream parameter to execute tool
3. ✅ Filter and format relevant events
4. ✅ Test streaming implementation (verified working)
5. ⚠️ **Integrate with SAM's status_update mechanism** (TODO - currently using log.info)
6. ⚠️ Test with real SAM agent system
