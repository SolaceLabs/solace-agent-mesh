# SAM Apps - Quick Reference Guide

Quick commands and information for working with the SAM Apps feature.

---

## Running Tests

```bash
# All tests (run in order)
python test_apps_backend.py        # Backend + Docker (6 tests)
python test_database_and_api.py    # Database migration (4 tests)
python test_api_endpoints.py       # API endpoints (4 tests)
python test_end_to_end.py          # Full E2E (8 steps)
python test_frontend_structure.py  # Frontend validation (26 tests)
```

**Expected Results**: All 49 tests should pass ✅

---

## Docker Images

### Build Images
```bash
# Build template image
cd docker/claude-code-sam-app
podman build -t claude-code-sam-app:latest .

# Build dev server image
cd docker/vite-dev-server
podman build -t vite-dev-server:latest .
```

### List Images
```bash
podman images | grep -E "(claude-code-sam-app|vite-dev-server)"
```

### Expected Output
```
localhost/vite-dev-server          latest   3dc25ef6cead   151 MB
localhost/claude-code-sam-app      latest   eb77885aed6a   260 MB
```

---

## Running the App Agent

```bash
# Start App Agent
python cli/main.py run examples/agents/app-agent.yaml

# Check logs
tail -f app-agent.log
```

**Expected**: Agent registers and publishes agent card every 10 seconds

---

## Database Migration

```bash
cd src/solace_agent_mesh/gateway/http_sse

# Run migration
DATABASE_URL="sqlite:///./apps.db" alembic upgrade head

# Check current version
DATABASE_URL="sqlite:///./apps.db" alembic current

# Rollback one version
DATABASE_URL="sqlite:///./apps.db" alembic downgrade -1
```

---

## Container Management

### View Running Containers
```bash
podman ps
```

### View All Containers (including stopped)
```bash
podman ps -a
```

### View Container Logs
```bash
podman logs <container-name>
podman logs -f <container-name>  # Follow logs
```

### Stop and Remove Container
```bash
podman stop sam-app-<user>-<app-id>
podman rm sam-app-<user>-<app-id>
```

### Container Naming Pattern
```
sam-app-{user_id}-{app_id}

Example: sam-app-test-user-my-dashboard
```

---

## Network Management

### Create sam-internal Network
```bash
podman network create sam-internal
```

### List Networks
```bash
podman network ls
```

### Inspect Network
```bash
podman network inspect sam-internal
```

---

## Workspace Structure

### Default Location
```
~/.claude-workspaces/{user_id}/apps/{app_id}/
```

### Or Custom (via WORKSPACE_BASE env var)
```bash
export WORKSPACE_BASE="/custom/path"
```

### Workspace Contents
```
my-app/
├── node_modules/          # 253 packages pre-installed
├── dist/                  # Build output
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   └── index.css
├── public/
├── package.json           # Customized with app name
├── CLAUDE.md              # Documentation for App Agent
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

---

## API Endpoints

### Apps Router (`/api/v1/apps`)

```bash
# List apps
GET /apps?pageNumber=1&pageSize=20

# Create app
POST /apps
{
  "name": "My App",
  "description": "Optional description"
}

# Get app
GET /apps/{app_id}

# Update app
PATCH /apps/{app_id}
{
  "name": "Updated Name",
  "description": "Updated description"
}

# Deploy app
POST /apps/{app_id}/deploy

# Archive app
DELETE /apps/{app_id}

# Start dev server
POST /apps/dev-server?workspaceId={workspace_id}

# Preview (HTTP proxy)
GET /apps/preview/{app_id}/{path}

# HMR (WebSocket proxy)
WS /apps/preview/{app_id}/__vite_hmr
```

### Storage Router (`/api/v1/apps/{app_id}/storage`)

```bash
# Set value
POST /apps/{app_id}/storage
{
  "key": "preferences",
  "value": {"theme": "dark"}
}

