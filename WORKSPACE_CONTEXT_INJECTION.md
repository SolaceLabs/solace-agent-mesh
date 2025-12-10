# Workspace Context Injection System

## Overview

Implemented a sophisticated system for automatically injecting workspace files (like APP_CONTEXT.md) into the App Agent's system instruction before every LLM call. This ensures the agent always has the latest application state without requiring manual file reads or relying on LLM memory.

## Architecture

### Components

1. **WorkspaceContextInjector** (`src/solace_agent_mesh/agent/adk/callbacks/workspace_context_injector.py`)
   - Core class that reads workspace files and injects content
   - Configurable per-agent via YAML configuration
   - Supports multiple files, file size limits, and optional files
   - Works for any agent with workspace-based context (not app-specific)

2. **Callback Function** (`src/solace_agent_mesh/agent/adk/callbacks.py`)
   - `inject_workspace_context_callback`: Wrapper function registered in callback chain
   - Called before each LLM request
   - Instantiates WorkspaceContextInjector with agent-specific config

3. **Setup Integration** (`src/solace_agent_mesh/agent/adk/setup.py`)
   - Registers callback in `before_model` callback chain
   - Reads `workspace_context_injection` from agent's app_config
   - Only active if configuration is present

4. **App Agent Configuration** (`examples/agents/app-agent.yaml`)
   - Defines workspace_context_injection settings
   - Configures APP_CONTEXT.md injection
   - Updated instruction to explain APP_CONTEXT.md management

## How It Works

### Injection Flow

```
1. User sends message → Backend receives it with app_id in metadata
2. app_id added to a2a_context (event_handlers.py:588, 761)
3. ADK runner prepares LLM request
4. Before-model callbacks execute
5. inject_workspace_context_callback runs:
   a. Reads a2a_context from callback_context.state
   b. Extracts user_id and app_id
   c. Determines workspace path: ~/.claude-workspaces/{user_id}/apps/{app_id}
   d. Reads APP_CONTEXT.md (if exists)
   e. Injects content into llm_request.config.system_instruction
6. LLM receives system instruction with latest APP_CONTEXT.md
7. Agent responds with current application context
```

### File Structure

```
~/.claude-workspaces/
└── {user_id}/
    └── apps/
        └── {app_id}/
            ├── APP_CONTEXT.md          ← Auto-injected into system prompt
            ├── src/
            ├── package.json
            └── ...
```

### Configuration

In agent YAML file:

```yaml
app_config:
  workspace_context_injection:
    workspace_base: "${HOME}/.claude-workspaces"
    files:
      - path: "APP_CONTEXT.md"
        header: "## Current Application State (Auto-Updated from Workspace)"
        required: false
        max_size: 50000  # 50KB limit
```

## APP_CONTEXT.md Management

### Agent Responsibilities

The App Agent is instructed to:

