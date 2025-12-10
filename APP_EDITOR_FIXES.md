# App Editor UI and Session Management Fixes

## Problems

### Problem 1: Missing Right Side Panel UI
The AppEditorPage is a custom implementation that's missing key features:
- No Files/Workflows/Preview tabs in right panel
- No workflow status display in chat (status line)
- Duplicates functionality that already exists in ChatPage

### Problem 2: All Apps Share Same Session
All apps currently use the same session because:
- App model doesn't have `sessionId` field
- No session creation/resumption logic per app
- ChatProvider doesn't associate sessions with apps

## Solution Overview

### Solution 1: Use ChatPage for App Editor
**Remove AppEditorPage and use existing ChatPage infrastructure**

ChatPage already has everything needed:
- ✅ ChatSidePanel with Files/Workflows/App Preview tabs
- ✅ Workflow status display in chat (`LoadingMessageRow` with `statusText`)
- ✅ App editor mode support via URL parameter `?appId=xxx`
- ✅ Task monitor integration for workflow progress
- ✅ Proper resizable panels

### Solution 2: Implement Per-App Session Management
**Add sessionId to App model and create/resume sessions per app**

Each app needs its own dedicated session for:
- Conversation continuity
- Independent chat history
- Proper isolation between apps

## Implementation Steps

### Step 1: Update Backend - Add sessionId to App Model

#### A. Update Database Schema

**File:** `src/solace_agent_mesh/gateway/http_sse/alembic/versions/[NEW]_add_session_id_to_apps.py`

```python
"""Add sessionId to apps table

Revision ID: xxx
"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column('apps', sa.Column('session_id', sa.String(255), nullable=True))

def downgrade() -> None:
    op.drop_column('apps', 'session_id')
```

#### B. Update App Model

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/dto/responses/app_responses.py`

```python
class AppResponse(BaseModel):
    id: int
    app_id: str
    user_id: str
    name: str
    description: Optional[str]
    workspace_id: str
    session_id: Optional[str]  # ADD THIS
    status: str
    current_version: int
    created_time: int
    updated_time: int
    archived_time: Optional[int]
