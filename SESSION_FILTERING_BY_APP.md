# Session Filtering by App ID - Implementation Summary

## Overview

Implemented backend support for filtering sessions by `app_id`, enabling the app editor to show only sessions relevant to the current app and implement smart session auto-selection logic.

## Backend Changes Completed ✅

### 1. Sessions Endpoint - Added app_id Query Parameter

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/sessions.py:30-49`

```python
@router.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def get_all_sessions(
    project_id: Optional[str] = Query(default=None, alias="project_id"),
    app_id: Optional[str] = Query(default=None, alias="app_id"),  # NEW
    page_number: int = Query(default=1, ge=1, alias="pageNumber"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    ...
):
    paginated_response = session_service.get_user_sessions(
        db, user_id, pagination, project_id=project_id, app_id=app_id  # NEW
    )
```

**Usage:**
- `GET /sessions?app_id=xxx` - Get all sessions for a specific app
- Supports pagination: `?app_id=xxx&pageSize=100`
- Works alongside existing `project_id` filtering

### 2. Session Service - Updated get_user_sessions

**File:** `src/solace_agent_mesh/gateway/http_sse/services/session_service.py:42-70`

```python
def get_user_sessions(
    self,
    db: DbSession,
    user_id: UserId,
    pagination: PaginationParams | None = None,
    project_id: str | None = None,
    app_id: str | None = None  # NEW
) -> PaginatedResponse[Session]:
    sessions = session_repository.find_by_user(
        db, user_id, pagination, project_id=project_id, app_id=app_id
    )
    total_count = session_repository.count_by_user(
        db, user_id, project_id=project_id, app_id=app_id
    )
```

### 3. Session Repository - Added app_id Filtering

**File:** `src/solace_agent_mesh/gateway/http_sse/repository/session_repository.py:28-70`

```python
def find_by_user(
    self, session: DBSession, user_id: UserId,
    pagination: PaginationParams | None = None,
    project_id: str | None = None,
    app_id: str | None = None  # NEW
) -> list[Session]:
    query = session.query(SessionModel).filter(
        SessionModel.user_id == user_id,
        SessionModel.deleted_at.is_(None)
    )

    if project_id is not None:
        query = query.filter(SessionModel.project_id == project_id)

    if app_id is not None:  # NEW
        query = query.filter(SessionModel.app_id == app_id)

    return [Session.model_validate(model) for model in query.all()]
```

**Same pattern applied to:**
- `count_by_user()` method
- Repository interface `ISessionRepository`

### 4. SessionResponse - Added app_id Field

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/session_responses.py:12-24`

```python
class SessionResponse(BaseTimestampResponse):
    """Response DTO for a session."""

    id: SessionId
    user_id: UserId = Field(alias="userId")
    name: str | None = None
    agent_id: str | None = Field(default=None, alias="agentId")
    project_id: str | None = Field(default=None, alias="projectId")
    project_name: str | None = Field(default=None, alias="projectName")
    app_id: str | None = Field(default=None, alias="appId")  # NEW
    has_running_background_task: bool = Field(default=False, alias="hasRunningBackgroundTask")
    created_time: int = Field(alias="createdTime")
    updated_time: int | None = Field(default=None, alias="updatedTime")
```

**Updated in routers/sessions.py:**
- `get_all_sessions()` - includes `app_id` in response
- `search_sessions()` - includes `app_id` in response

### 5. Session Entity - Added app_id Field

**File:** `src/solace_agent_mesh/gateway/http_sse/repository/entities/session.py:16-27`

```python
class Session(BaseModel):
    """Session domain entity with business logic."""

    id: SessionId
    user_id: UserId
    name: str | None = None
    agent_id: AgentId | None = None
    project_id: str | None = None
    project_name: str | None = None
    app_id: str | None = None  # NEW
    has_running_background_task: bool = False
    created_time: int
    updated_time: int | None = None
```

### 6. Session Repository save() - Includes app_id

**File:** `src/solace_agent_mesh/gateway/http_sse/repository/session_repository.py:93-115`

```python
def save(self, db_session: DBSession, session: Session) -> Session:
    if existing_model:
        update_model = UpdateSessionModel(
            name=session.name,
            agent_id=session.agent_id,
            project_id=session.project_id,
            app_id=session.app_id,  # NEW
            updated_time=session.updated_time,
        )
    else:
        create_model = CreateSessionModel(
            id=session.id,
            name=session.name,
            user_id=session.user_id,
            agent_id=session.agent_id,
            project_id=session.project_id,
            app_id=session.app_id,  # NEW
            created_time=session.created_time,
            updated_time=session.updated_time,
        )
```

## How It Works

### Backend Flow

1. **Session Creation with app_id**
   - Frontend sends message with `app_id` in metadata
   - Backend creates session with `app_id` field populated
   - Database stores session with link to app

2. **Filtering Sessions by App**
   - Frontend requests: `GET /sessions?app_id=xxx`
   - Backend filters SQL query: `WHERE app_id = 'xxx'`
   - Returns only sessions for that app

3. **Session Response**
   - Each session response includes `appId` field
   - Frontend can verify which app each session belongs to

### Frontend Integration Pattern

```typescript
// 1. Fetch sessions for an app
const response = await fetch(`${apiPrefix}/sessions?app_id=${appId}&pageSize=100`);
const { data: sessions } = await response.json();

// 2. Auto-selection logic
if (sessions.length === 0) {
    // No sessions - create new one
    const sessionId = await createNewSession(appId);
} else if (sessions.length === 1) {
    // One session - auto-select it
    await loadSession(sessions[0].id);
} else {
    // Multiple sessions - auto-select most recent (or show picker)
    await loadSession(sessions[0].id);  // First is most recent (sorted by updated_time desc)
}

// 3. Sessions sidebar automatically filtered
// The sidebar calls GET /sessions?app_id=xxx
// Only shows sessions for current app
```

## User Experience

### App Editor with 0 Sessions
1. User opens app editor
2. System queries sessions: `GET /sessions?app_id=xxx` → returns []
3. System creates new session automatically
4. User starts chatting immediately

### App Editor with 1 Session
1. User opens app editor
2. System queries sessions: `GET /sessions?app_id=xxx` → returns [session1]
3. System auto-loads session1
4. User sees previous conversation
5. Sessions sidebar shows only this session

### App Editor with Multiple Sessions
1. User opens app editor
2. System queries sessions: `GET /sessions?app_id=xxx` → returns [session1, session2, session3]
3. System auto-loads most recent (session1)
4. Sessions sidebar shows all 3 sessions for this app
5. User can switch between sessions using sidebar

## Benefits

1. **Session Isolation** - Each app's sessions are separate
2. **Auto-Selection** - Smart logic reduces user friction
3. **Multiple Conversations** - Support different aspects of same app
4. **Clean UI** - Sidebar only shows relevant sessions
5. **Scalable** - Efficient SQL filtering with index

## Database Support

- Migration already applied: `20251208_add_app_id_to_sessions.py`
- Index created: `idx_sessions_app_id` on `sessions.app_id`
- Efficient queries: `SELECT * FROM sessions WHERE app_id = ? AND deleted_at IS NULL`

## Testing

### Manual Test 1: Session Filtering
```bash
# Create session with app_id
curl -X POST http://localhost:8000/api/v1/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "message": {
        "role": "user",
        "content": "Hello",
        "metadata": {
          "agent_name": "AppAgent",
          "app_id": "test-app-123"
        }
      }
    }
  }'

# Query sessions for that app
curl http://localhost:8000/api/v1/sessions?app_id=test-app-123

# Verify only sessions for that app are returned
```

### Manual Test 2: Multiple Apps
```bash
# Create sessions for app A
# (send messages with app_id=app-a)

# Create sessions for app B
# (send messages with app_id=app-b)

# Query app A sessions
curl http://localhost:8000/api/v1/sessions?app_id=app-a
# Should only see app A sessions

# Query app B sessions
curl http://localhost:8000/api/v1/sessions?app_id=app-b
# Should only see app B sessions
```

## Next Steps for Frontend

1. **Update ChatProvider** - Implement session querying and auto-selection logic
2. **Update Sessions Sidebar** - Filter by app_id when in app editor mode
3. **Session Switcher** - Allow users to switch between sessions for same app
4. **New Session Button** - Add "New Conversation" button in app editor

## API Reference

### GET /sessions

**Query Parameters:**
- `app_id` (string, optional) - Filter sessions by app ID
- `project_id` (string, optional) - Filter sessions by project ID
- `pageNumber` (int, default=1) - Page number
- `pageSize` (int, default=20) - Items per page

**Response:**
```json
{
  "data": [
    {
      "id": "session-123",
      "userId": "user-456",
      "name": "App: Todo App",
      "agentId": "AppAgent",
      "appId": "todo-app-789",  // NEW
      "projectId": null,
      "projectName": null,
      "hasRunningBackgroundTask": false,
      "createdTime": 1702345678000,
      "updatedTime": 1702345690000
    }
  ],
  "meta": {
    "pagination": {
      "pageNumber": 1,
      "count": 3,
      "pageSize": 20,
      "nextPage": null,
      "totalPages": 1
    }
  }
}
```

## Summary

Backend is fully implemented and ready for frontend integration. The system now supports:
- ✅ Filtering sessions by app_id
- ✅ Returning app_id in session responses
- ✅ Efficient database queries with index
- ✅ One-to-many relationship (one app, many sessions)
- ✅ Compatible with existing project_id filtering

Frontend can now implement smart session management for the app editor.
