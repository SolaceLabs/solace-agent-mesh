# SAM Apps - User Guide

Build production-ready React applications through conversation with an AI agent.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [User Workflow](#user-workflow)
4. [Architecture](#architecture)
5. [Developer Guide](#developer-guide)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)
8. [API Reference](#api-reference)

---

## Overview

SAM Apps enables users to build React applications through natural conversation with an AI agent. The App Agent uses Claude Code tools to generate code, manage workspaces, and validate builds. Apps run in secure iframes with hot module replacement during development.

### Key Features

- 🤖 **AI-Powered Development** - Describe your app, the agent builds it
- ⚡ **Lightning Fast** - Workspace creation in 2.63s (23x faster than npm install)
- 🔥 **Hot Reload** - Instant preview with Vite HMR
- 🎨 **Modern Stack** - React 19, TypeScript 5.8, Vite 6, Tailwind CSS 3.4
- 🔒 **Secure Isolation** - Apps run in sandboxed iframes
- 📦 **Pre-built Template** - 253 packages pre-installed
- 🚀 **One-Click Deploy** - Build validation and versioning

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker or Podman
- PostgreSQL or SQLite

### 1. Build Docker Images

```bash
# Build template image
cd docker/claude-code-sam-app
podman build -t claude-code-sam-app:latest .

# Build dev server image
cd ../vite-dev-server
podman build -t vite-dev-server:latest .
```

### 2. Run Database Migration

```bash
cd src/solace_agent_mesh/gateway/http_sse
DATABASE_URL="sqlite:///./apps.db" alembic upgrade head
```

### 3. Start App Agent

```bash
sam run examples/agents/app-agent.yaml
```

### 4. Start HTTP/SSE Gateway

```bash
# Start gateway to enable API endpoints
sam run examples/gateways/http-sse-gateway.yaml
```

### 5. Build Frontend

```bash
cd client/webui/frontend
npm run build
```

Now navigate to `http://localhost:8080/#/apps` to start building apps!

---

## User Workflow

### Creating an App

1. **Navigate to Apps**
   - Click "Apps" in the navigation menu
   - You'll see a list of your apps

2. **Create New App**
   - Click "New App" button
   - Enter app name and description
   - Click "Create"

3. **Chat with App Agent**
   - The App Agent will greet you and ask clarifying questions
   - Describe your app requirements
   - The agent will propose an implementation plan

4. **Preview Your App**
   - As the agent builds features, click "Preview"
   - See live updates with hot module replacement
   - Request changes through conversation

5. **Deploy Your App**
   - When ready, click "Save & Deploy"
   - The agent validates the build
   - If errors occur, the agent fixes them automatically
   - Deployed app is available at `/apps/{app-id}/view`

### Example Conversation

```
User: I want to build a dashboard that shows agent activity metrics

Agent: I'll help you build an agent activity dashboard. Let me clarify a few things:

1. What metrics would you like to display?
   - Number of active agents
   - Message volume
   - Response times
   - Success rates

2. How should the data be visualized?
   - Real-time charts
   - Summary cards
   - Tables with filtering

3. Should the dashboard refresh automatically?

User: Show active agents count, message volume over time as a chart,
and recent messages in a table. Auto-refresh every 10 seconds.

Agent: Perfect! I'll create a dashboard with:
- Header with active agents count
- Line chart showing message volume (last 24 hours)
- Table of recent messages with filters
- Auto-refresh every 10 seconds

Building this now...
[Agent uses claude_code_execute to build the app]

Agent: Dashboard is ready! Click "Preview" to see it.
The app calls the SAM agent registry API to get live data.
```

---

## Architecture

### Agent-Centric Design

```
User → UI → Backend → App Agent → Claude Code Tools
                  ↓
            Dev Server Container (Vite)
                  ↓
            Preview in iframe
```

### Components

1. **App Agent** (`examples/agents/app-agent.yaml`)
   - Conversational AI that orchestrates app development
   - Uses claude-code tools for code generation
   - SQL-backed session for conversation continuity

2. **Backend Routers** (`src/solace_agent_mesh/gateway/http_sse/routers/`)
   - `apps.py` - App CRUD, workspace management, dev servers
   - `storage.py` - App-scoped key-value storage

3. **Docker Images**
   - `claude-code-sam-app` - Pre-built React template (260 MB)
   - `vite-dev-server` - Containerized Vite dev server (151 MB)

4. **Frontend Pages** (`client/webui/frontend/src/lib/components/pages/`)
   - `AppsPage.tsx` - List all apps
   - `AppEditorPage.tsx` - Chat + preview
   - `AppViewPage.tsx` - Deployed app viewer

5. **SAM SDK** (`packages/sam-sdk/`)
   - TypeScript library for apps to call agents, manage storage, and handle artifacts

### Data Flow

1. **Create App**:
   ```
   UI → POST /api/v1/apps → Backend creates workspace → Returns app_id
   ```

2. **Start Session**:
   ```
   UI → POST /api/v1/sessions → Creates session with App Agent
   ```

3. **Build App**:
   ```
   User message → Agent → claude_code_execute → Code written to workspace
   ```

4. **Preview**:
   ```
   UI → GET /api/v1/apps/preview/{app_id}/ → Backend starts Vite container → Proxies requests
   ```

5. **Deploy**:
   ```
   UI → POST /api/v1/apps/{app_id}/deploy → Backend runs npm run build → Creates version
   ```

---

## Developer Guide

### App Template Structure

Every app workspace starts with this structure:

```
my-app/
├── node_modules/          # 253 packages pre-installed
├── dist/                  # Build output (after deploy)
├── src/
│   ├── main.tsx          # Entry point
│   ├── App.tsx           # Root component
│   └── index.css         # Global styles (Tailwind)
├── public/               # Static assets
├── index.html            # HTML entry point
├── package.json          # Dependencies
├── CLAUDE.md             # Documentation for App Agent
├── vite.config.ts        # Vite configuration
├── tailwind.config.ts    # Tailwind configuration
└── tsconfig.json         # TypeScript configuration
```

### Using SAM SDK in Your App

```typescript
import { SAM } from '@sam/sdk';

// Wait for SDK to initialize (postMessage handshake)
await SAM.ready();

// Call other SAM agents
const result = await SAM.agents.call('data-analyzer', {
  prompt: 'Analyze this dataset...'
});

// Use app-scoped storage
await SAM.storage.set('userPreferences', { theme: 'dark' });
const prefs = await SAM.storage.get('userPreferences');

// Handle artifacts
const artifact = await SAM.artifacts.upload(file);
const blob = await SAM.artifacts.download(artifactId);

// Get current theme
const theme = SAM.ui.getTheme(); // 'light' | 'dark'
```

### Agent Discovery

Apps can call any agent in the SAM ecosystem:

```typescript
// List all available agents
const agents = await SAM.agents.list();

// Call specific agent
const result = await SAM.agents.call('document-processor', {
  prompt: 'Extract key information from this PDF'
});
```

### Styling with Tailwind

Always use Tailwind CSS for styling:

```tsx
// Layout
<div className="flex items-center justify-between p-4">

// Responsive design
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">

// Colors and spacing
<button className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg">

// Dark mode support (when SAM SDK available)
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">
```

### Code Quality Standards

1. **TypeScript** - All files must use TypeScript (.tsx, .ts)
2. **Type Safety** - Define interfaces for props and data structures
3. **Component Structure** - Use functional components with hooks
4. **Error Handling** - Always handle errors gracefully
5. **Responsive Design** - Ensure apps work on mobile and desktop
6. **Accessibility** - Use semantic HTML and ARIA labels

---

## Testing

### Run All Tests

```bash
# Backend tests (23 tests)
python3 test_apps_backend.py       # Docker + containers
python3 test_database_and_api.py   # Database migration
python3 test_api_endpoints.py      # API endpoints
python3 test_end_to_end.py         # Full E2E workflow

# Frontend tests (26 tests)
python3 test_frontend_structure.py  # Frontend validation

# Expected: All 49 tests pass ✅
```

### Test Coverage

- ✅ Container runtime detection
- ✅ Workspace creation (2.63s)
- ✅ Dev server lifecycle
- ✅ Database migrations
- ✅ Storage isolation
- ✅ Build validation
- ✅ TypeScript compilation
- ✅ Component structure
- ✅ Router configuration

---

## Troubleshooting

### Container Won't Start

```bash
# Check if image exists
podman images | grep vite-dev-server

# Check logs
podman logs sam-app-<user>-<app>

# Check network
podman network ls | grep sam-internal
```

### Workspace Creation Fails

```bash
# Verify template image
podman images | grep claude-code-sam-app

# Test extraction manually
podman run --rm -v $(pwd)/test:/output claude-code-sam-app:latest sh -c "cp -r /template /output/myapp"
```

### Build Fails

```bash
# Run build inside container
podman exec sam-app-<user>-<app> npm run build

# Check TypeScript errors
podman exec sam-app-<user>-<app> npx tsc --noEmit
```

### Health Check Failing

```bash
# Check container health
podman inspect --format='{{.State.Health.Status}}' <container-name>

# Check if Vite is running
podman exec <container-name> wget -q -O - http://localhost:5173
```

---

## API Reference

### Apps API

#### Create App
```http
POST /api/v1/apps
Content-Type: application/json

{
  "name": "My Dashboard",
  "description": "Agent activity dashboard"
}

Response: 201 Created
{
  "app_id": "my-dashboard",
  "name": "My Dashboard",
  "status": "draft",
  "workspace_id": "user123",
  "created_at": 1733598123
}
```

#### List Apps
```http
GET /api/v1/apps?pageNumber=1&pageSize=20

Response: 200 OK
{
  "data": [
    {
      "app_id": "my-dashboard",
      "name": "My Dashboard",
      "status": "deployed",
      "current_version": 3,
      "created_at": 1733598123
    }
  ],
  "meta": {
    "pagination": {
      "pageNumber": 1,
      "pageSize": 20,
      "totalPages": 1,
      "count": 1
    }
  }
}
```

#### Deploy App
```http
POST /api/v1/apps/{app_id}/deploy

Response: 200 OK
{
  "success": true,
  "version": 4,
  "build_path": "/workspaces/user123/apps-deployed/my-dashboard/v4",
  "errors": null
}
```

### Storage API

#### Set Value
```http
POST /api/v1/apps/{app_id}/storage
Content-Type: application/json

{
  "key": "preferences",
  "value": {"theme": "dark", "lang": "en"}
}

Response: 200 OK
{
  "key": "preferences",
  "value": {"theme": "dark", "lang": "en"}
}
```

#### Get Value
```http
GET /api/v1/apps/{app_id}/storage/preferences

Response: 200 OK
{
  "key": "preferences",
  "value": {"theme": "dark", "lang": "en"}
}
```

#### List Keys
```http
GET /api/v1/apps/{app_id}/storage?prefix=user.

Response: 200 OK
{
  "keys": ["user.settings", "user.profile"]
}
```

---

## Performance

### Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| Workspace Creation | 2.63s | 23x faster than npm install |
| Vite Startup | 115ms | Instant HMR |
| Production Build | 912ms | Optimized bundles |
| Container Startup | ~34s | One-time per app |

### Resource Limits

Dev server containers have resource limits:
- Memory: 512 MB
- CPU: 1 core

---

## Security

### Isolation

1. **Workspace Isolation** - Each user's apps in separate directories
2. **Container Network** - Dev servers on sam-internal network only
3. **iframe Sandboxing** - `sandbox="allow-scripts allow-same-origin"`
4. **Storage Isolation** - Storage keyed by (user_id, app_id, key)

### Best Practices

- Never expose credentials in app code
- Use SAM SDK for all API calls (provides auth)
- Validate user input
- Follow OWASP security guidelines

---

## Documentation

- **Quick Reference**: `APPS_QUICK_REFERENCE.md`
- **Test Summary**: `COMPLETE_TEST_SUMMARY.md`
- **Implementation Status**: `IMPLEMENTATION_STATUS.md`
- **Architecture**: `docs/apps-feature-architecture.md`

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review test files for examples
3. Check container logs
4. Consult architecture documentation

---

**Version**: 1.0.0
**Last Updated**: December 7, 2025
**Status**: Production Ready (95%)
