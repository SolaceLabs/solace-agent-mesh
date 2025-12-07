# SAM Apps Feature - Architecture & Implementation Plan

**Version:** 1.0
**Date:** December 6, 2024
**Status:** Planning

## Executive Summary

The SAM Apps feature enables users to build fully-fledged HTML-based applications that run in the SAM UI within secure iframes. These apps are 100% coded by AI using a coding agent with Claude Code tools, providing users with the ability to create custom dashboards, data visualizations, and interactive tools tailored to their specific needs.

### Key Capabilities

- **AI-Generated Apps**: Apps are created entirely by an AI coding agent using claude-code tools
- **Full-Stack Framework**: React + Tailwind + TypeScript pre-configured with hot reload
- **SAM Integration**: Apps can call agents, access LLMs, manage artifacts, and persist data
- **Isolated Execution**: Each app runs in a sandboxed iframe with per-app storage
- **Version Control**: Git-based versioning through claude-code workspaces

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [User Experience Flow](#user-experience-flow)
3. [SAM SDK Design](#sam-sdk-design)
4. [Backend Infrastructure](#backend-infrastructure)
5. [Frontend Integration](#frontend-integration)
6. [Claude Code Integration](#claude-code-integration)
7. [Security Model](#security-model)
8. [Implementation Roadmap](#implementation-roadmap)
9. [API Reference](#api-reference)
10. [Examples](#examples)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SAM UI (Parent)                          │
│  ┌────────────┬────────────┬────────────┬──────────────────┐   │
│  │   Chats    │  Projects  │  Prompts   │   Apps (NEW)     │   │
│  └────────────┴────────────┴────────────┴──────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              App Frame (iframe container)                │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │          User's App (AI-Generated)                │  │   │
│  │  │  ┌─────────────────────────────────────────────┐  │  │   │
│  │  │  │  React Components + SAM SDK                 │  │  │   │
│  │  │  │  - Agent Calls                              │  │  │   │
│  │  │  │  - LLM Access                               │  │  │   │
│  │  │  │  - Artifact Management                      │  │  │   │
│  │  │  │  - Storage (key-value)                      │  │  │   │
│  │  │  └─────────────────────────────────────────────┘  │  │   │
│  │  │          ▲                                         │  │   │
│  │  │          │ @sam/sdk (TypeScript)                  │  │   │
│  │  │          │                                         │  │   │
│  │  │          │ postMessage (init) + REST/SSE (runtime)│  │   │
│  │  └──────────┼─────────────────────────────────────────┘  │   │
│  └─────────────┼─────────────────────────────────────────────┘   │
│                │                                                   │
└────────────────┼───────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SAM Backend (FastAPI)                         │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Existing Routers:                                         │ │
│  │  - /message:stream (agent calls)                           │ │
│  │  - /artifacts/* (upload, download, list, delete)           │ │
│  │  - /tasks/* (list, get, events)                            │ │
│  │  - /sessions/* (CRUD)                                      │ │
│  │  - /agentCards (list agents)                               │ │
│  │  - /people/search (user search)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  NEW Routers (for Apps):                                   │ │
│  │  - /storage/* (per-app key-value storage)                  │ │
│  │  - /llm/* (direct LLM completion)                          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│              Claude Code Tools (Containerized)                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Workspace Type: "app"                                     │ │
│  │  Environment: node (React + Vite + Tailwind)               │ │
│  │  Pre-installed: @sam/sdk package                           │ │
│  │  Git: Automatic versioning                                 │ │
│  │  Testing: Build validation + linting                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### 1. **SAM UI (Parent Frame)**
- Navigation to /apps route
- Apps list/grid view
- App creation via coding agent
- App iframe container with security controls
- postMessage initialization handshake
- Theme propagation (dark/light mode)

#### 2. **User's App (Iframe)**
- React 19 + TypeScript + Tailwind
- SAM SDK for platform integration
- Custom UI/UX built by AI
- Isolated storage namespace
- Direct API access to SAM backend

#### 3. **SAM SDK** (`@sam/sdk`)
- TypeScript library pre-installed in containers
- Modules: auth, agents, llm, artifacts, storage, tasks, ui
- React hooks for ergonomic integration
- EventSource for streaming responses
- Type-safe API with full TypeScript support

#### 4. **SAM Backend**
- Existing routers for agent calling, artifacts, tasks
- NEW: Storage router for app-scoped key-value persistence
- NEW: LLM router for direct Claude API access
- Authentication & authorization
- Rate limiting via user quotas

#### 5. **Claude Code Tools**
- Containerized development environment
- Workspace management (git, build, test)
- Multi-turn AI coding sessions
- Hot reload during development
- Build validation before deployment

---

## User Experience Flow

### App Creation Flow

```
1. User: "Create an app"
   └─> SAM UI navigates to /apps route

2. User clicks "New App"
   └─> Opens creation dialog
   └─> User provides: name, description, desired features

3. SAM UI initiates coding agent
   └─> Creates claude-code workspace (type: "app", environment: "node")
   └─> Generates CLAUDE.md with:
       - App name & description
       - Available libraries (React, Tailwind, Plotly, etc.)
       - SAM SDK documentation
       - Required features from user

4. Coding agent (multi-turn)
   Turn 1: "Set up React app with Vite + Tailwind"
   Turn 2: "Install SAM SDK and create base layout"
   Turn 3: "Implement dashboard with agent calling"
   Turn 4: "Add data visualization with Plotly"
   Turn 5: "Run build and tests"
   └─> Agent uses claude_code_execute tool for each turn

5. Build validation
   └─> npm run build succeeds
   └─> npm run lint passes
   └─> App artifacts created in workspace

6. Deployment
   └─> App registered in SAM database
   └─> Workspace marked as "app" type
   └─> User sees app in apps list

7. Running the app
   └─> User clicks app from list
   └─> SAM UI loads app in iframe
   └─> postMessage handshake initializes SAM SDK
   └─> App renders with full SAM integration
```

### App Usage Flow

```
1. User navigates to /apps
   └─> Sees grid of available apps

2. User clicks app
   └─> SAM UI creates AppFrame component
   └─> Mounts iframe with sandbox attributes
   └─> Serves app from workspace build output

3. Iframe loads app
   └─> App imports SAM SDK
   └─> SDK sends "ready" postMessage to parent

4. Parent responds with initialization data
   {
     type: "init",
     authToken: "...",
     apiEndpoint: "https://sam.example.com/api/v1",
     user: { id, email, displayName },
     theme: "dark",
     appId: "user-dashboard"
   }

5. SDK initializes
   └─> Stores auth token in memory
   └─> Sets up API client
   └─> Emits "initialized" event

6. App renders
   └─> Makes agent calls via SAM.agents.call()
   └─> Fetches data via SAM.storage.get()
   └─> Displays UI with theme inherited from parent

7. Hot reload (during development)
   └─> User requests changes via coding agent
   └─> Agent modifies code
   └─> Vite hot-reloads iframe
   └─> Changes appear immediately
```

---

## SAM SDK Design

### Package Structure

```
client/webui/sam-sdk/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── README.md
├── src/
│   ├── index.ts                 # Main entry, exports SAM object
│   ├── core/
│   │   ├── SamSDK.ts            # Main SDK class
│   │   ├── transport.ts         # postMessage initialization
│   │   └── config.ts            # SDK configuration
│   ├── modules/
│   │   ├── auth.ts              # Authentication module
│   │   ├── agents.ts            # Agent calling
│   │   ├── llm.ts               # Direct LLM access
│   │   ├── artifacts.ts         # Artifact CRUD
│   │   ├── tasks.ts             # Task history
│   │   ├── storage.ts           # Key-value storage
│   │   ├── users.ts             # User search
│   │   ├── notifications.ts     # Toast notifications
│   │   └── ui.ts                # Theme, parent UI integration
│   ├── utils/
│   │   ├── api.ts               # authenticatedFetch wrapper
│   │   ├── events.ts            # EventEmitter
│   │   └── helpers.ts           # Utilities
│   └── types/
│       ├── index.ts             # All type exports
│       ├── sdk.ts               # SDK-specific types
│       └── api.ts               # API request/response types
├── react/                       # React-specific exports
│   ├── index.ts
│   └── hooks.ts                 # useAgent, useStorage, etc.
└── dist/                        # Build output
    ├── index.js
    ├── index.d.ts
    └── sam-sdk.css
```

### Core API

```typescript
// Import SDK
import { SAM } from '@sam/sdk';

// SDK auto-initializes via postMessage handshake
await SAM.ready(); // Promise resolves when initialized

// ===== AUTH MODULE =====
const user = SAM.auth.getCurrentUser();
// { userId: string, email: string, displayName: string, permissions: string[] }

SAM.auth.onAuthChange((user) => {
  if (!user) {
    // Handle logout
  }
});

// ===== AGENT MODULE =====
// Simple agent call
const result = await SAM.agents.call('data-analyzer', {
  prompt: 'Analyze sales data',
  context: { timeframe: 'last-30-days' }
});

// Streaming agent call
const stream = SAM.agents.stream('report-generator', {
  prompt: 'Generate quarterly report'
});

stream.on('status', (status) => {
  console.log('Status:', status.message);
});

stream.on('text', (chunk) => {
  appendToUI(chunk);
});

stream.on('artifact', (artifact) => {
  console.log('Created:', artifact.filename);
});

stream.on('complete', (result) => {
  console.log('Done!', result);
});

stream.on('error', (error) => {
  handleError(error);
});

// ===== LLM MODULE =====
// Direct Claude access
const response = await SAM.llm.complete({
  prompt: 'Summarize this data',
  model: 'claude-sonnet-4',
  maxTokens: 1000
});

// Streaming LLM
const llmStream = SAM.llm.stream({
  messages: [
    { role: 'user', content: 'Write a poem' }
  ]
});

llmStream.on('text', (chunk) => { /* ... */ });

// ===== ARTIFACTS MODULE =====
// Upload
const artifact = await SAM.artifacts.upload(file, {
  description: 'User data CSV'
});

// Download
const blob = await SAM.artifacts.download(artifactId);
const url = URL.createObjectURL(blob);

// List
const artifacts = await SAM.artifacts.list({
  type: 'image/*',
  limit: 20
});

// Delete
await SAM.artifacts.delete(artifactId);

// ===== STORAGE MODULE =====
// Get/Set (app-scoped automatically)
await SAM.storage.set('user-preferences', {
  theme: 'dark',
  layout: 'grid'
});

const prefs = await SAM.storage.get('user-preferences');

// List keys
const keys = await SAM.storage.keys();

// Bulk operations
await SAM.storage.setMany({
  'key1': 'value1',
  'key2': { complex: 'object' }
});

const data = await SAM.storage.getMany(['key1', 'key2']);

// ===== TASKS MODULE =====
// List tasks
const tasks = await SAM.tasks.list({
  status: 'completed',
  limit: 20
});

// Get task
const task = await SAM.tasks.get(taskId);

// ===== USERS MODULE =====
// Search users
const users = await SAM.users.search('john');

// ===== UI MODULE =====
// Get theme
const theme = SAM.ui.getTheme(); // 'light' | 'dark'

// Listen for theme changes
SAM.ui.onThemeChange((theme) => {
  applyTheme(theme);
});

// Show notification in parent
SAM.ui.showNotification({
  title: 'Success',
  message: 'Data saved',
  type: 'success'
});

// Open artifact in parent UI
SAM.ui.openArtifact(artifactId);
```

### React Hooks

```typescript
import { useAgent, useStorage, useArtifacts, useTheme } from '@sam/sdk/react';

function MyDashboard() {
  // Agent calling hook
  const { call, loading, result, error } = useAgent('data-analyzer');

  // Storage hook (like useState but persisted)
  const [preferences, setPreferences] = useStorage('user-prefs', {
    theme: 'dark',
    refreshInterval: 5000
  });

  // Artifacts hook
  const { artifacts, loading: artifactsLoading, refetch } = useArtifacts();

  // Theme hook
  const { theme, setTheme } = useTheme();

  return (
    <div className={theme === 'dark' ? 'dark' : ''}>
      <button onClick={() => call({ prompt: 'Analyze data' })}>
        Analyze
      </button>
      {loading && <Spinner />}
      {result && <ResultView data={result} />}
    </div>
  );
}
```

---

## Backend Infrastructure

### Existing Endpoints (SDK Can Use)

From `src/solace_agent_mesh/gateway/http_sse/routers/`:

#### tasks.py
- `POST /message:stream` - Agent calling with SSE
- `POST /message:send` - Non-streaming agent call
- `GET /tasks` - List all tasks
- `GET /tasks/{task_id}` - Get task details
- `GET /tasks/{task_id}/events` - Get task events
- `POST /tasks/{taskId}:cancel` - Cancel task

#### artifacts.py
- `POST /artifacts/upload` - Upload artifact (FormData)
- `GET /artifacts/{session_id}` - List artifacts
- `GET /artifacts/{session_id}/download/{filename}` - Download
- `DELETE /artifacts/{session_id}/{filename}` - Delete

#### sessions.py
- `GET /sessions` - List sessions
- `GET /sessions/search` - Search sessions
- `GET /sessions/{session_id}` - Get session

#### agent_cards.py
- `GET /agentCards` - List available agents

#### users.py
- `GET /me` - Current user info
- `GET /me/capabilities` - User capabilities

#### people.py
- `GET /people/search` - Search users

#### auth.py
- `POST /auth/refresh` - Refresh access token

### New Endpoints Required

#### 1. Storage Router (`routers/storage.py`)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from ..shared.auth_utils import get_current_user

router = APIRouter(prefix="/storage", tags=["Storage"])

@router.get("/{app_id}/{key}")
async def get_value(
    app_id: str,
    key: str,
    user_id: str = Depends(get_current_user)
):
    """Get value from app storage"""
    # Query: SELECT value FROM storage WHERE user_id=? AND app_id=? AND key=?
    pass

@router.post("/{app_id}/{key}")
async def set_value(
    app_id: str,
    key: str,
    value: dict,
    user_id: str = Depends(get_current_user)
):
    """Set value in app storage"""
    # INSERT OR UPDATE storage
    pass

@router.delete("/{app_id}/{key}")
async def delete_value(
    app_id: str,
    key: str,
    user_id: str = Depends(get_current_user)
):
    """Delete value from app storage"""
    pass

@router.get("/{app_id}/keys")
async def list_keys(
    app_id: str,
    user_id: str = Depends(get_current_user)
):
    """List all keys in app storage"""
    pass

@router.post("/{app_id}:batch-get")
async def batch_get(
    app_id: str,
    keys: list[str],
    user_id: str = Depends(get_current_user)
):
    """Get multiple values at once"""
    pass

@router.post("/{app_id}:batch-set")
async def batch_set(
    app_id: str,
    data: dict[str, any],
    user_id: str = Depends(get_current_user)
):
    """Set multiple values at once"""
    pass
```

**Database Schema:**

```sql
CREATE TABLE storage (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    app_id VARCHAR(255) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    UNIQUE(user_id, app_id, key)
);

CREATE INDEX idx_storage_lookup ON storage(user_id, app_id, key);
CREATE INDEX idx_storage_app ON storage(user_id, app_id);
```

#### 2. LLM Router (`routers/llm.py`)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ..shared.auth_utils import get_current_user

router = APIRouter(prefix="/llm", tags=["LLM"])

@router.post("/complete")
async def complete(
    request: LLMCompletionRequest,
    user_id: str = Depends(get_current_user)
):
    """Direct LLM completion (non-streaming)"""
    # Use SAM's existing LLM provider
    # Apply user rate limits
    # Return completion
    pass

@router.post("/stream")
async def stream(
    request: LLMCompletionRequest,
    user_id: str = Depends(get_current_user)
):
    """Streaming LLM completion (SSE)"""
    # Use SAM's existing LLM provider
    # Stream via EventSource
    async def generate():
        async for chunk in llm_provider.stream(request):
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

**Request/Response Types:**

```python
class LLMCompletionRequest(BaseModel):
    prompt: Optional[str] = None
    messages: Optional[list[Message]] = None
    model: Optional[str] = "claude-sonnet-4"
    max_tokens: Optional[int] = 4000
    temperature: Optional[float] = 1.0

class LLMCompletionResponse(BaseModel):
    text: str
    model: str
    usage: TokenUsage
```

---

## Frontend Integration

### Apps Navigation

Add new route to SAM UI router:

```typescript
// client/webui/frontend/src/main.tsx or routes config

const router = createBrowserRouter([
  // ... existing routes
  {
    path: "/apps",
    element: <AppsPage />,
  },
  {
    path: "/apps/:appId",
    element: <AppViewPage />,
  },
]);
```

### Apps List Page

```typescript
// client/webui/frontend/src/pages/AppsPage.tsx

export function AppsPage() {
  const { apps, loading } = useApps(); // Custom hook
  const navigate = useNavigate();

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">My Apps</h1>
        <Button onClick={() => navigate('/apps/new')}>
          New App
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {apps.map(app => (
          <AppCard
            key={app.id}
            app={app}
            onClick={() => navigate(`/apps/${app.id}`)}
          />
        ))}
      </div>
    </div>
  );
}
```

### App Frame Component

```typescript
// client/webui/frontend/src/components/apps/AppFrame.tsx

interface AppFrameProps {
  appId: string;
  workspacePath: string;
}

export function AppFrame({ appId, workspacePath }: AppFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { user } = useAuthContext();
  const { theme } = useThemeContext();
  const { configServerUrl } = useConfigContext();

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Wait for iframe to load
    iframe.onload = () => {
      // Send initialization message
      iframe.contentWindow?.postMessage({
        type: 'init',
        authToken: getAccessToken(),
        apiEndpoint: `${configServerUrl}/api/v1`,
        user: {
          id: user.userId,
          email: user.email,
          displayName: user.displayName
        },
        theme: theme,
        appId: appId
      }, '*'); // TODO: Restrict origin
    };

    // Listen for messages from app
    const handleMessage = (event: MessageEvent) => {
      // Validate origin
      if (event.source !== iframe.contentWindow) return;

      const { type, payload } = event.data;

      switch (type) {
        case 'ready':
          console.log('App ready');
          break;
        case 'notification':
          showNotification(payload);
          break;
        case 'openArtifact':
          // Navigate to artifact view
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [appId, user, theme]);

  return (
    <iframe
      ref={iframeRef}
      src={`/apps/${appId}/index.html`}
      sandbox="allow-scripts allow-same-origin"
      className="w-full h-full border-0"
      title={`App: ${appId}`}
    />
  );
}
```

### App Creation Dialog

```typescript
// client/webui/frontend/src/components/apps/CreateAppDialog.tsx

export function CreateAppDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [features, setFeatures] = useState('');
  const { createApp, loading } = useAppCreation();

  const handleCreate = async () => {
    const app = await createApp({
      name,
      description,
      features,
    });

    if (app) {
      onClose();
      navigate(`/apps/${app.id}`);
    }
  };

  return (
    <Dialog>
      <DialogContent>
        <DialogTitle>Create New App</DialogTitle>

        <Input
          label="App Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <Textarea
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

        <Textarea
          label="Features (what should this app do?)"
          value={features}
          onChange={(e) => setFeatures(e.target.value)}
          rows={5}
        />

        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button onClick={handleCreate} loading={loading}>
            Create App
          </Button>
        </DialogActions>
      </DialogContent>
    </Dialog>
  );
}
```

---

## Claude Code Integration

### Workspace Configuration

Apps are created as claude-code workspaces with `workspace_type: "app"`:

```yaml
workspace_id: "user-{userId}-app-{appName}"
workspace_type: "app"
environment: "node"
workspace_name: "{App Name}"
workspace_description: "{User's description}"
```

### Container Pre-installation

Add SAM SDK to `docker/claude-code-node/Dockerfile`:

```dockerfile
FROM node:20-slim

# ... existing setup ...

# Install SAM SDK globally
RUN npm install -g @sam/sdk

# ... rest of container setup ...
```

### CLAUDE.md Template

Generated for each app workspace:

```markdown
# {App Name}

{User's description}

## Environment

This is a React + TypeScript + Vite + Tailwind application that will run in the SAM platform.

## Available Tools & Libraries

Pre-installed npm packages:
- react@19
- react-dom@19
- typescript@5.8
- vite@6
- tailwindcss@4
- @sam/sdk (SAM platform integration)
- plotly.js (data visualization)
- recharts (charts)
- lucide-react (icons)
- clsx, tailwind-merge

## SAM SDK

The `@sam/sdk` package provides integration with the SAM platform:

```typescript
import { SAM } from '@sam/sdk';

// Call agents
const result = await SAM.agents.call('agent-name', { prompt: '...' });

// Access LLM
const response = await SAM.llm.complete({ prompt: '...' });

// Manage artifacts
const artifact = await SAM.artifacts.upload(file);

// Persist data (app-scoped)
await SAM.storage.set('key', value);
const data = await SAM.storage.get('key');
```

See full SDK documentation at the end of this file.

## Requirements

- Build must succeed: `npm run build`
- Linting must pass: `npm run lint`
- TypeScript must compile without errors
- App must be responsive (mobile + desktop)
- Follow React best practices (hooks, composition)

## Development Process

1. Set up project structure
2. Install dependencies
3. Create components
4. Implement features using SAM SDK
5. Test build and lint
6. Verify functionality

---

## SAM SDK Full Reference

[Full API documentation here - same as earlier in this doc]
```

### Agent Instructions

The coding agent should receive these instructions:

```
You are building a React application that will run in the SAM platform.

CRITICAL REQUIREMENTS:
- Use TypeScript for all code
- Use Tailwind CSS for styling
- Follow React 19 patterns (hooks, composition)
- Use @sam/sdk for all SAM platform integration
- Run `npm run build` and `npm run lint` before finishing
- Ensure app is responsive

AVAILABLE via @sam/sdk:
- SAM.agents.call() - Call SAM agents
- SAM.llm.complete() - Direct LLM access
- SAM.artifacts.upload() - Upload files
- SAM.storage.set()/get() - Persist app data

WORKFLOW:
1. Create project structure (src/, public/, etc.)
2. Set up Vite config, tsconfig, tailwind config
3. Install dependencies
4. Build React components
5. Integrate with SAM SDK
6. Test: npm run build && npm run lint
7. Verify: Test in development mode

DO NOT:
- Ask for approval to run builds or tests
- Create unnecessary abstractions
- Add features not requested
- Skip build validation
```

---

## Security Model

### iframe Sandboxing

```html
<iframe
  sandbox="allow-scripts allow-same-origin"
  src="/apps/{appId}/index.html"
/>
```

**Sandbox restrictions:**
- `allow-scripts`: Required for React
- `allow-same-origin`: Allows API calls to SAM backend
- NO `allow-top-navigation`: Prevents escaping iframe
- NO `allow-popups`: Blocks popup windows
- NO `allow-forms`: Prevents form submissions outside API

### Content Security Policy

Apps should have restricted CSP:

```http
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  connect-src https://{SAM_DOMAIN};
  img-src 'self' data: https:;
  font-src 'self';
```

### postMessage Origin Validation

SDK validates origin:

```typescript
window.addEventListener('message', (event) => {
  // Only accept messages from SAM parent
  if (event.origin !== window.location.ancestorOrigins[0]) {
    return;
  }

  // Process message
});
```

Parent validates origin:

```typescript
const handleMessage = (event: MessageEvent) => {
  // Only accept from our iframe
  if (event.source !== iframeRef.current?.contentWindow) {
    return;
  }

  // Process message
};
```

### Authentication

- Parent never sends refresh token to iframe
- Access token passed once via postMessage on init
- SDK stores token in memory (not localStorage)
- Token expires with parent session
- SDK cannot access cookies or local storage

### Storage Isolation

- Each app gets its own storage namespace
- Storage keyed by `(user_id, app_id, key)`
- Apps cannot access other apps' data
- Apps cannot access global user storage
- Enforced at database level

### Rate Limiting

- Apps use user's existing quotas
- LLM calls count toward user limits
- Agent calls count toward user limits
- No per-app limits (yet)

---

## Implementation Roadmap

### Phase 1: Backend Infrastructure (Week 1-2)

**Goal:** Create backend endpoints for app storage and LLM access

- [ ] Create storage router (`routers/storage.py`)
- [ ] Create storage repository (`repository/storage_repository.py`)
- [ ] Create storage model (`repository/models/storage_model.py`)
- [ ] Create database migration for storage table
- [ ] Create LLM router (`routers/llm.py`)
- [ ] Implement storage endpoints (get, set, delete, keys, batch)
- [ ] Implement LLM endpoints (complete, stream)
- [ ] Add tests for storage router
- [ ] Add tests for LLM router
- [ ] Update main.py to include new routers

**Deliverables:**
- Working `/storage/*` endpoints
- Working `/llm/*` endpoints
- Tests passing
- Documentation

### Phase 2: SDK Core (Week 2-3)

**Goal:** Build TypeScript SDK package

- [ ] Create package structure (`client/webui/sam-sdk/`)
- [ ] Set up build tooling (Vite, TypeScript)
- [ ] Implement transport layer (postMessage)
- [ ] Implement auth module
- [ ] Implement API utilities (authenticatedFetch)
- [ ] Implement agents module (call, stream)
- [ ] Implement artifacts module
- [ ] Implement storage module
- [ ] Implement LLM module
- [ ] Implement tasks module
- [ ] Implement users module
- [ ] Implement UI module
- [ ] Create React hooks package
- [ ] Write unit tests
- [ ] Write API documentation

**Deliverables:**
- `@sam/sdk` npm package
- `@sam/sdk/react` hooks
- Full TypeScript types
- API documentation
- Unit tests

### Phase 3: Frontend Integration (Week 3-4)

**Goal:** Add Apps section to SAM UI

- [ ] Create `/apps` route
- [ ] Create AppsPage component
- [ ] Create AppCard component
- [ ] Create AppFrame component
- [ ] Create CreateAppDialog component
- [ ] Create useApps hook
- [ ] Create useAppCreation hook
- [ ] Add Apps to main navigation
- [ ] Implement postMessage handshake
- [ ] Implement theme propagation
- [ ] Add app versioning UI
- [ ] Add app export/import
- [ ] Write integration tests

**Deliverables:**
- Working Apps UI in SAM
- App creation flow
- App viewing in iframe
- postMessage communication
- Tests passing

### Phase 4: Claude Code Integration (Week 4-5)

**Goal:** Enable AI to build apps via claude-code

- [ ] Add @sam/sdk to docker/claude-code-node
- [ ] Create CLAUDE.md template generator
- [ ] Create coding agent instructions
- [ ] Update app workspace initialization
- [ ] Add build validation checks
- [ ] Add linting checks
- [ ] Create sample app template
- [ ] Test full app creation flow
- [ ] Document app development workflow

**Deliverables:**
- @sam/sdk pre-installed in containers
- CLAUDE.md with full SDK docs
- Working end-to-end app creation
- Sample apps

### Phase 5: Polish & Documentation (Week 5-6)

**Goal:** Production-ready feature

- [ ] Performance optimization
- [ ] Security audit
- [ ] Error handling improvements
- [ ] Loading states and feedback
- [ ] User documentation
- [ ] Developer documentation
- [ ] Example apps gallery
- [ ] Video tutorial
- [ ] Release notes

**Deliverables:**
- Production-ready feature
- Complete documentation
- Example apps
- Tutorial content

---

## API Reference

### SAM SDK API

See [SAM SDK Design](#sam-sdk-design) section above for complete API reference.

### Backend Endpoints

#### Storage API

```
GET    /storage/{app_id}/{key}           - Get value
POST   /storage/{app_id}/{key}           - Set value
DELETE /storage/{app_id}/{key}           - Delete value
GET    /storage/{app_id}/keys            - List keys
POST   /storage/{app_id}:batch-get       - Bulk get
POST   /storage/{app_id}:batch-set       - Bulk set
```

#### LLM API

```
POST   /llm/complete                     - Non-streaming completion
POST   /llm/stream                       - Streaming completion (SSE)
```

---

## Examples

### Example 1: Dashboard App

```typescript
import { SAM } from '@sam/sdk';
import { useAgent, useStorage } from '@sam/sdk/react';
import { BarChart, Bar, XAxis, YAxis } from 'recharts';

function Dashboard() {
  const [config, setConfig] = useStorage('dashboard-config', {
    refreshInterval: 60000,
    agentName: 'data-analyzer'
  });

  const { call, loading, result } = useAgent(config.agentName);

  useEffect(() => {
    const interval = setInterval(() => {
      call({ prompt: 'Get latest metrics' });
    }, config.refreshInterval);

    return () => clearInterval(interval);
  }, [config.refreshInterval]);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Sales Dashboard</h1>

      {loading && <Spinner />}

      {result?.data && (
        <BarChart width={600} height={300} data={result.data}>
          <Bar dataKey="sales" fill="#8884d8" />
          <XAxis dataKey="month" />
          <YAxis />
        </BarChart>
      )}
    </div>
  );
}
```

### Example 2: Data Export Tool

```typescript
import { SAM } from '@sam/sdk';
import { useState } from 'react';

function DataExporter() {
  const [format, setFormat] = useState<'csv' | 'json'>('csv');

  const handleExport = async () => {
    // Call agent to generate report
    const result = await SAM.agents.call('report-generator', {
      prompt: `Generate sales report in ${format} format`
    });

    // Download artifact
    if (result.artifacts?.length > 0) {
      const blob = await SAM.artifacts.download(result.artifacts[0].id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report.${format}`;
      a.click();
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Export Data</h1>

      <select value={format} onChange={(e) => setFormat(e.target.value)}>
        <option value="csv">CSV</option>
        <option value="json">JSON</option>
      </select>

      <button onClick={handleExport} className="ml-4 btn-primary">
        Generate & Download
      </button>
    </div>
  );
}
```

### Example 3: Chat Interface

```typescript
import { SAM } from '@sam/sdk';
import { useState } from 'react';

function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');

  const handleSend = async () => {
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    // Stream response from agent
    const stream = SAM.agents.stream('assistant', {
      prompt: input
    });

    let assistantMsg = { role: 'assistant', content: '' };
    setMessages(prev => [...prev, assistantMsg]);

    stream.on('text', (chunk) => {
      assistantMsg.content += chunk;
      setMessages(prev => [...prev.slice(0, -1), { ...assistantMsg }]);
    });
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-auto p-4">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role === 'user' ? 'text-right' : ''}>
            <div className="inline-block p-3 rounded bg-gray-100">
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          className="w-full p-2 border rounded"
        />
      </div>
    </div>
  );
}
```

---

## Success Criteria

- [ ] SDK can be imported and initialized in iframe app
- [ ] Authentication works seamlessly (inherited from parent)
- [ ] Agent calls work with streaming callbacks
- [ ] Artifact upload/download works
- [ ] Storage persistence works (per-app isolated)
- [ ] Theme detection and updates work
- [ ] React hooks provide idiomatic integration
- [ ] TypeScript provides full type safety
- [ ] Documentation is clear and complete
- [ ] Sample app can be generated by claude-code
- [ ] Apps run securely in sandboxed iframes
- [ ] Hot reload works during development
- [ ] Build validation prevents broken apps

---

## Appendix

### Technologies Used

**Frontend:**
- React 19
- TypeScript 5.8
- Vite 6
- Tailwind CSS 4
- Radix UI (existing SAM components)

**Backend:**
- FastAPI (Python)
- PostgreSQL (existing SAM database)
- SQLAlchemy (ORM)
- Alembic (migrations)

**Development:**
- Claude Code CLI
- Docker/Podman containers
- Git (version control)
- npm/pnpm (package management)

### References

- [Claude Code Tools Documentation](./developing/claude-code-tools-dev-guide.md)
- [SAM Chat Application](../client/webui/frontend/)
- [A2A Protocol](https://github.com/solace-ai/a2a-protocol)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Vite](https://vite.dev)

---

**Document Version:** 1.0
**Last Updated:** December 6, 2024
**Status:** Planning Complete, Ready for Implementation