1. **Create APP_CONTEXT.md** on first code change (if doesn't exist)
2. **Update APP_CONTEXT.md** after EVERY change to the application
3. **Include**:
   - What's Built: Implemented features with file references
   - Current State: What works, what's in progress, what's planned
   - Recent Changes: Latest modifications
   - Architecture: Component structure, data flow, SAM integrations
   - Known Issues: Bugs, technical debt, performance concerns

### Example APP_CONTEXT.md

```markdown
# App: Todo List Manager

## What's Built
- Task list component (`src/components/TaskList.tsx`)
- Task creation form (`src/components/TaskForm.tsx`)
- SAM storage integration for persistence
- Responsive layout with Tailwind CSS

## Current State
- ✅ What works: Create, read, delete tasks with SAM.storage
- 🚧 What's in progress: Edit task functionality
- 📋 What's planned: Task categories, due dates

## Recent Changes
- Added delete confirmation dialog (Session: 2024-12-08 10:30 AM)
- Fixed task duplication bug

## Architecture
- Component structure: App > TaskList > TaskItem
- State: React useState for local state, SAM.storage for persistence
- SAM Integration: SAM.storage for task CRUD operations

## Known Issues
- Task edit UI needs better UX
- No loading state when fetching from storage
```

## Benefits

### 1. **Cross-Session Continuity**
- Agent remembers application state across different sessions
- Multiple concurrent sessions all see the same current state
- No "forgetting" what was built previously

### 2. **Context Efficiency**
- Single file injection (APP_CONTEXT.md) vs multiple tool calls to read files
- File content injected once per LLM call (not duplicated in history)
- 50KB size limit prevents context explosion

### 3. **Always Current**
- File re-read before EVERY LLM call
- No stale context from cached file reads
- Works even if user manually edits APP_CONTEXT.md

### 4. **Generic & Reusable**
- Not specific to App Agent - any agent can use it
- Could inject ARCHITECTURE.md, TODO.md, DESIGN_DECISIONS.md, etc.
- Configurable per-agent via YAML

## Testing

### Manual Test 1: File Injection

1. Restart App Agent with new configuration
2. Create an app via UI
3. Send message: "What's the current state of this app?"
4. Check logs for:
   ```
   [WorkspaceContextInjector] Workspace does not exist yet: ...
   ```
5. Use claude_code_execute to create APP_CONTEXT.md
6. Send another message
7. Check logs for:
   ```
   [WorkspaceContextInjector] Injected APP_CONTEXT.md (XXX chars) from {app_id}
   ```

### Manual Test 2: Content Awareness

1. Create APP_CONTEXT.md with specific content:
   ```markdown
   # App: Test App

   ## What's Built
   - Feature X implemented in src/components/X.tsx
   ```
2. Ask agent: "What have I built so far?"
3. Agent should reference Feature X from APP_CONTEXT.md without reading the file explicitly

### Manual Test 3: Update Cycle

1. Ask agent to add a new feature
2. Verify APP_CONTEXT.md is updated by agent after change
3. Ask about current state in a NEW session
4. Agent should be aware of the new feature (from APP_CONTEXT.md)

## Troubleshooting

### Callback Not Running

Check logs for:
```
Added inject_workspace_context_callback to before_model chain
```

If missing, verify `workspace_context_injection` is in app_config.

### File Not Injected

Check logs for:
- `Workspace does not exist yet` → Workspace not created
- `Optional file not found` → APP_CONTEXT.md doesn't exist (expected initially)

### File Too Large

If APP_CONTEXT.md exceeds 50KB:
```
File APP_CONTEXT.md is 75000 chars, truncating to 50000
```

Increase `max_size` in config or ask agent to summarize APP_CONTEXT.md.

## Future Enhancements

1. **Multi-File Injection**: Inject ARCHITECTURE.md, CHANGELOG.md, etc.
2. **Conditional Injection**: Only inject for certain agent names
3. **Template Files**: Provide APP_CONTEXT.md template on workspace creation
4. **Metrics**: Track injection frequency, file sizes
5. **Caching**: Cache file content per-session to reduce I/O (with invalidation)

## Code References

- **Callback Class**: `src/solace_agent_mesh/agent/adk/callbacks/workspace_context_injector.py:1-214`
- **Callback Registration**: `src/solace_agent_mesh/agent/adk/setup.py:1097-1108`
- **Callback Function**: `src/solace_agent_mesh/agent/adk/callbacks.py:2321-2359`
- **App ID Extraction**: `src/solace_agent_mesh/agent/protocol/event_handlers.py:588, 761`
- **App Agent Config**: `examples/agents/app-agent.yaml:155-162`
- **App Agent Instruction**: `examples/agents/app-agent.yaml:40-98`

## Summary

This system provides a robust, efficient way to maintain application state awareness across multiple sessions and concurrent conversations. The App Agent automatically maintains APP_CONTEXT.md, and the system automatically injects the latest version before every LLM call, ensuring the agent always has current context without relying on memory or manual file reads.
