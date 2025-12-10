# Frontend App Editor Implementation - Remaining Changes

## Completed - Backend

✅ Database migration: `20251208_add_app_id_to_sessions.py`
✅ SessionModel updated with `app_id` field
✅ Removed incorrect session endpoints from apps.py
✅ Removed `sessionId` from App interface and response models

## Architecture Decision

**CORRECT**: `app_id` in sessions table (one app → many sessions)
- Supports multiple conversations per app
- Future-proof for advanced workflows
- Sessions filtered by app_id in app editor context

**REJECTED**: `session_id` in apps table (one app → one session)
- Too restrictive
- Not scalable

## Remaining Frontend Changes

### Change 1: Update Session Creation - Include app_id

**File:** `client/webui/frontend/src/lib/providers/ChatProvider.tsx` or wherever sessions are created

When creating a session in app editor context, include the `app_id` field:

```typescript
// Effect to handle app editor mode - create session with app_id
useEffect(() => {
    if (!appEditorMode) return;

    const loadAppSession = async () => {
        try {
            const log_prefix = "ChatProvider.loadAppSession:";
            console.log(`${log_prefix} Loading sessions for app ${appEditorMode.appId}`);

            // Query existing sessions for this app
            // TODO: Add endpoint to get sessions by app_id
            // For now, create a new session with app_id

            // Create new session for this app
            console.log(`${log_prefix} Creating new session for app`);
            const sessionResponse = await fetch(`${apiPrefix}/sessions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    agentName: "AppAgent",
                    sessionName: `App: ${appEditorMode.appName || appEditorMode.appId}`,
                    appId: appEditorMode.appId,  // IMPORTANT: Include app_id
                }),
            });

            if (!sessionResponse.ok) {
                throw new Error("Failed to create session");
            }

            const { sessionId } = await sessionResponse.json();
            console.log(`${log_prefix} Created session ${sessionId} for app ${appEditorMode.appId}`);

            // Load the new session
            await loadSession(sessionId);

            // Select AppAgent
            setSelectedAgentName("AppAgent");
        } catch (err) {
            console.error("Failed to load app session:", err);
            addNotification({
                title: "Failed to load app session",
                description: err instanceof Error ? err.message : "Unknown error",
                variant: "destructive",
            });
        }
    };

    loadAppSession();
}, [appEditorMode, apiPrefix, setSelectedAgentName, addNotification]);
```

**Key Changes:**
- Include `appId: appEditorMode.appId` in session creation request body
- This creates a session linked to the app (one-to-many relationship)
- Future enhancement: Query existing sessions by app_id and let user choose to resume or create new

### Change 2: Update AppsPage Navigation

**File:** `client/webui/frontend/src/lib/components/pages/AppsPage.tsx`

Find the button or link that navigates to app editor and change it from:
```typescript
onClick={() => navigate(`/apps/${app.appId}/edit`)}
```

To:
```typescript
onClick={() => navigate(`/chat?appId=${app.appId}`)}
```

### Change 3: Remove AppEditorPage Route

**File:** `client/webui/frontend/src/main.tsx`

Remove this route:
```typescript
{
  path: "/apps/:appId/edit",
  element: <AppEditorPage />,
},
```

Also remove the import:
```typescript
import { AppEditorPage } from "@/lib/components/pages/AppEditorPage";
```

### Change 4: Delete AppEditorPage Component

**File:** `client/webui/frontend/src/lib/components/pages/AppEditorPage.tsx`

DELETE THIS FILE - It's no longer needed.

### Change 5: Ensure ChatSidePanel Has App Preview Tab

**File:** `client/webui/frontend/src/lib/components/chat/ChatSidePanel.tsx`

Verify it has an app-preview tab. If not present, add logic similar to this:

```typescript
const tabs = useMemo(() => {
    const baseTabs = [
        { id: "files", label: "Files", icon: FileText },
        { id: "workflow", label: "Workflow", icon: Workflow },
    ];

    // Add app-preview tab when in app editor mode (appId prop provided)
    if (props.appId) {
        baseTabs.push({
            id: "app-preview",
            label: "Preview",
            icon: Eye,  // You'll need to import Eye from lucide-react
        });
    }

    return baseTabs;
}, [props.appId]);

// In tab content rendering section:
{activeTab === "app-preview" && props.appId && (
    <AppPreview appId={props.appId} />
)}
```

## Testing Checklist

After making these changes:

### Test 1: Create New App
1. Go to /apps
2. Click "New App"
3. Fill in name/description
4. Click "Create"
5. Should redirect to `/chat?appId=xxx`
6. Verify right panel has Files, Workflows, Preview tabs
7. Send a message to AppAgent
8. Verify message appears in chat
9. Verify workflow status shows in chat
10. Verify can click "View Workflow" to open Workflow tab

### Test 2: Session Isolation
1. Create App A
2. Send message "Build a todo app"
3. Note the conversation
4. Navigate back to /apps
5. Create App B
6. Send message "Build a calculator"
7. Navigate to App A (click Edit)
8. Verify previous conversation ("todo app") is there
9. Navigate to App B (click Edit)
10. Verify it shows calculator conversation (NOT todo)

### Test 3: Session Persistence
1. Open App A editor
2. Send several messages
3. Refresh browser
4. Navigate to App A editor again
5. Verify all previous messages still there

### Test 4: Workflow Status Display
1. Open any app editor
2. Send a coding request to AppAgent
3. Verify status text appears in chat (e.g., "Coding tool: Reading files...")
4. Verify "View Workflow" link appears
5. Click "View Workflow"
6. Verify Workflow tab opens and shows task progress

## Manual Steps After Code Changes

1. Run database migration:
   ```bash
   cd src/solace_agent_mesh/gateway/http_sse
   alembic upgrade head
   ```

2. Restart backend server

3. Rebuild frontend:
   ```bash
   cd client/webui/frontend
   npm run build
   ```

4. Clear browser cache and reload

5. Test all scenarios above

## Expected Behavior

- ✅ App editor uses ChatPage (same UI as normal chat)
- ✅ Right panel shows Files/Workflows/Preview tabs
- ✅ Workflow status displays in chat during agent responses
- ✅ Each app has its own isolated session
- ✅ Sessions persist when navigating away and back
- ✅ Sessions survive browser refresh
- ✅ No duplicate AppEditorPage code
