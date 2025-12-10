# Backend Changes for App-Session Architecture

## Summary

Successfully implemented the correct architecture for app-session relationship:
- **CORRECT**: `app_id` in sessions table (one app → many sessions)
- **REJECTED**: `session_id` in apps table (one app → one session)

This allows multiple chat sessions per app, supporting future use cases where users can have multiple conversations about different aspects of the same app.

## Completed Backend Changes

### 1. Database Migration ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/alembic/versions/20251208_add_app_id_to_sessions.py`

```python
def upgrade() -> None:
    # Add app_id column to sessions table (nullable, no foreign key constraint)
    op.add_column('sessions', sa.Column('app_id', sa.String(255), nullable=True))
    op.create_index('idx_sessions_app_id', 'sessions', ['app_id'])

def downgrade() -> None:
    # Remove index and column
    op.drop_index('idx_sessions_app_id', 'sessions')
    op.drop_column('sessions', 'app_id')
```

**Status:** Created and ready to apply
**Command:** `alembic upgrade head` (run from `src/solace_agent_mesh/gateway/http_sse/`)

### 2. SessionModel Updates ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/repository/models/session_model.py`

Added `app_id` field to:
- `SessionModel` (SQLAlchemy model) - line 23
- `CreateSessionModel` (Pydantic model) - line 45
- `UpdateSessionModel` (Pydantic model) - line 55

Follows same pattern as `project_id` (nullable, no FK constraint).

### 3. App Response Model Cleanup ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/app_responses.py`

**Removed:** `session_id` field from `AppResponse` (line 16)

This field was incorrectly added in the initial implementation. Apps don't need to know about sessions - sessions know about apps.

### 4. App Request Model Cleanup ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/dto/requests/app_requests.py`

**Removed:** `UpdateAppSessionRequest` class (lines 32-37)

No longer needed since apps don't store session IDs.

### 5. Apps Router Cleanup ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/apps.py`

**Changes:**
- Removed `UpdateAppSessionRequest` import (line 45)
- Removed `session_id` from `list_apps` response (line 465)
- Removed `session_id` from `get_app` response (lines 515, 557)
- Removed session endpoints:
  - `POST /apps/{app_id}/session` (lines 584-614)
  - `GET /apps/{app_id}/session` (lines 617-641)

### 6. Session Service Updates ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/services/session_service.py`

**Method:** `create_session()` (line 153)

**Added parameter:**
```python
def create_session(
    self,
    db: DbSession,
    user_id: UserId,
    name: str | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    app_id: str | None = None,  # NEW
) -> Optional[Session]:
```

**Updated session creation:**
```python
session = Session(
    id=session_id,
    user_id=user_id,
    name=name,
    agent_id=agent_id,
    project_id=project_id,
    app_id=app_id,  # NEW
    created_time=now_ms,
    updated_time=now_ms,
)
```

### 7. Message Handler Updates ✅

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/tasks.py`

**Changes:**

**Extract app_id from metadata (line 342):**
```python
agent_name = None
project_id = None
app_id = None  # NEW
if payload.params and payload.params.message and payload.params.message.metadata:
    agent_name = payload.params.message.metadata.get("agent_name")
    project_id = payload.params.message.metadata.get("project_id")
    app_id = payload.params.message.metadata.get("app_id")  # NEW
```

**Pass app_id to session creation (line 435):**
```python
session_service.create_session(
    db=db,
    user_id=user_id,
    agent_id=agent_name,
    session_id=session_id,
    project_id=project_id,
    app_id=app_id,  # NEW
)
```

### 8. Frontend Type Updates ✅

**File:** `client/webui/frontend/src/lib/types/app.ts`

**Removed:** `sessionId` field from `App` interface (line 12)

```typescript
export interface App {
    id: string;
    appId: string;
    userId: string;
    name: string;
    description: string | null;
    workspaceId: string;
    // sessionId: string | null;  // REMOVED
    status: "draft" | "deployed" | "archived";
    currentVersion: number;
    createdTime: number;
    updatedTime: number;
    archivedTime: number | null;
}
```

## How It Works

### Session Creation Flow

1. **Frontend creates app**
   - POST `/api/v1/apps` → returns `app_id`

2. **Frontend navigates to app editor**
   - URL: `/chat?appId=xxx`
   - ChatProvider detects `appId` parameter

3. **Frontend sends first message**
   - Includes `app_id` in message metadata
   - Example:
     ```json
     {
       "message": {
         "role": "user",
         "content": "Build a todo app",
         "metadata": {
           "agent_name": "AppAgent",
           "app_id": "todo-app-3be0"
         }
       }
     }
     ```

4. **Backend creates session**
   - Extracts `app_id` from message metadata
   - Calls `session_service.create_session(app_id=app_id)`
   - Session stored with `app_id` field populated

5. **Claude Code tools use app_id**
   - Extract `app_id` from `tool_context.state.a2a_context`
   - Override workspace_id with app_id
   - Build files in correct workspace: `/workspaces/{user_id}/apps/{app_id}`

### Multiple Sessions Per App (Future)

The architecture now supports:
- User creates app "Dashboard Builder"
- **Session 1**: "Design the UI layout" → focused on components
- **Session 2**: "Add analytics integration" → focused on API calls
- **Session 3**: "Optimize performance" → focused on refactoring

Each session is isolated but works on the same app workspace.

## Testing Checklist

### After Running Migration

1. ✅ Run migration: `alembic upgrade head`
2. ✅ Restart backend server
3. ✅ Verify sessions table has `app_id` column and index

### Manual Testing

1. **Create new app**
   - Go to `/apps`, click "New App"
   - Create app named "Test App"
   - Verify redirects to `/chat?appId=xxx`

2. **Session creation**
   - Send first message to AppAgent
   - Check database: `SELECT * FROM sessions WHERE app_id IS NOT NULL`
   - Verify session has correct `app_id`

3. **Workspace isolation**
   - Send message: "Create a file called test.txt"
   - Verify file created in `/workspaces/{user_id}/apps/{app_id}/test.txt`
   - NOT in `/workspaces/default_user/` or wrong app_id

4. **Multiple sessions (future)**
   - Create session 1, send messages
   - Create session 2 for same app
   - Verify both sessions work on same workspace
   - Verify conversations are isolated

## Migration Plan

1. **Apply database migration**
   ```bash
   cd src/solace_agent_mesh/gateway/http_sse
   alembic upgrade head
   ```

2. **Restart backend**
   ```bash
   # Restart SAM backend service
   ```

3. **Frontend changes** (see FRONTEND_APP_EDITOR_IMPLEMENTATION.md)
   - Update session creation to include `app_id` in metadata
   - Update ChatProvider to handle `?appId=xxx` parameter
   - Update AppsPage navigation

4. **Test end-to-end**
   - Create new app
   - Send messages to AppAgent
   - Verify workspace isolation
   - Verify session persistence

## Rollback Plan

If issues arise:

1. **Database rollback**
   ```bash
   cd src/solace_agent_mesh/gateway/http_sse
   alembic downgrade -1
   ```

2. **Revert code changes**
   ```bash
   git revert <commit-hash>
   ```

## Notes

- Migration is non-destructive (adds column, doesn't modify existing data)
- Existing sessions will have `app_id = NULL` (backward compatible)
- No foreign key constraint on `app_id` (similar to `project_id` pattern)
- Index on `app_id` for efficient queries when filtering sessions by app