```

#### C. Update Apps Router

**File:** `src/solace_agent_mesh/gateway/http_sse/routers/apps.py`

Add endpoint to create/update session for an app:

```python
@router.post("/{app_id}/session")
async def create_or_update_app_session(
    app_id: str,
    request: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update the session ID for an app."""
    app = await app_repository.get_app(db, app_id, user_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # Update app's session_id
    app.session_id = request.session_id
    await db.commit()

    return {"session_id": request.session_id}

@router.get("/{app_id}/session")
async def get_app_session(
    app_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the session ID for an app."""
    app = await app_repository.get_app(db, app_id, user_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    return {"session_id": app.session_id}
```

### Step 2: Update Frontend Types

**File:** `client/webui/frontend/src/lib/types/app.ts`

```typescript
export interface App {
    id: string;
    appId: string;
    userId: string;
    name: string;
    description: string | null;
    workspaceId: string;
    sessionId: string | null;  // ADD THIS
    status: "draft" | "deployed" | "archived";
    currentVersion: number;
    createdTime: number;
    updatedTime: number;
    archivedTime: number | null;
}
```

### Step 3: Update Frontend - Session Management

**File:** `client/webui/frontend/src/lib/hooks/useApp.ts`

Add session management functions:

```typescript
export function useApp(appId: string): UseAppResult {
    // ... existing code ...

    const createOrLoadSession = useCallback(async (agentName: string = "AppAgent"): Promise<string | null> => {
        try {
            // Check if app already has a session
            if (app?.sessionId) {
                // Try to load existing session
                // This will be handled by ChatProvider
                return app.sessionId;
            }

            // No session yet, create one
            const response = await fetch(`/api/v1/sessions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    agentName,
                    sessionName: `App: ${app?.name}`,
                }),
            });

            if (!response.ok) {
                throw new Error("Failed to create session");
            }

            const { sessionId } = await response.json();

            // Store session ID in app
            await fetch(`/api/v1/apps/${appId}/session`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ sessionId }),
            });

            // Refetch app to get updated session_id
            await fetchApp();

            return sessionId;
        } catch (err) {
            console.error("Failed to create/load session:", err);
            return null;
        }
    }, [app, appId, fetchApp]);

    return {
        app,
        loading,
        error,
        deploy,
        deploying,
        refetch: fetchApp,
        createOrLoadSession,  // ADD THIS
    };
}
```

### Step 4: Update ChatProvider - App Session Handling

**File:** `client/webui/frontend/src/lib/providers/ChatProvider.tsx`

Update the app editor mode effect to load/create session:

```typescript
// When appEditorMode is set, load or create session for the app
useEffect(() => {
    if (!appEditorMode) return;

    const loadAppSession = async () => {
        try {
            // Fetch app to get session_id
            const response = await fetch(`${apiPrefix}/apps/${appEditorMode.appId}`);
            if (!response.ok) throw new Error("Failed to fetch app");

            const app = await response.json();

            if (app.sessionId) {
                // Resume existing session
                await loadSession(app.sessionId);
            } else {
                // Create new session for this app
                const sessionResponse = await fetch(`${apiPrefix}/sessions`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        agentName: "AppAgent",
                        sessionName: `App: ${app.name}`,
                    }),
                });

                if (!sessionResponse.ok) throw new Error("Failed to create session");

                const { sessionId } = await sessionResponse.json();

                // Store session ID in app
                await fetch(`${apiPrefix}/apps/${app.appId}/session`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ sessionId }),
                });

                // Load the new session
                await loadSession(sessionId);
            }

            // Select AppAgent
            setSelectedAgentName("AppAgent");
        } catch (err) {
            console.error("Failed to load app session:", err);
        }
    };

    loadAppSession();
}, [appEditorMode, apiPrefix, loadSession, setSelectedAgentName]);
```

### Step 5: Update Routing

**File:** `client/webui/frontend/src/main.tsx`

Change app editor route:

```typescript
// REMOVE THIS:
{
  path: "/apps/:appId/edit",
  element: <AppEditorPage />,
},

// Apps list still uses dedicated page
{
  path: "/apps",
  element: <AppsPage />,
},

// App view (deployed apps)
{
  path: "/apps/:appId/view",
  element: <AppViewPage />,
},

// App editor now uses ChatPage with URL parameter
// No route needed - navigate to /chat?appId=xxx
```

### Step 6: Update Navigation

**File:** `client/webui/frontend/src/lib/components/pages/AppsPage.tsx`

Update the "Edit" button click handler:

```typescript
const handleEdit = (appId: string) => {
    // Instead of: navigate(`/apps/${appId}/edit`);
    navigate(`/chat?appId=${appId}`);
};
```

### Step 7: Remove AppEditorPage

**File:** `client/webui/frontend/src/lib/components/pages/AppEditorPage.tsx`

Delete this file - it's no longer needed.

### Step 8: Update ChatSidePanel for App Preview

**File:** `client/webui/frontend/src/lib/components/chat/ChatSidePanel.tsx`

Ensure it has an "app-preview" tab that shows `<AppPreview appId={appId} />` when `appId` prop is provided.

If it doesn't exist, add it:

```typescript
export function ChatSidePanel({ appId, ...otherProps }) {
    // ... existing code ...

    const tabs = useMemo(() => {
        const baseTabs = [
            { id: "files", label: "Files", icon: FileText },
            { id: "workflow", label: "Workflow", icon: Workflow },
        ];

        // Add app-preview tab when in app editor mode
        if (appId) {
            baseTabs.push({
                id: "app-preview",
                label: "Preview",
                icon: Eye,
            });
        }

        return baseTabs;
    }, [appId]);

    // In tab content rendering:
    {activeTab === "app-preview" && appId && (
        <AppPreview appId={appId} />
    )}
}
```

## Testing Plan

### Test 1: UI Functionality
1. Navigate to Apps page
2. Click "Edit" on an app
3. Verify redirected to `/chat?appId=xxx`
4. Verify right side panel has tabs: Files, Workflows, Preview
5. Send message to AppAgent
6. Verify workflow status appears in chat
7. Click "View Workflow" link
8. Verify Workflow tab opens showing task progress

### Test 2: Session Isolation
1. Create App A
2. Send message "Build a todo list"
3. Note the conversation
4. Navigate back to Apps list
5. Create App B
6. Send message "Build a calculator"
7. Navigate back to App A editor
8. Verify previous conversation ("Build a todo list") is still there
9. Navigate to App B editor
10. Verify it shows calculator conversation (NOT todo list)

### Test 3: Session Persistence
1. Open App A editor
2. Send several messages
3. Close browser
4. Reopen browser
5. Navigate to App A editor
6. Verify all previous messages are still there
7. Verify can continue conversation

## Summary of Changes

### Backend Changes
- [ ] Add database migration for `session_id` column in apps table
- [ ] Update App model/response to include `sessionId`
- [ ] Add `/apps/{app_id}/session` POST endpoint (create/update)
- [ ] Add `/apps/{app_id}/session` GET endpoint (retrieve)

### Frontend Changes
- [ ] Update `App` interface to include `sessionId?: string | null`
- [ ] Update `useApp` hook to include `createOrLoadSession` function
- [ ] Update ChatProvider to load/create app-specific sessions
- [ ] Update AppsPage navigation to use `/chat?appId=xxx`
- [ ] Remove `/apps/:appId/edit` route
- [ ] Delete AppEditorPage.tsx
- [ ] Ensure ChatSidePanel has app-preview tab

### Expected Behavior After Fix
- ✅ App editor shows Files/Workflows/Preview tabs in right panel
- ✅ Workflow status displays in chat during agent responses
- ✅ Each app has its own isolated session
- ✅ Sessions persist when navigating away and back
- ✅ Sessions survive browser refresh

## Migration Path

For existing apps without session IDs:
1. Backend returns `sessionId: null` for old apps
2. Frontend detects null and creates new session on first open
3. Session ID is saved to app record
4. Subsequent opens use saved session

No data loss - old apps just get new sessions on next open.
