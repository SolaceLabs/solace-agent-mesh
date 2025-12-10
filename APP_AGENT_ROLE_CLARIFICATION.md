# AppAgent Role Clarification - Summary of Changes

## Problem Identified

The original instructions in `app-agent.yaml` treated AppAgent as if it was doing the coding work itself, when its actual role is to **orchestrate** Claude Code (which does the actual development).

## Key Conceptual Fix

### Before (Incorrect)
- AppAgent instructions implied it would write code, fix errors, run builds
- APP_CONTEXT.md described as communication mechanism TO AppAgent
- Confusion about who maintains what files

### After (Correct)
- **AppAgent** = Project manager / orchestrator
  - Gathers requirements from user
  - Translates to clear instructions for Claude Code
  - Sources assets from other agents
  - Interprets results and communicates progress

- **Claude Code** = Actual developer
  - Reads/writes code
  - Runs builds and tests
  - Fixes errors
  - Maintains APP_CONTEXT.md for its own use

## Changes Made

### 1. app-agent.yaml Instructions (examples/agents/app-agent.yaml)

**Added:**
- Clear role definition: "YOU ARE NOT A CODER - You are an orchestrator"
- Access control: Must refuse calls from other agents (user-only)
- Workflow for handling Claude Code questions/asset requests
- Asset sourcing responsibilities and limitations to communicate
- Emphasis on NOT debugging/fixing code yourself

**Changed:**
- From "You write code" → "You call Claude Code to write code"
- From "You fix errors" → "You pass errors to Claude Code"
- From "APP_CONTEXT.md is yours" → "APP_CONTEXT.md is Claude Code's memory"

### 2. CLAUDE.md for Claude Code (docker/claude-code-sam-app/template/CLAUDE.md)

**Added:**
- "Your Role" section explaining Claude Code is the developer
- APP_CONTEXT.md ownership: "for YOUR benefit" (Claude Code's)
- "Asking Questions and Requesting Assets" section with:
  - How to ask clarification questions
  - How to request assets (images, icons, etc.)
  - Asset limitations (single size, no transparency, rudimentary)
  - Example response format with questions and asset requests
  - How to work with provided assets (CSS workarounds)

**Key Message to Claude Code:**
- You CAN and SHOULD ask questions
- You CAN request assets through the App Agent
- Assets will be basic - plan accordingly

## Communication Flow

```
User
  ↕ (conversation)
AppAgent (Orchestrator)
  ↕ (instructions + assets)
Claude Code (Developer)
  ↕ (questions + code)
Workspace
```

### Asset Flow

```
User: "I need a dashboard with charts"
  ↓
AppAgent: Gathers requirements
  ↓
AppAgent → Claude Code: "Build dashboard..."
  ↓
Claude Code: "I need: 1) Logo image 2) Chart background"
  ↓
AppAgent: Calls ImageGenerator agent
  ↓
AppAgent → Claude Code: "Assets saved to /public/logo.png (NO transparency)"
  ↓
Claude Code: Builds dashboard with CSS workarounds for limitations
```

## Benefits

1. **Clear Separation of Concerns**
   - AppAgent doesn't try to code (it can't see files)
   - Claude Code doesn't try to gather requirements (it can't talk to user directly)

2. **Better Asset Support**
   - Claude Code can request what it needs
   - AppAgent sources from other agents
   - Limitations clearly communicated

3. **Iterative Development**
   - Claude Code can ask questions rather than guess
   - More efficient back-and-forth

4. **Access Control**
   - AppAgent refuses agent-to-agent calls (user-only interface)
   - Prevents misuse

## Testing Recommendations

1. **Test Claude Code Questions**: Give vague requirements, verify Claude Code asks for clarification
2. **Test Asset Requests**: Request feature needing images, verify Claude Code asks for them
3. **Test Asset Limitations**: Verify Claude Code handles no-transparency images properly
4. **Test A2A Refusal**: Try calling AppAgent from another agent, verify refusal
5. **Test Error Handling**: Introduce build error, verify AppAgent passes to Claude Code (doesn't try to fix itself)

## Files Modified

1. `/examples/agents/app-agent.yaml` - AppAgent instructions completely rewritten
2. `/docker/claude-code-sam-app/template/CLAUDE.md` - Added "Your Role", "APP_CONTEXT.md", and "Asking Questions and Requesting Assets" sections

## Related Documentation

- Architecture: `docs/app-builder-architecture.md` (already correctly documented the roles)
- Claude Code Tool Design: `docs/claude-code-tool-design.md` (tool implementation details)
