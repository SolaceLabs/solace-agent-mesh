# Agent-Powered Command Palette

This document describes the agent-powered command palette feature that allows users to execute natural language commands directly from the command palette.

## Overview

The command palette now detects action-like queries (e.g., "create a project called ABC") and routes them to a specialized UI Assistant agent that can execute operations on the product using exposed API tools.

## Architecture

### Backend Components

#### 1. UI Action Tools (`src/solace_agent_mesh/agent/tools/ui_action_tools.py`)
- **Purpose**: Provides tools that the UI Assistant agent can use to interact with the web UI
- **Current Tools**:
  - `create_project`: Creates a new project with the specified name and optional description
- **Implementation**: Tools call the existing HTTP API endpoints internally using httpx

#### 2. UI Assistant Agent (`configs/agents/ui_assistant.yaml`)
- **Purpose**: Specialized agent that interprets natural language commands and executes appropriate tools
- **Characteristics**:
  - Stateless sessions (command palette interactions don't need conversation history)
  - Fast responses optimized for command execution
  - Clear, concise confirmations
- **Tools Available**: `create_project` (registered as builtin tool)

### Frontend Components

#### 1. Agent API Service (`client/webui/frontend/src/lib/api/agent-assistant.ts`)
- **Purpose**: Frontend service for calling the UI Assistant agent
- **Function**: `executeAgentCommand(query: string)` - Sends natural language query to agent and parses response

#### 2. AgentAction Class (`client/webui/frontend/src/lib/components/common/actions/AgentAction.ts`)
- **Purpose**: Action type that executes commands via the UI Assistant agent
- **Features**:
  - Calls the agent with the command
  - Handles agent response
  - Performs UI actions based on response (e.g., navigation)

#### 3. Command Palette Integration
- **Detection**: Regex patterns detect command-like queries:
  - `create/make/new/start ... project`
  - `add/create ... project/folder`
- **UI**: Agent actions display with purple/AI theme and Sparkles icon
- **Priority**: Agent actions appear before "Ask in chat" fallback

## User Flow

1. User opens command palette (Cmd/Ctrl+K)
2. User types a command: "create a project called Marketing Dashboard"
3. Command palette detects this as an agent command
4. Agent action appears with purple theme and Sparkles icon
5. User presses Enter
6. Frontend calls UI Assistant agent via API
7. Agent interprets command and calls `create_project` tool
8. Tool creates project via HTTP API
9. Agent returns success with project ID
10. Frontend navigates user to newly created project

## Example Commands

### Create Project
- "create a project called ABC"
- "make a new project named Dashboard"
- "start a project for Q4 Planning"

## Extending the System

### Adding New Tools

1. **Add tool function to `ui_action_tools.py`**:
```python
async def new_tool_function(
    param1: str,
    tool_context: ToolContext = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    # Implementation
    pass

new_tool_def = BuiltinTool(
    name="new_tool",
    implementation=new_tool_function,
    description="Description for the agent",
    category="ui_actions",
    parameters=...,
)

tool_registry.register(new_tool_def)
```

2. **Add tool to UI Assistant agent config** (`configs/agents/ui_assistant.yaml`):
```yaml
tools:
  - tool_name: create_project
    tool_type: builtin
  - tool_name: new_tool  # Add your new tool
    tool_type: builtin
```

3. **Update command detection patterns** in `CommandPalette.tsx`:
```typescript
const isAgentCommand = (query: string): boolean => {
    const commandPatterns = [
        /^(create|make|new)\s+project/i,
        /^your-new-pattern/i,  // Add your pattern
    ];
    return commandPatterns.some(pattern => pattern.test(query));
};
```

4. **Handle new UI actions** in `AgentAction.ts`:
```typescript
// Handle the response action
if (response.data?.action === "your_new_action") {
    // Perform UI action
}
```

## Technical Details

### Authentication
- Tools use the user ID from the agent's invocation context
- HTTP API calls include user ID as Bearer token for internal authentication

### Error Handling
- Tool failures return ToolResult.error()
- Frontend catches errors and can display toasts
- Agent provides user-friendly error messages

### Performance
- Stateless sessions avoid database overhead
- Direct HTTP calls to existing APIs
- No intermediate layers or complex routing

## Future Enhancements

- Add more UI action tools (delete project, update settings, etc.)
- Improve natural language understanding with more patterns
- Add success/error toasts in UI
- Support multi-step commands ("create project X and add file Y")
- Voice command support via STT integration
