# SAM App Builder Architecture

## Table of Contents

1. [Overview](#1-overview)
2. [System Components](#2-system-components)
3. [App Agent](#3-app-agent)
4. [SAM SDK](#4-sam-sdk)
5. [Data Flow & Communication](#5-data-flow--communication)
6. [Workspace Management](#6-workspace-management)
7. [Key File Reference](#7-key-file-reference)
8. [Development Workflow](#8-development-workflow)
9. [Implementation Details](#9-implementation-details)

---

## 1. Overview

### 1.1 What is the App Builder?

The SAM App Builder is a conversational AI-powered system for creating production-ready React applications that run within the SAM platform. Users describe what they want to build, and the AppAgent uses Claude Code to autonomously generate code, manage workspaces, and validate builds.

### 1.2 Key Features

- **Conversational Development**: Build apps through natural language dialogue
- **Live Preview**: See changes instantly in sandboxed iframe preview
- **SAM Integration**: Apps can call SAM agents, use persistent storage, and manage artifacts
- **Autonomous Coding**: Claude Code handles all coding tasks (reading, writing, building, testing)
- **Incremental Build**: Features are built one at a time with user feedback
- **Production Ready**: Full TypeScript, React 19, Vite 6, Tailwind CSS stack

### 1.3 Architecture Goals

1. **Separation of Concerns**: Gateway handles HTTP/DB, agents handle AI logic, tools handle coding
2. **Self-Contained Workspaces**: Apps are isolated with all dependencies pre-installed
3. **Container Self-Initialization**: Containers initialize their own workspaces (no gateway container dependency)
4. **Real-Time Communication**: SDK uses postMessage for iframe↔parent communication
5. **Persistent Context**: APP_CONTEXT.md maintains application state across turns

---

## 2. System Components

### 2.1 Frontend (React WebUI)

#### 2.1.1 App Pages

**Location**: `client/webui/frontend/src/lib/components/pages/`

- **AppsPage**: Lists all user's apps with search and filtering
- **CreateAppPage**: Form for creating new apps (name + description)
- **AppView** (via ChatPage): Combined chat + preview interface for app development

#### 2.1.2 Chat Integration

**Location**: `client/webui/frontend/src/lib/components/pages/ChatPage.tsx`

When `appId` query parameter is present:
- Automatically sets `selectedAgentName` to "AppAgent" (line 135)
- Enables app editor mode with `appEditorMode: { appId }`
- Opens side panel to "app-preview" tab by default
- Associates all messages with `app_id` in metadata

**Location**: `client/webui/frontend/src/lib/providers/ChatProvider.tsx`

- Handles message sending with `agent_name` and `app_id` in metadata (lines 2061, 2069-2071)
- Manages SSE connections for streaming responses
- Tracks task state and message history
- Saves tasks to backend with app_id context

#### 2.1.3 Preview System

**Location**: `client/webui/frontend/src/lib/components/chat/ChatSidePanel.tsx`

- Renders app in sandboxed iframe
- Proxies app through `/api/v1/apps/preview/{app_id}/`
- Supports manual refresh to see code changes
- Sandbox attributes: `allow-scripts allow-same-origin allow-forms`

#### 2.1.4 SAM SDK Host (postMessage Bridge)

**Location**: `client/webui/frontend/src/lib/hooks/useSamSdkHost.ts`

Handles bidirectional postMessage communication between iframe (app) and parent (SAM UI):

**Incoming Messages from App (SDK):**
- `sam:init` → Respond with `sam:ready` + theme
- `sam:agent:list` → Fetch from `/api/v1/agentCards`, return agent list
- `sam:agent:call` → Create task, subscribe to SSE, stream results back
- `sam:storage:*` → Proxy to `/api/v1/apps/{app_id}/storage` endpoints
- `sam:artifact:upload` → Upload files to `/api/v1/artifacts/upload`
- `sam:theme:get` → Return current theme

**Outgoing Messages to App:**
- `sam:ready` → SDK initialization complete
- `sam:agent:list:response` → List of available agents
- `sam:agent:response` → Final agent response
- `sam:agent:stream` → Streaming text chunks
- `sam:agent:status` → Progress updates
- `sam:agent:artifact` → Artifact created
- `sam:storage:response` → Storage operation result
- `sam:theme:changed` → Theme changed (sent when parent theme changes)

### 2.2 Backend (Gateway APIs)

#### 2.2.1 Apps Router

**Location**: `src/solace_agent_mesh/gateway/http_sse/routers/apps.py`

**Endpoints:**
- `POST /api/v1/apps` → Create new app (empty workspace + DB record)
- `GET /api/v1/apps` → List user's apps with pagination
- `GET /api/v1/apps/{app_id}` → Get app metadata
- `PATCH /api/v1/apps/{app_id}` → Update app metadata (not yet implemented)
- `DELETE /api/v1/apps/{app_id}` → Archive app (not yet implemented)
- `POST /api/v1/apps/{app_id}/deploy` → Deploy new version (placeholder)
- `GET /api/v1/apps/preview/{app_id}/{path}` → Serve built app from dist/ folder

**Create App Flow:**
1. Generate unique `app_id` (slugified name + random suffix)
2. Create workspace path: `{workspace_base}/{user_id}/apps/{app_id}`
3. Create empty directory via `mkdir`
4. Insert database record (status='draft')
5. Return `app_id` and `workspace_path`

**Note**: Workspace initialization (template copy, git init) is now handled by the container when agent first connects, NOT by the gateway.

#### 2.2.2 Storage Router

**Location**: `src/solace_agent_mesh/gateway/http_sse/routers/storage.py`

App-scoped persistent storage endpoints:
- `GET /api/v1/apps/{app_id}/storage` → List all keys
- `GET /api/v1/apps/{app_id}/storage/{key}` → Get value
- `PUT /api/v1/apps/{app_id}/storage/{key}` → Set value
- `DELETE /api/v1/apps/{app_id}/storage/{key}` → Delete key
- `DELETE /api/v1/apps/{app_id}/storage` → Clear all storage

Storage is user-scoped, app-scoped, and persisted to database.

#### 2.2.3 Database Models

**Location**: `src/solace_agent_mesh/gateway/http_sse/repository/models/`

**AppModel** (`app_model.py`):
- `id`, `app_id`, `user_id`, `name`, `description`
- `workspace_id`, `status`, `current_version`
- `created_time`, `updated_time`, `archived_time`

**SessionModel** (`session_model.py`):
- Extended with `app_id` field for linking sessions to apps
- Sessions associated with apps are filtered by app in session lists

**Migration**: `alembic/versions/20251208_add_app_id_to_sessions.py`

#### 2.2.4 Repositories & Services

- **AppRepository**: CRUD operations for apps
- **SessionService**: Session management with app_id filtering
- **SessionRepository**: Database queries with app_id support

### 2.3 Claude Code Tools

#### 2.3.1 Execute Tool

**Location**: `src/solace_agent_mesh/agent/tools/claude_code/execute_tool.py`

Primary tool for executing Claude Code in app workspaces.

**Key Features:**
- Resolves workspace from `app_id` in A2A context (app mode)
- Hides workspace parameters from LLM (automatic binding)
- Calls `initialize_workspace_if_needed()` before executing
- Streams status updates back through SAM progress mechanism
- Manages persistent sessions across tool invocations

**Workflow:**
1. Extract `user_id` and `app_id` from tool context
2. Resolve workspace path: `{workspace_base}/{user_id}/apps/{app_id}`
3. Check if workspace needs initialization (empty directory)
4. Run container init script if needed (SAM apps only)
5. Execute Claude Code in container with streaming
6. Return results with session_id for continuation

#### 2.3.2 Workspace Management

**Location**: `src/solace_agent_mesh/agent/tools/claude_code/utils.py`

**Key Functions:**

`initialize_workspace_if_needed()` - Lines 492-595
- Checks if workspace is empty (no .git, minimal files)
- Only runs for `workspace_type='app'` (SAM apps)
- Runs container with `--entrypoint=/usr/local/bin/init-workspace.sh`
- Passes `APP_ID` and `APP_NAME` as environment variables
- Returns True if initialization ran, False if skipped

`run_claude_code_headless()` - Lines 223-490
- Detects SAM apps by checking if `/apps/` in workspace path
- Uses `claude-code-sam-app:latest` for SAM apps, `claude-code-{env}:latest` for others
- Builds container command with volume mounts
- Handles streaming vs non-streaming modes
- Parses JSON output and extracts session_id

#### 2.3.3 Context Injection (APP_CONTEXT.md)

**Location**: `src/solace_agent_mesh/agent/adk/workspace_callbacks/`

**Configuration** (in `app-agent.yaml`):
```yaml
workspace_context_injection:
  workspace_base: "${HOME}/.claude-workspaces"
  files:
    - path: "APP_CONTEXT.md"
      header: "## Current Application State (Auto-Updated from Workspace)"
      required: false
      max_size: 50000
```

**Purpose:**
- Automatically injects `APP_CONTEXT.md` content into system prompt before each LLM call
- Provides AppAgent with up-to-date application state
- Claude Code maintains this file (updated via prompt_suffix)
- Path resolved as: `{workspace_base}/{user_id}/apps/{app_id}/APP_CONTEXT.md`

### 2.4 Docker Containers

#### 2.4.1 claude-code-sam-app (App Builder Container)

**Location**: `docker/claude-code-sam-app/Dockerfile`

**Purpose**: Pre-built React template with all dependencies installed and validated.

**Base Image**: `node:20-alpine`

**Installed:**
- System tools: git, ripgrep, curl, bash, procps-ng
- Claude Code CLI: `@anthropic-ai/claude-code`
- React 19 + TypeScript 5.8 + Vite 6 + Tailwind CSS 3.4
- SAM SDK at `/template/node_modules/@sam/sdk` (pre-built)
- All npm dependencies (pre-installed)

**Structure:**
```
/template/          # Pre-built React template
  ├── src/          # React source code
  ├── public/       # Static assets
  ├── dist/         # Pre-built output (validated)
  ├── node_modules/ # All dependencies (including @sam/sdk)
  ├── package.json
  ├── tsconfig.json
  ├── vite.config.ts
  └── CLAUDE.md     # Full SAM SDK documentation

/usr/local/bin/init-workspace.sh  # Workspace initialization script
/workspace/                        # Mount point for app workspace
```

**Entrypoint**: `claude` (Claude Code CLI)

**Environment Variables:**
- `TEMPLATE_DIR=/template` - Location of template to copy

**Users:**
- Runs as `node` user (non-root)
- Home directory: `/home/node`
- Claude settings mounted at `/home/node/.claude`

#### 2.4.2 Template Structure

**Location**: `docker/claude-code-sam-app/template/`

**Key Files:**
- `src/main.tsx` - React entry point
- `src/App.tsx` - Root component with SAM SDK examples
- `src/index.css` - Tailwind imports
- `index.html` - HTML entry point
- `vite.config.ts` - Vite configuration
- `tailwind.config.ts` - Tailwind configuration
- `tsconfig.json` - TypeScript configuration
- `package.json` - Dependencies and scripts
- `CLAUDE.md` - Comprehensive SAM SDK documentation (300+ lines)

**Dependencies** (in `package.json`):
- `@sam/sdk` - SAM platform integration (file:../packages/sam-sdk)
- `react@^19.0.0` - React library
- `react-dom@^19.0.0` - React DOM renderer
- `clsx`, `tailwind-merge` - Utility libraries

**Build Process:**
- Dockerfile validates template builds successfully during image creation
- Template is self-contained (no external dependencies)

#### 2.4.3 Workspace Initialization Script

**Location**: `docker/init-workspace.sh`

**Purpose**: Universal script for initializing empty workspaces.

**Logic:**
1. Check if workspace is already initialized (has `.git` or files)
2. If already initialized, exit silently
3. If `$TEMPLATE_DIR` is set, copy template to workspace
4. If `$APP_ID` and `$APP_NAME` are set, update `package.json`:
   - Set `name` field to `$APP_ID`
   - Set `description` field to "SAM App: $APP_NAME"
   - Uses Node.js to properly parse/write JSON
5. Initialize git repository with initial commit
6. Output success message

**Usage:**
```bash
# Agent runs this when workspace is empty
podman run --rm \
  -v /workspace/path:/workspace \
  -e APP_ID=my-app-1234 \
  -e APP_NAME="My App" \
  --entrypoint=/usr/local/bin/init-workspace.sh \
  claude-code-sam-app:latest
```

---

## 3. App Agent

### 3.1 Configuration

**Location**: `examples/agents/app-agent.yaml`

**Agent Name**: `AppAgent` (also `app-agent_app`)
**Display Name**: "App Builder"
**Model**: Uses planning model (typically Claude Opus or Sonnet 4.5)

### 3.2 Core Capabilities

The AppAgent is designed to:
1. **Gather Requirements**: Ask clarifying questions about features, UI/UX, data sources
2. **Design Architecture**: Plan React component structure, data flow, SAM integrations
3. **Generate Code**: Use Claude Code to write TypeScript/React components
4. **Validate Builds**: Run `npm run build` to ensure code compiles
5. **Fix Errors**: Autonomously debug and fix build/runtime errors
6. **Iterate**: Respond to user feedback and make incremental changes

### 3.3 Instruction Highlights

**Context Awareness:**
- Has access to `APP_CONTEXT.md` (auto-injected before every LLM call)
- `APP_CONTEXT.md` maintained by Claude Code (via prompt_suffix)
- Always sees latest application state

**Error Handling:**
- Must pass errors DIRECTLY to claude_code_execute
- Must NOT attempt to fix errors manually
- Claude Code has full workspace access and can see actual code

**Build Process:**
- Must run `npm run build` after ANY code changes
- Must verify build succeeds before completing tasks
- Built app (dist/) immediately available in preview pane
- User manually refreshes preview to see changes (no auto-reload)

**SAM Integration:**
- SDK is production-ready (NOT a mock)
- Apps call real SAM agents via `SAM.agents.call()`
- Storage, artifacts, and UI APIs are fully functional

### 3.4 Available Tools

**Configured in tool_config:**

1. **claude_code_execute** - Primary coding tool
   - `default_environment: "node"` - Always uses Node.js container
   - `default_workspace_type: "app"` - Always uses app workspaces
   - `app_mode.enabled: true` - Automatic workspace binding
   - `app_mode.hide_workspace_params: true` - LLM doesn't see workspace params
   - `prompt_suffix` - Instructions for APP_CONTEXT.md maintenance and builds

2. **claude_code_read_files** - Read workspace files

3. **claude_code_create_version** - Create git tags for versions

4. **claude_code_export_workspace** - Export app as tar.gz

**Hidden Tools** (app mode):
- `claude_code_list_workspaces`
- `claude_code_list_sessions`
- `claude_code_import_workspace`

### 3.5 Skills (Agent Card)

**Defined in agent_card section:**

1. **app_design** - Analyzes requirements, designs architecture
2. **react_development** - Creates React apps with TypeScript/Tailwind
3. **sam_integration** - Integrates SAM SDK (agents, storage, artifacts, UI)
4. **incremental_development** - Builds features one at a time
5. **build_validation** - Validates builds, fixes errors autonomously

---

## 4. SAM SDK

### 4.1 SDK Overview

**Location**: `packages/sam-sdk/`

The SAM SDK is a production-ready TypeScript library that enables iframe-based apps to communicate with the SAM platform parent frame via postMessage.

**Build System**: Uses `tsup` to compile TypeScript to:
- CommonJS: `dist/index.js`
- ES Modules: `dist/index.mjs`
- Type Definitions: `dist/index.d.ts`, `dist/index.d.mts`

### 4.2 Communication Protocol

**Pattern**: Request/Response via postMessage

1. App (iframe) sends message to parent: `{ type: 'sam:agent:list', id: 'req-123', payload: {} }`
2. Parent processes request (API calls, etc.)
3. Parent sends response back: `{ type: 'sam:agent:list:response', id: 'req-123', payload: { agents: [...] } }`
4. SDK resolves promise with payload data

**Timeout**: 30 seconds per request

### 4.3 API Surface

#### 4.3.1 SAM.ready()

Wait for SDK to establish communication with parent.

```typescript
await SAM.ready()
```

#### 4.3.2 SAM.agents

**list()** - Get list of available agents
```typescript
const agents: AgentInfo[] = await SAM.agents.list()
// Returns: [{ id, name, description?, version?, capabilities? }]
```

**call()** - Call an agent
```typescript
const result = await SAM.agents.call('agent-name', {
  prompt: 'instruction',
  context: { key: 'value' },
  stream: true,
  onText: (text) => console.log(text),
  onStatus: (status) => console.log(status),
  onArtifact: (artifact) => console.log(artifact),
})
```

#### 4.3.3 SAM.storage

App-scoped, user-specific persistent storage:
- `get<T>(key: string): Promise<T | null>`
- `set<T>(key: string, value: T): Promise<void>`
- `delete(key: string): Promise<void>`
- `list(prefix?: string): Promise<string[]>`
- `clear(): Promise<void>`

#### 4.3.4 SAM.artifacts

File upload/download:
- `upload(file: File): Promise<string>` - Returns artifact ID
- `download(artifactId: string): Promise<Blob>` - Returns file as Blob

#### 4.3.5 SAM.ui

Theme and UI state:
- `getTheme(): Theme` - Returns 'light' or 'dark'
- `onThemeChange(callback): () => void` - Subscribe to theme changes, returns unsubscribe function

### 4.4 Message Types

**Location**: `packages/sam-sdk/src/types.ts`

```typescript
enum MessageType {
  // Initialization
  INIT = 'sam:init',
  READY = 'sam:ready',

  // Agent calls
  AGENT_CALL = 'sam:agent:call',
  AGENT_RESPONSE = 'sam:agent:response',
  AGENT_ERROR = 'sam:agent:error',
  AGENT_STREAM = 'sam:agent:stream',
  AGENT_STATUS = 'sam:agent:status',
  AGENT_ARTIFACT = 'sam:agent:artifact',
  AGENT_LIST = 'sam:agent:list',
  AGENT_LIST_RESPONSE = 'sam:agent:list:response',

  // Storage operations
  STORAGE_GET = 'sam:storage:get',
  STORAGE_SET = 'sam:storage:set',
  STORAGE_DELETE = 'sam:storage:delete',
  STORAGE_LIST = 'sam:storage:list',
  STORAGE_CLEAR = 'sam:storage:clear',
  STORAGE_RESPONSE = 'sam:storage:response',

  // Artifacts
  ARTIFACT_UPLOAD = 'sam:artifact:upload',
  ARTIFACT_DOWNLOAD = 'sam:artifact:download',
  ARTIFACT_RESPONSE = 'sam:artifact:response',

  // UI theme
  THEME_GET = 'sam:theme:get',
  THEME_RESPONSE = 'sam:theme:response',
  THEME_CHANGED = 'sam:theme:changed',
}
```

---

## 5. Data Flow & Communication

### 5.1 App Creation Flow

```
User clicks "Create App"
  ↓
Frontend: POST /api/v1/apps { name, description }
  ↓
Backend Gateway (apps.py):
  1. Generate app_id (slug + random suffix)
  2. Create empty directory: mkdir {workspace_base}/{user_id}/apps/{app_id}
  3. Insert DB record (AppModel)
  4. Return { app_id, workspace_path, status: 'draft' }
  ↓
Frontend: Navigate to /app/{app_id}
  ↓
ChatPage detects appId parameter
  ↓
Sets selectedAgentName = "AppAgent"
Sets appEditorMode = { appId }
Opens app-preview side panel
```

### 5.2 Chat Session Flow (User → Agent → Tools)

```
User types message in chat
  ↓
ChatProvider.handleSubmit():
  1. Build A2A Message with metadata:
     - agent_name: "AppAgent"
     - app_id: {app_id}
  2. POST /api/v1/message:stream
  ↓
Backend Gateway:
  1. Route to AppAgent based on agent_name in metadata
  2. Create task and session (with app_id)
  3. Return task_id
  ↓
Frontend subscribes to SSE: GET /api/v1/sse/subscribe/{task_id}
  ↓
AppAgent receives message:
  1. Reads APP_CONTEXT.md (auto-injected from workspace)
  2. Processes user request
  3. Calls claude_code_execute tool
  ↓
Tool resolves workspace from app_id in A2A context
  ↓
Tool checks if workspace needs initialization:
  - If empty: runs init-workspace.sh in container
  - If initialized: proceeds to execute
  ↓
Tool runs Claude Code in claude-code-sam-app container:
  podman run -v {workspace}:/workspace claude-code-sam-app:latest
  ↓
Claude Code:
  1. Reads/writes files in workspace
  2. Runs npm run build
  3. Updates APP_CONTEXT.md
  4. Returns results
  ↓
Tool streams results back through SSE
  ↓
Frontend displays agent response + updates messages
  ↓
User refreshes preview pane to see built app
```

### 5.3 SDK Communication Flow (iframe ↔ parent)

```
App loads in iframe
  ↓
SAM SDK constructor:
  window.addEventListener('message', handleMessage)
  window.parent.postMessage({ type: 'sam:init', id: 'xyz' })
  ↓
Parent (useSamSdkHost) receives sam:init
  ↓
Parent responds: { type: 'sam:ready', id: 'xyz', payload: { theme: 'light' } }
  ↓
SDK marks isReady = true, resolves ready() promise
  ↓
App calls: const agents = await SAM.agents.list()
  ↓
SDK sends: { type: 'sam:agent:list', id: 'abc' }
  ↓
Parent fetches: GET /api/v1/agentCards
  ↓
Parent transforms and responds: { type: 'sam:agent:list:response', id: 'abc', payload: { agents: [...] } }
  ↓
SDK resolves promise with agents array
  ↓
App renders agent list in UI
```

### 5.4 Workspace Initialization Flow

```
Gateway creates app: mkdir {workspace_base}/{user_id}/apps/{app_id}
  ↓
User sends first message to AppAgent
  ↓
claude_code_execute tool called
  ↓
Tool checks workspace:
  - Has .git? NO
  - Has files? NO (empty directory)
  - workspace_type == "app"? YES
  ↓
Tool runs initialization:
  podman run --rm \
    -v {workspace}:/workspace \
    -e APP_ID={app_id} \
    -e APP_NAME={name} \
    --entrypoint=/usr/local/bin/init-workspace.sh \
    claude-code-sam-app:latest
  ↓
init-workspace.sh:
  1. Copy /template/* to /workspace/
  2. Update package.json with app_id and app_name
  3. git init + git add + git commit
  ↓
Workspace now initialized:
  - All template files copied
  - node_modules with @sam/sdk installed
  - package.json customized
  - Git repository initialized
  ↓
Tool proceeds to execute Claude Code normally
```

---

## 6. Workspace Management

### 6.1 Workspace Structure

**Path Pattern**: `{workspace_base}/{user_id}/apps/{app_id}`

**Example**: `~/.claude-workspaces/sam_user/apps/todo-app-a1b2/`

**Contents After Initialization:**
```
{app_id}/
├── .git/                 # Git repository
├── src/
│   ├── main.tsx         # React entry point
│   ├── App.tsx          # Root component
│   └── index.css        # Tailwind imports
├── public/              # Static assets
├── dist/                # Build output (after npm run build)
├── node_modules/
│   └── @sam/sdk/        # SAM SDK (pre-built)
├── package.json         # Customized with app_id and app_name
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── CLAUDE.md            # SAM SDK documentation
└── APP_CONTEXT.md       # Auto-maintained by Claude Code
```

### 6.2 Template System

**Template Location** (in container): `/template/`

**Template Creation** (during Docker build):
1. Copy SAM SDK to `/build/packages/sam-sdk`
2. Copy template files to `/build/template`
3. Run `npm install` in template
4. Replace SDK symlink with actual files: `cp -r /build/packages/sam-sdk node_modules/@sam/sdk`
5. Validate build: `npm run build`
6. Move to final location: `cp -r /build/template /template`

**Self-Contained**: Template includes all dependencies, no external references needed.

### 6.3 Initialization Process

**Trigger**: When `initialize_workspace_if_needed()` detects empty workspace

**Conditions for Initialization:**
- No `.git` directory exists
- Fewer than 2 files in workspace (excluding hidden files)
- `workspace_type == "app"` (SAM apps only)

**Execution:**
1. Agent detects empty workspace
2. Agent runs container with init script entrypoint
3. Init script copies template and customizes metadata
4. Init script initializes git repository
5. Workspace ready for Claude Code execution

### 6.4 Git Integration

**Configuration** (in container):
- User: "Claude Code" <cc@workspace>
- Default branch: main

**Initial Commit**: "Initial commit from template" or "Initial commit"

**Purpose**: Track all changes, enable versioning, support rollback

---

## 7. Key File Reference

### 7.1 Frontend Files

**Pages & Components:**
- `client/webui/frontend/src/lib/components/pages/AppsPage.tsx` - App list view
- `client/webui/frontend/src/lib/components/pages/CreateAppPage.tsx` - Create app form
- `client/webui/frontend/src/lib/components/pages/ChatPage.tsx` - App editor (chat + preview)
- `client/webui/frontend/src/lib/components/chat/ChatSidePanel.tsx` - Preview iframe
- `client/webui/frontend/src/lib/components/apps/AppCard.tsx` - App card component

**Providers & Hooks:**
- `client/webui/frontend/src/lib/providers/ChatProvider.tsx` - Chat state management
- `client/webui/frontend/src/lib/hooks/useSamSdkHost.ts` - postMessage handler (SDK host)
- `client/webui/frontend/src/lib/hooks/useApp.ts` - Single app data fetching
- `client/webui/frontend/src/lib/hooks/useApps.ts` - App list data fetching

**Types:**
- `client/webui/frontend/src/lib/types/app.ts` - App type definitions
- `client/webui/frontend/src/lib/types/index.ts` - Includes Message types

**Routing:**
- `client/webui/frontend/src/router.tsx` - Defines /apps/* routes

### 7.2 Backend Files

**Routers:**
- `src/solace_agent_mesh/gateway/http_sse/routers/apps.py` - App CRUD + preview serving
- `src/solace_agent_mesh/gateway/http_sse/routers/storage.py` - App storage endpoints
- `src/solace_agent_mesh/gateway/http_sse/routers/sessions.py` - Session management with app_id
- `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py` - Task submission/management

**DTOs:**
- `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/app_requests.py`
- `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/app_responses.py`
- `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/storage_requests.py`
- `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/storage_responses.py`

**Database:**
- `src/solace_agent_mesh/gateway/http_sse/repository/models/app_model.py` - AppModel SQLAlchemy
- `src/solace_agent_mesh/gateway/http_sse/repository/models/session_model.py` - SessionModel (with app_id)
- `src/solace_agent_mesh/gateway/http_sse/repository/app_repository.py` - App DB operations
- `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20251207_add_apps_tables.py` - Migration
- `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20251208_add_app_id_to_sessions.py` - Migration

**Services:**
- `src/solace_agent_mesh/gateway/http_sse/services/session_service.py` - Session business logic

### 7.3 Tool Files

**Claude Code Tools:**
- `src/solace_agent_mesh/agent/tools/claude_code/tool_provider.py` - Tool registration
- `src/solace_agent_mesh/agent/tools/claude_code/execute_tool.py` - Main execution tool
- `src/solace_agent_mesh/agent/tools/claude_code/utils.py` - Helper functions (init, container execution)
- `src/solace_agent_mesh/agent/tools/claude_code/context_helpers.py` - App mode context resolution
- `src/solace_agent_mesh/agent/tools/claude_code/streaming_utils.py` - SSE streaming parser
- `src/solace_agent_mesh/agent/tools/claude_code/read_files_tool.py` - File reading
- `src/solace_agent_mesh/agent/tools/claude_code/create_version_tool.py` - Version tagging
- `src/solace_agent_mesh/agent/tools/claude_code/export_workspace_tool.py` - Workspace export

**Workspace Callbacks:**
- `src/solace_agent_mesh/agent/adk/workspace_callbacks/` - APP_CONTEXT.md injection logic
- `src/solace_agent_mesh/agent/adk/callbacks.py` - Callback registration
- `src/solace_agent_mesh/agent/adk/runner.py` - LLM call interception

### 7.4 Docker/Container Files

**Container Definitions:**
- `docker/claude-code-sam-app/Dockerfile` - App builder container
- `docker/claude-code-node/Dockerfile` - Node.js container
- `docker/claude-code-python/Dockerfile` - Python container
- `docker/claude-code-go/Dockerfile` - Go container

**Build Scripts:**
- `docker/claude-code-sam-app/build.sh` - Builds SAM SDK + container
- `docker/init-workspace.sh` - Universal workspace initialization script

**Template:**
- `docker/claude-code-sam-app/template/` - Complete React app template
- `docker/claude-code-sam-app/template/CLAUDE.md` - SAM SDK documentation (300+ lines)

### 7.5 SDK Files

**Source:**
- `packages/sam-sdk/src/index.ts` - Main exports
- `packages/sam-sdk/src/client.ts` - SAMClient implementation
- `packages/sam-sdk/src/types.ts` - Type definitions

**Build Output:**
- `packages/sam-sdk/dist/index.js` - CommonJS build
- `packages/sam-sdk/dist/index.mjs` - ES Module build
- `packages/sam-sdk/dist/index.d.ts` - TypeScript definitions

**Config:**
- `packages/sam-sdk/package.json` - Package metadata
- `packages/sam-sdk/tsconfig.json` - TypeScript config

---

## 8. Development Workflow

### 8.1 Creating a New App

1. User navigates to /apps and clicks "Create New App"
2. User enters app name and description
3. Frontend calls `POST /api/v1/apps`
4. Gateway creates empty workspace directory and DB record
5. User redirected to `/app/{app_id}` (chat interface)
6. ChatPage automatically selects AppAgent
7. User describes what they want to build

### 8.2 Agent-Driven Development

1. **Requirements Gathering**: AppAgent asks clarifying questions
2. **Planning**: AppAgent proposes component structure and features
3. **Implementation**: AppAgent calls `claude_code_execute` tool
4. **Tool Execution**:
   - Tool detects empty workspace → runs init script
   - Init script copies template, updates package.json, inits git
   - Tool executes Claude Code in container
   - Claude Code reads/writes files, runs npm run build
   - Claude Code updates APP_CONTEXT.md
5. **Results**: AppAgent receives results, informs user
6. **Preview**: User clicks Refresh in preview pane to see changes
7. **Iteration**: User provides feedback, AppAgent makes more changes

### 8.3 Live Preview & Hot Reload

**Preview Serving:**
- URL: `/api/v1/apps/preview/{app_id}/`
- Serves from: `{workspace_path}/dist/`
- CORS enabled for iframe sandbox
- HTML URL rewriting to fix asset paths
- SPA fallback: missing routes serve index.html

**Update Flow:**
1. Claude Code makes changes → runs `npm run build` → updates dist/
2. Built app immediately available at preview endpoint
3. User manually clicks "Refresh" button in preview pane
4. Iframe reloads, showing new version

**Note**: No auto-reload. Manual refresh required.

### 8.4 Build & Deploy

**Build:**
- Automatic via Claude Code after every change
- Command: `npm run build` (TypeScript compile + Vite build)
- Output: `dist/` folder with index.html and bundled assets

**Deploy** (future):
- Endpoint: `POST /api/v1/apps/{app_id}/deploy`
- Creates versioned deployment
- Updates current_version in database
- Creates git tag

---

## 9. Implementation Details

### 9.1 Session Association (app_id linking)

**Purpose**: Link chat sessions to apps for context and filtering.

**Implementation:**
- `app_id` added to `SessionModel` (migration: 20251208)
- Passed in message metadata: `metadata: { app_id: {app_id} }`
- Session created with `app_id` field populated
- Sessions filtered by `app_id` in session lists

**Benefit**: Users see only relevant chat sessions when in app context.

### 9.2 Context Injection (workspace context)

**Mechanism**: `workspace_context_injection` in app-agent.yaml

**Process:**
1. Before each LLM call, ADK runner intercepts
2. Resolves workspace path from `app_id` in A2A context
3. Reads `APP_CONTEXT.md` from workspace
4. Injects content into system instruction with header
5. LLM sees current application state

**Maintenance:**
- Claude Code updates `APP_CONTEXT.md` via prompt_suffix instruction
- Keeps file concise (under 20 lines recommended)
- Updates after significant changes only
- Contains: features, architecture, known issues, TODOs

**Benefits:**
- AppAgent always has up-to-date application state
- No need to manually read workspace files
- Context persists across conversation turns
- Reduces hallucination (LLM sees actual state)

### 9.3 Container Self-Initialization

**Problem Solved**: Gateway no longer needs container runtime (docker/podman).

**Old Approach** (removed):
```python
# Gateway ran containers to copy template
runtime = detect_container_runtime()  # Gateway had dependency
await asyncio.create_subprocess_exec(
    runtime, "run", "--rm",
    "-v", f"{workspace_path}:/output",
    "claude-code-sam-app:latest",
    "sh", "-c", "cp -r /template /output/{app_id}",
)
```

**New Approach** (current):
```python
# Gateway just creates directory
workspace_path.mkdir(parents=True, exist_ok=True)

# Agent tool detects empty workspace and runs init
if workspace is empty:
    podman run --entrypoint=/usr/local/bin/init-workspace.sh \
      -e APP_ID={app_id} \
      -e APP_NAME={name} \
      -v {workspace}:/workspace \
      claude-code-sam-app:latest
```

**Benefits:**
- Gateway has no container dependency
- Container holds both template and initialization logic
- Clean separation: gateway manages directories, container manages workspaces
- Init script output doesn't interfere with Claude Code stdout streaming

### 9.4 Permission & Security Model

**User Isolation:**
- Workspaces scoped by user_id: `{base}/{user_id}/apps/{app_id}`
- Sessions filtered by user_id
- Storage scoped by app_id + user_id

**App Isolation:**
- Each app has dedicated workspace directory
- Storage is app-scoped (no cross-app access)
- Sessions associated with specific apps

**Container Security:**
- Runs as non-root user (node)
- Workspace mounted with SELinux label (:Z flag)
- Sandboxed execution in Docker/Podman
- No host network access (isolated)

**iframe Security:**
- Sandbox attributes: `allow-scripts allow-same-origin allow-forms`
- CORS enabled for preview endpoint
- Cross-Origin-Resource-Policy: cross-origin
- Apps can only communicate via postMessage (no direct DOM access)

**API Security:**
- All endpoints require authentication (JWT)
- Agent list filtered by user permissions/scopes
- Storage/artifacts scoped to user + app
- Preview endpoint validates user owns app before serving

---

## 10. Agent Card & Discovery

**AppAgent Agent Card** (defined in app-agent.yaml):

```yaml
description: "AI-powered app builder that creates production-ready React applications for the SAM platform..."

skills:
  - app_design: Architecture and planning
  - react_development: React 19 + TypeScript development
  - sam_integration: SAM SDK integration
  - incremental_development: Feature-by-feature building
  - build_validation: Build checks and error recovery
```

**Discovery:**
- AppAgent publishes agent card every 10 seconds
- Available at `/api/v1/agentCards` endpoint
- Filtered by user's `agent:*:delegate` scopes
- Apps can discover via `SAM.agents.list()`

---

## 11. Known Limitations & Future Enhancements

### Current Limitations

1. **SDK Updates**: Existing apps don't auto-update SDK (manual copy needed)
2. **No Hot Reload**: Preview requires manual refresh
3. **Deploy Placeholder**: Deploy endpoint not fully implemented
4. **Single Template**: Only React template available
5. **No Version History UI**: Can create versions but no UI to browse/restore

### Future Enhancements

1. **SDK CDN**: Serve SDK from shared URL for automatic updates
2. **Live Reload**: WebSocket-based hot module reloading
3. **Multiple Templates**: Python, Go, Vue, Svelte templates
4. **Deployment System**: Production builds with versioned URLs
5. **Version Management UI**: Browse/compare/restore previous versions
6. **App Sharing**: Share apps with other users
7. **App Marketplace**: Discover and clone community apps

---

## 12. Troubleshooting

### Issue: SDK method not found in app

**Symptom**: `SAM.agents.list() is not available in this SDK version`

**Cause**: App was created before SDK update, has old SDK version in node_modules

**Solution**:
```bash
# Copy latest SDK to app workspace
cp -r packages/sam-sdk/dist/* \
  ~/.claude-workspaces/{user_id}/apps/{app_id}/node_modules/@sam/sdk/dist/
```

**Long-term**: Need SDK update mechanism for existing apps

### Issue: App preview shows 404

**Symptom**: Preview pane shows "App not built yet"

**Cause**: `dist/` folder doesn't exist (build hasn't run)

**Solution**: Ask AppAgent to make a change (triggering build) or run `npm run build` manually

### Issue: Workspace not initializing

**Symptom**: Empty workspace, template not copied

**Cause**: Init script not running or failing

**Debug**:
1. Check if container has init script: `podman run --entrypoint=ls claude-code-sam-app:latest /usr/local/bin/`
2. Run init manually: `podman run --entrypoint=/usr/local/bin/init-workspace.sh -v {workspace}:/workspace claude-code-sam-app:latest`
3. Check logs for errors

### Issue: Agent using wrong agent (Orchestrator instead of AppAgent)

**Symptom**: Chat session in app builder uses OrchestratorAgent

**Cause**: AppAgent not available or routing logic falling back to default

**Solution**: Verify AppAgent is running and registered in agent registry. Check that `agent_name: "AppAgent"` is in message metadata.

---

## Appendix A: Environment Variables

**Gateway:**
- `DATABASE_URL` - PostgreSQL/SQLite connection string
- `WORKSPACE_BASE` - Base directory for workspaces (default: ~/.claude-workspaces)

**AppAgent:**
- `NAMESPACE` - A2A topic namespace
- `APP_AGENT_DATABASE_URL` - AppAgent session database
- `ANTHROPIC_API_KEY` - Claude API key
- `ANTHROPIC_BASE_URL` - Anthropic API base URL
- `ANTHROPIC_BEDROCK_BASE_URL` - Bedrock API base URL
- `GITHUB_TOKEN` - GitHub token for Claude Code (optional)
- `NPM_TOKEN` - NPM token for Claude Code (optional)

**Container (claude-code-sam-app):**
- `APP_ID` - Unique app identifier (set by init script invocation)
- `APP_NAME` - Human-readable app name (set by init script invocation)
- `TEMPLATE_DIR` - Location of template in container (default: /template)
- `WORKSPACE_DIR` - Workspace mount point (default: /workspace)
- `ANTHROPIC_API_KEY` - Passed through from tool_config

---

## Appendix B: URL Patterns

**Frontend Routes:**
- `/apps` - App list page
- `/apps/new` - Create new app page
- `/app/{app_id}` - App editor (chat + preview)

**Backend API Endpoints:**
- `/api/v1/apps` - App CRUD operations
- `/api/v1/apps/{app_id}` - Get app details
- `/api/v1/apps/{app_id}/deploy` - Deploy app
- `/api/v1/apps/preview/{app_id}/` - Serve built app
- `/api/v1/apps/{app_id}/storage` - Storage operations
- `/api/v1/apps/{app_id}/storage/{key}` - Get/set/delete key
- `/api/v1/agentCards` - List available agents
- `/api/v1/message:stream` - Send message to agent
- `/api/v1/sse/subscribe/{task_id}` - Subscribe to task SSE stream

---

## Appendix C: Docker Build Commands

**Build SAM App Container:**
```bash
./docker/claude-code-sam-app/build.sh
# or
cd packages/sam-sdk && npm run build
podman build -f docker/claude-code-sam-app/Dockerfile -t claude-code-sam-app:latest .
```

**Build Other Containers:**
```bash
podman build -f docker/claude-code-node/Dockerfile -t claude-code-node:latest .
podman build -f docker/claude-code-python/Dockerfile -t claude-code-python:latest .
podman build -f docker/claude-code-go/Dockerfile -t claude-code-go:latest .
```

**Test Init Script:**
```bash
mkdir -p /tmp/test-app
podman run --rm \
  -v /tmp/test-app:/workspace \
  -e APP_ID=test-123 \
  -e APP_NAME="Test App" \
  --entrypoint=/usr/local/bin/init-workspace.sh \
  claude-code-sam-app:latest
```

---

## Appendix D: Key Design Decisions

### Why postMessage for SDK?

**Pros:**
- Standard browser API for iframe communication
- Works with any framework (React, Vue, Svelte, vanilla)
- Secure (origin-based access control)
- Bidirectional (parent↔child)
- Supports async request/response pattern

**Cons:**
- Requires serialization (no functions/DOM nodes)
- More complex than direct API calls
- Debugging harder (message passing layer)

### Why Container Self-Initialization?

**Previous**: Gateway ran containers to initialize workspaces
**Problem**: Gateway had container runtime dependency, mixed concerns

**Current**: Containers initialize themselves via init script
**Benefits**:
- No gateway container dependency
- Single source of truth (container knows its setup)
- Clean stdout (init runs separately)
- Better separation of concerns

### Why APP_CONTEXT.md Auto-Injection?

**Problem**: AppAgent lost context between turns, asked repetitive questions

**Solution**: Claude Code maintains APP_CONTEXT.md, auto-injected before each LLM call

**Benefits**:
- AppAgent always knows current state
- Reduces hallucination
- Improves multi-turn coherence
- No manual file reading needed

### Why App Mode (hide_workspace_params)?

**Problem**: LLM had to specify workspace_id every time, could make mistakes

**Solution**: Extract app_id from A2A context, auto-bind to workspace

**Benefits**:
- LLM can't make workspace mistakes
- Simpler tool interface for LLM
- Automatic workspace routing
- Consistent behavior

---

**Document Version**: 1.0
**Last Updated**: 2025-12-09
**Maintainer**: SAM Platform Team
