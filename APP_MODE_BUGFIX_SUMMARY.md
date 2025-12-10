# App Mode Bug Fix Summary

## Problem

When testing the app builder, the app was created in the wrong location:
- **Expected:** `/Users/edfunnekotter/.claude-workspaces/sam_dev_user/apps/a-todo-app-3be0`
- **Actual:** `/Users/edfunnekotter/.claude-workspaces/default_user/apps/todo-app`

This indicated two issues:
1. User ID was defaulting to `default_user` instead of `sam_dev_user`
2. Workspace ID was LLM-chosen `todo-app` instead of app_id `a-todo-app-3be0`

## Root Causes

### Issue 1: Missing app_mode Configuration

The `examples/agents/app-agent.yaml` was missing the `app_mode` configuration section in `tool_config`. Without this:
- The LLM could see and provide `workspace_id` parameter
- Tools didn't extract `app_id` from A2A context
- All 7 tools were visible (including irrelevant ones like list_workspaces)

### Issue 2: User ID Extraction Only Checked tool_context.user_id

The `get_user_id_from_context()` function in all Claude Code tools only checked `tool_context.user_id`, but didn't fall back to checking `a2a_context.user_id` (which is where SAM puts the user ID).

## Fixes Applied

### Fix 1: Added app_mode Configuration to app-agent.yaml

Added the following to `examples/agents/app-agent.yaml`:

```yaml
# App Mode Configuration
# This enables automatic workspace binding based on app_id from A2A context
app_mode:
  enabled: true
  extract_app_id_from_context: true
  fixed_workspace_type: "app"
  hide_workspace_params: true
  hidden_tools:
    - "claude_code_list_workspaces"
    - "claude_code_list_sessions"
    - "claude_code_import_workspace"
```

**Effect:**
- LLM no longer sees `workspace_id` or `workspace_type` parameters
- Tools automatically extract `app_id` from `a2a_context` and use it as `workspace_id`
- Only 4 relevant tools exposed: execute, read_files, create_version, export_workspace

### Fix 2: Updated get_user_id_from_context() to Check a2a_context

Updated all 7 Claude Code tool files to extract user_id from a2a_context as fallback:

**Files Modified:**
- `execute_tool.py`
- `read_files_tool.py`
- `create_version_tool.py`
- `export_workspace_tool.py`
- `import_workspace_tool.py`
- `list_workspaces_tool.py`
- `list_sessions_tool.py`

**New Implementation:**
```python
def get_user_id_from_context(tool_context: Optional[ToolContext]) -> str:
    """Extract user ID from tool context."""
    if tool_context:
        # First try tool_context.user_id (ADK standard)
        if hasattr(tool_context, "user_id") and tool_context.user_id:
            return tool_context.user_id

        # Fall back to a2a_context.user_id (SAM pattern)
        if hasattr(tool_context, "state"):
            a2a_context = tool_context.state.get("a2a_context", {})
            user_id = a2a_context.get("user_id")
            if user_id:
                return user_id

    return "default_user"
```

**Effect:**
- Tools now correctly extract `user_id` from SAM's A2A context
- Workspaces created in correct user directory

### Fix 3: Updated app-agent.yaml Instruction

Removed references to workspace parameters from the agent instruction since they're now automatic:

**Before:**
```yaml
- claude_code_execute: Write code, run builds, read files
  IMPORTANT: Always use these parameters:
  - workspace_id: Use the app's workspace_id (provided in initial message)
  - workspace_type: "app" (for persistent workspaces)
  - environment: "node" (for React apps)
```

**After:**
```yaml
- claude_code_execute: Write code, run builds, read files
  Note: Your workspace is automatically configured for this app
```

## How It Works Now

### Data Flow

```
User sends message in app editor
  ↓
Frontend: Include app_id in message metadata
  ↓
Backend: Pass app_id and user_id in A2A context
  ↓
Tool receives tool_context with state.a2a_context:
  - user_id: "sam_dev_user"
  - app_id: "a-todo-app-3be0"
  ↓
get_user_id_from_context() extracts "sam_dev_user"
resolve_workspace_params() extracts "a-todo-app-3be0" as workspace_id
  ↓
Workspace created at: /Users/.../.claude-workspaces/sam_dev_user/apps/a-todo-app-3be0
```

### LLM Perspective

The LLM no longer sees or provides workspace parameters:

**Tool Call (as LLM sees it):**
```json
{
  "tool": "claude_code_execute",
  "args": {
    "prompt": "Create a todo list component with Add/Delete functionality"
  }
}
```

**Behind the Scenes (what actually happens):**
- Tool extracts `user_id="sam_dev_user"` from `a2a_context`
- Tool extracts `app_id="a-todo-app-3be0"` from `a2a_context`
- Tool uses `workspace_id="a-todo-app-3be0"`, `workspace_type="app"`, `environment="node"`
- Workspace created/used at correct location

## Next Steps

### 1. Restart App Agent (Required)

The app-agent.yaml changes require restarting the App Agent for the new configuration to take effect:

```bash
# Kill existing app agent process
# Restart with new config
sam run examples/agents/app-agent.yaml
```

### 2. Frontend Integration (If Not Done)

Ensure the frontend sends `app_id` in message metadata when in app editor mode:

```typescript
// In ChatProvider or app editor message sending logic
const metadata = {
  ...existingMetadata,
  app_id: appEditorMode.appId  // When in app editor context
};
```

### 3. Test Again

Create a new app and verify:
- User ID is correct (`sam_dev_user` not `default_user`)
- Workspace ID matches app_id (e.g., `a-todo-app-3be0`)
- Workspace created at: `~/.claude-workspaces/{user_id}/apps/{app_id}/`
- Dev server serves from correct location

## Verification

After restarting the App Agent, you can verify the configuration is working by:

1. Creating a new app in the UI
2. Checking the logs for `[App Mode]` messages:
   ```
   [App Mode] Extracted app_id from a2a_context: a-todo-app-3be0
   [App Mode] Using workspace_id from context: a-todo-app-3be0
   ```
3. Verifying workspace is created in correct location
4. Checking that LLM tool calls don't include workspace_id parameter

## Files Changed

### Modified
- `src/solace_agent_mesh/agent/tools/claude_code/execute_tool.py` - Updated get_user_id_from_context()
- `src/solace_agent_mesh/agent/tools/claude_code/read_files_tool.py` - Updated get_user_id_from_context()
- `src/solace_agent_mesh/agent/tools/claude_code/create_version_tool.py` - Updated get_user_id_from_context()
- `src/solace_agent_mesh/agent/tools/claude_code/export_workspace_tool.py` - Updated get_user_id_from_context()
- `src/solace_agent_mesh/agent/tools/claude_code/import_workspace_tool.py` - Updated get_user_id_from_context()
- `src/solace_agent_mesh/agent/tools/claude_code/list_workspaces_tool.py` - Updated get_user_id_from_context()
- `src/solace_agent_mesh/agent/tools/claude_code/list_sessions_tool.py` - Updated get_user_id_from_context()
- `examples/agents/app-agent.yaml` - Added app_mode config, updated instruction

### Created (Previously)
- `src/solace_agent_mesh/agent/tools/claude_code/context_helpers.py` - Helper functions for app_mode
- `test_app_mode_tools.py` - Test suite for app_mode functionality
- `APP_MODE_IMPLEMENTATION_SUMMARY.md` - Implementation documentation

---

**Status:** ✅ Bug Fixes Complete - Restart App Agent to Apply