# Get value
GET /apps/{app_id}/storage/{key}

# List keys
GET /apps/{app_id}/storage?prefix=user.

# Delete key
DELETE /apps/{app_id}/storage/{key}

# Clear all
DELETE /apps/{app_id}/storage
```

---

## Common Tasks

### Create a Test Workspace
```python
from solace_agent_mesh.gateway.http_sse.routers.apps import create_workspace_from_template
from pathlib import Path

await create_workspace_from_template(
    workspace_path=Path("/path/to/workspace"),
    app_id="my-app",
    app_name="My Application"
)
```

### Start a Dev Server
```python
from solace_agent_mesh.gateway.http_sse.routers.apps import start_dev_server

internal_url = start_dev_server(
    app_id="my-app",
    workspace_path="/path/to/workspace",
    user_id="user123"
)
# Returns: http://sam-app-user123-my-app:5173
```

### Stop a Dev Server
```python
from solace_agent_mesh.gateway.http_sse.routers.apps import stop_dev_server

stop_dev_server(app_id="my-app", user_id="user123")
```

---

## Performance Expectations

- **Workspace Creation**: ~2-3 seconds
- **Dev Server Startup**: ~30-40 seconds (one-time per app)
- **Vite Ready**: ~100-150ms
- **Production Build**: ~900ms-1.5s
- **Container Cleanup**: <1 second

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

## File Locations

### Backend
- **Apps Router**: `src/solace_agent_mesh/gateway/http_sse/routers/apps.py`
- **Storage Router**: `src/solace_agent_mesh/gateway/http_sse/routers/storage.py`
- **DTOs**: `src/solace_agent_mesh/gateway/http_sse/routers/dto/`
- **Migration**: `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20251207_add_apps_tables.py`

### Docker
- **Template Image**: `docker/claude-code-sam-app/`
- **Dev Server**: `docker/vite-dev-server/`

### Frontend
- **Pages**: `client/webui/frontend/src/lib/components/pages/Apps*.tsx`
- **Components**: `client/webui/frontend/src/lib/components/apps/`
- **Hooks**: `client/webui/frontend/src/lib/hooks/useApp*.ts`
- **Router**: `client/webui/frontend/src/router.tsx`

### SDK
- **Package**: `packages/sam-sdk/`
- **Types**: `packages/sam-sdk/src/types.ts`
- **Client**: `packages/sam-sdk/src/client.ts`

### Config
- **App Agent**: `examples/agents/app-agent.yaml`

### Tests
- `test_apps_backend.py`
- `test_database_and_api.py`
- `test_api_endpoints.py`
- `test_end_to_end.py`

---

## Environment Variables

```bash
# Workspace base directory
export WORKSPACE_BASE="/custom/path"

# Database URL (for migrations)
export DATABASE_URL="sqlite:///./apps.db"
# or
export DATABASE_URL="postgresql://user:pass@localhost/samdb"

# App Agent database
export APP_AGENT_DATABASE_URL="sqlite:///./app-agent.db"

# Anthropic API key (for claude-code tools)
export ANTHROPIC_API_KEY="your-key-here"

# Namespace (for A2A protocol)
export NAMESPACE="your-namespace"
```

---

## Next Steps

1. **Start HTTP/SSE Gateway** - For proxy endpoint testing
2. **Build Frontend** - Compile React UI with new pages
3. **Integration Test** - Test full stack with live server
4. **User Acceptance** - Manual workflow validation

---

## Test Results

**49/49 tests passed** ✅ (100% success rate)

- Backend: 23/23 tests
- Frontend: 26/26 tests

See detailed reports:
- `COMPLETE_TEST_SUMMARY.md` - Full test summary (all 49 tests)
- `FINAL_TEST_REPORT.md` - Comprehensive backend test results
- `APPS_BACKEND_TEST_RESULTS.md` - Backend integration details
- `SAM_APPS_COMPLETE_TEST_SUMMARY.md` - Previous summary
