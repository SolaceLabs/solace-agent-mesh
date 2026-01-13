# Project Sharing with Role-Based Access Control

## Epic Context

This feature extends SAM's project-based organization to support multi-user collaboration for enterprise customers. Building on the MVP foundation that delivered individual user projects with basic file upload capabilities, this adds project sharing across users with role-based access control.

**Enterprise Context**: This is for enterprise customers only. Implementation is in `sam-agent-mesh` which exports project capabilities to the enterprise product.

**Backend Status**: POC implementation exists in PR #732 (draft, do_not_merge) with REST API endpoints defined.

## Jobs to Be Done

### Primary JTBD

**When** I want to collaborate with team members on a curated knowledge base and shared project prompts,
**I want to** share my project with specific users and control their access level,
**So that** my team can benefit from the same curated context while maintaining their own private chats.

### Supporting JTBD

1. **When** I need to give a colleague read-only access to project resources, **I want to** invite them as a Viewer, **so that** they can reference our knowledge base without making changes.

2. **When** I need team members to help curate project content, **I want to** invite them as Editors, **so that** they can add/modify files and prompts collaboratively.

3. **When** someone's role needs to change, **I want to** update their access level, **so that** permissions stay aligned with their responsibilities.

4. **When** someone leaves the team or project, **I want to** remove their access, **so that** project security is maintained.

5. **When** I'm invited to a shared project, **I want to** see it in my project list, **so that** I can access the shared knowledge and prompts.

## Key Customer Outcomes

### Business Value

- **Team Collaboration**: Sales teams can maintain shared projects with product documentation, competitive analysis, and standardized sales prompts
- **Department-Wide Sharing**: Enable knowledge sharing across teams while maintaining access control
- **Compliance**: Audit visibility and governance policies support regulatory requirements

### Technical Capability

- Projects can be shared with multiple users via email
- Three-tier role model (Owner, Editor, Viewer) with specific permissions
- Only project owner can manage collaborators (share, update roles, remove)
- Integration with SAM's existing RBAC framework
- Backend API implementation in `src/solace_agent_mesh/gateway/http_sse/routers/projects.py`

### User Experience

- Intuitive sharing interface from project detail view
- Clear visibility of who has access and their roles
- Shared projects appear in user's project list with role indication
- Users create private chats within shared projects (chats remain private)

## Role Definitions & Permissions

### Owner (Project Creator)

- **Definition**: User who created the project (stored as `project.user_id`)
- **Permissions**: Full control - view, edit, delete project, share, manage collaborators
- **UI Access**: All buttons visible (Edit, Delete, Share)
- **Backend Enforcement**: Only owner can call `/share`, `/collaborators/{user_id}` PUT/DELETE endpoints
- **RBAC Scope Required**: `project:*` or `project:share`

### Editor (Shared Collaborator)

- **Definition**: Collaborator with read/write access
- **Permissions**: View project, edit content (description, files, prompts)
- **UI Access**: Can edit fields, cannot see Share/Delete buttons
- **Cannot**: Share project, delete project, manage collaborators
- **RBAC Scope Required**: `project:read`, `project:update`

### Viewer (Shared Collaborator)

- **Definition**: Collaborator with read-only access
- **Permissions**: View project details only
- **UI Access**: All input fields disabled, no action buttons visible
- **Cannot**: Edit anything, share, delete, manage collaborators
- **RBAC Scope Required**: `project:read`

## Backend API Contract

Based on actual implementation in `src/solace_agent_mesh/gateway/http_sse/routers/projects.py`.

### POST /api/v1/projects/{projectId}/share

Share project with a user by email. Owner only.

**Request Body** (Form Data):

- `user_email` (string, required): Email address of user to invite (sent as form field, not JSON)
- `role` (string, required): Either `"editor"` or `"viewer"` (cannot assign `"owner"`)

**Important**: Backend expects form data, not JSON. Field name is `user_email` (snake_case) in the form data.

**Response**:

```json
{
    "message": "Project shared successfully",
    "user_id": "target-user-uuid"
}
```

**Notes**:

- Only the project owner can share
- Requires `project:share` scope
- Backend uses identity service to resolve email to user_id
- Returns error if user already has access

### GET /api/v1/projects/{projectId}/collaborators

Retrieve project collaborators. Any role can view.

**Response** (`ProjectCollaboratorsResponse` DTO):

```json
{
    "projectId": "844188e4-136f-451e-8fba-52943bb32959",
    "owner": {
        "userId": "john@test.com",
        "userEmail": "john@test.com",
        "userName": "John Admin",
        "role": "owner",
        "addedAt": 1768246527527,
        "addedByUserId": "john@test.com"
    },
    "collaborators": [
        {
            "userId": "sarah-456",
            "userEmail": "sarah@test.com",
            "userName": "Sarah Editor",
            "role": "editor",
            "addedAt": 1768246558952,
            "addedByUserId": "john@test.com"
        }
    ]
}
```

**Field Details** (from `CollaboratorInfo` DTO):

- `userId` (string): Unique user identifier
- `userEmail` (string | null): User's email address (may be null)
- `userName` (string | null): User's display name (may be null)
- `role` (string): "owner", "editor", or "viewer"
- `addedAt` (number): Unix timestamp in milliseconds
- `addedByUserId` (string): User ID who added this collaborator

**Notes**:

- **All field names are camelCase** (Pydantic aliased from Python snake_case)
- Response includes both `owner` and `collaborators` arrays (separate)
- `userEmail` and `userName` may be null depending on identity service data

### PUT /api/v1/projects/{projectId}/collaborators/{userId}

Update collaborator role. Owner only.

**Request Body** (Form Data):

- `role` (string, required): Either `"editor"` or `"viewer"`

**Important**: Backend expects form data, not JSON.

**Response**:

```json
{
    "message": "Role updated successfully"
}
```

**Notes**:

- `{userId}` is the collaborator's userId (e.g., "sarah-456" or email like "john@test.com")
- Only the project owner can update roles
- Requires `project:share` scope

### DELETE /api/v1/projects/{projectId}/collaborators/{userId}

Remove collaborator access. Owner only.

**Response**: `204 No Content` (empty body)

**Notes**:

- `{userId}` is the collaborator's userId to remove
- Only the project owner can remove collaborators
- Requires `project:share` scope

## Frontend Requirements

### Type Extensions Required

Extend `src/lib/types/projects.ts`:

```typescript
// Role type (only 3 roles)
export type ProjectRole = "owner" | "editor" | "viewer";

// Add to existing Project type
export interface Project {
    // ... existing fields
    role?: ProjectRole; // User's role for this project (undefined = owner for backward compat)
    collaboratorCount?: number; // Optional: count of collaborators
}

// Collaborator interface (matches backend CollaboratorInfo DTO)
export interface Collaborator {
    userId: string; // Backend: user_id (aliased to userId)
    userEmail: string | null; // Backend: user_email (aliased to userEmail)
    userName: string | null; // Backend: user_name (aliased to userName)
    role: ProjectRole; // Backend: role
    addedAt: number; // Backend: added_at (aliased to addedAt) - Unix timestamp in ms
    addedByUserId: string; // Backend: added_by_user_id (aliased to addedByUserId)
}

// API response for GET /collaborators (matches backend ProjectCollaboratorsResponse)
export interface CollaboratorsResponse {
    projectId: string; // Backend: project_id (aliased to projectId)
    owner: Collaborator;
    collaborators: Collaborator[];
}

// Share request (form data, single user)
export interface ShareProjectRequest {
    user_email: string;
    role: "editor" | "viewer"; // Cannot assign "owner"
}

// Update role request (form data)
export interface UpdateCollaboratorRequest {
    role: "editor" | "viewer";
}
```

### New Components Needed

#### ShareDialog.tsx (Single Combined Component)

**Location**: `src/lib/components/projects/ShareDialog.tsx`

**Purpose**: Combined dialog for both sharing new users AND managing existing collaborators

**Props**:

```typescript
interface ShareDialogProps {
    isOpen: boolean;
    onClose: () => void;
    projectId: string;
    isOwner: boolean; // Only owners see this dialog
}
```

**Features**:

**Top Section - Add User**:

- Email input field
- Role dropdown (Editor, Viewer only)
- "Invite" button
- Email validation
- Calls POST /share endpoint for each user
- Success/error feedback via notifications

**Bottom Section - Current Access** (Combined List):

- Owner shown first with "Owner" badge (non-editable, non-removable)
- Collaborators below with role dropdown and remove button
- Display format: Name/Email (fallback to userId if null) | Role | Actions
- Convert Unix timestamps to readable dates ("Added on...")
- Role updates call PUT /collaborators/{userId}
- Remove calls DELETE /collaborators/{userId} with confirmation
- Loading states during operations

**State Management**:

- Fetches collaborators on mount via GET /collaborators
- `collaboratorsData: CollaboratorsResponse | null`
- `email: string`, `selectedRole: 'editor' | 'viewer'`
- `isInviting`, `isLoading`, `error`

**Pattern**: Follow `CreateProjectDialog.tsx` for form + data table layout

**Storybook Story**: Create `ShareDialog.stories.tsx` with:

- Default: Owner + 3 collaborators (1 editor, 2 viewers)
- Empty: Owner only (no collaborators)

### Component Integration Points

#### ProjectDetailView.tsx Updates

**Location**: `src/lib/components/projects/ProjectDetailView.tsx`

**Changes**:

1. **Add state**: `const [shareDialogOpen, setShareDialogOpen] = useState(false)`
2. **Determine ownership**: `const isOwner = canShareProject(project)`
3. **Add "Share" button in header** (owner only):
    ```tsx
    {
        isOwner && (
            <Button key="share" onClick={() => setShareDialogOpen(true)}>
                <Share2 className="mr-2 h-4 w-4" />
                Share
            </Button>
        );
    }
    ```
4. **Render ShareDialog**:
    ```tsx
    <ShareDialog isOpen={shareDialogOpen} onClose={() => setShareDialogOpen(false)} projectId={project.id} isOwner={isOwner} />
    ```
5. **Conditional edit/delete buttons** (owner only):
    ```tsx
    {
        isOwner && <Button key="edit">Edit Details</Button>;
    }
    {
        isOwner && <DropdownMenuItem onClick={handleDelete}>Delete</DropdownMenuItem>;
    }
    ```
6. **Disable inputs for viewers**:
    ```tsx
    <Textarea
        disabled={!canEditProject(project)}
        // ... other props
    />
    ```

#### ProjectCard.tsx Updates

**Location**: `src/lib/components/projects/ProjectCard.tsx`

**Changes**:

1. **Add role badge** for shared projects:
    ```tsx
    {
        project.role && project.role !== "owner" && <Badge variant="secondary">Shared • {capitalize(project.role)}</Badge>;
    }
    ```
2. **Conditional delete action** (owner only):
    ```tsx
    {
        canDeleteProject(project) && (
            <DropdownMenuItem onClick={onDelete}>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
            </DropdownMenuItem>
        );
    }
    ```
3. **Visual indicator**: Optional icon or styling for shared projects

### API Service Extensions

#### New Service: src/lib/api/projects/sharing.ts

```typescript
import { ApiClient } from "@/lib/api/client";
import type { CollaboratorsResponse, ShareProjectRequest, UpdateCollaboratorRequest } from "@/lib/types/projects";

export const ProjectSharingService = {
    // Share project (sends form data)
    shareProject: async (projectId: string, request: ShareProjectRequest): Promise<{ message: string; user_id: string }> => {
        const formData = new FormData();
        formData.append("user_email", request.user_email);
        formData.append("role", request.role);

        return ApiClient.post(`/api/v1/projects/${projectId}/share`, formData);
    },

    // Get all collaborators (owner + collaborators list)
    getCollaborators: async (projectId: string): Promise<CollaboratorsResponse> => {
        return ApiClient.get(`/api/v1/projects/${projectId}/collaborators`);
    },

    // Update collaborator role (sends form data)
    updateCollaborator: async (projectId: string, userId: string, request: UpdateCollaboratorRequest): Promise<{ message: string }> => {
        const formData = new FormData();
        formData.append("role", request.role);

        return ApiClient.put(`/api/v1/projects/${projectId}/collaborators/${userId}`, formData);
    },

    // Remove collaborator
    removeCollaborator: async (projectId: string, userId: string): Promise<void> => {
        return ApiClient.delete(`/api/v1/projects/${projectId}/collaborators/${userId}`);
    },
};
```

**Notes**:

- **Request format**: All write operations use FormData with snake_case field names (`user_email`, `role`)
- **Response format**: All responses return JSON with camelCase field names (`userId`, `userEmail`, etc.)
- Backend uses Pydantic field aliases to convert snake_case → camelCase
- `getCollaborators` returns both owner and collaborators in separate arrays
- Use `userId` (camelCase from response) for update/remove operations
- `userId` may be email or UUID depending on identity service configuration

### State Management

**Option 1 (Recommended)**: Extend ProjectProvider

- Add sharing-related methods to `ProjectContextValue`
- Fetch collaborators when project is loaded
- Update project list when sharing changes

**Option 2**: Create separate SharingProvider (if ProjectProvider gets too large)

### Permission Utilities

Create utility: `src/lib/utils/permissions.ts`

```typescript
import type { Project, ProjectRole } from "@/lib/types/projects";

// Only owner can share projects
export const canShareProject = (project: Project): boolean => {
    return project.role === "owner" || !project.role; // No role = owner (backward compat)
};

// Owner and editor can edit content
export const canEditProject = (project: Project): boolean => {
    const role = project.role || "owner";
    return ["owner", "editor"].includes(role);
};

// Only owner can delete
export const canDeleteProject = (project: Project): boolean => {
    return project.role === "owner" || !project.role;
};
```

**Usage**: Use these throughout UI to conditionally render/disable features based on user's role.

## Acceptance Criteria

### Sharing Projects (Owner Only)

- [ ] Project owner can click "Share" button in ProjectDetailView header
- [ ] ShareDialog opens showing "Add User" form + current collaborators list
- [ ] Email input validates format before allowing invite
- [ ] Role dropdown shows only "Editor" and "Viewer" options
- [ ] POST /share API call succeeds for valid email
- [ ] Success notification displays after adding collaborator
- [ ] Collaborator list refreshes to show newly added user

### Managing Collaborators (Owner Only)

- [ ] ShareDialog displays owner at top with "Owner" badge (non-editable)
- [ ] Collaborators listed below with role dropdown and remove button
- [ ] Owner can change collaborator role via dropdown (Editor ↔ Viewer)
- [ ] PUT /collaborators/{userId} API call succeeds on role change
- [ ] Owner can click remove button to delete collaborator
- [ ] Confirmation prompt appears before removal
- [ ] DELETE /collaborators/{userId} API call succeeds
- [ ] Changes reflect immediately in collaborator list

### Viewing Shared Projects

- [ ] Shared projects appear in user's project list
- [ ] Project cards show role badge for shared projects (e.g., "Shared • Editor")
- [ ] ProjectDetailView displays appropriate UI based on role:
    - **Owner**: All controls enabled (Edit, Delete, Share)
    - **Editor**: Edit fields enabled, Share/Delete buttons hidden
    - **Viewer**: All inputs disabled, all action buttons hidden

### Permission Enforcement

- [ ] Share button only visible to project owners
- [ ] Editors cannot see or access Share button
- [ ] Viewers see fully read-only interface
- [ ] API calls respect backend RBAC (owner-only for sharing operations)

### Error Handling

- [ ] Invalid email format shows validation error
- [ ] "User already has access" error handled gracefully
- [ ] Network failures show user-friendly error messages
- [ ] Loading states display during all API operations (invite, update, remove)

## Technical Notes

### Existing Patterns to Follow

1. **Dialog Pattern**: Use Shadcn Dialog with form state management like `CreateProjectDialog.tsx`
2. **API Integration**: Use ApiClient from `src/lib/api/client.ts`
3. **Context Updates**: Follow `ProjectProvider.tsx` pattern for state management
4. **Icon Usage**: Lucide icons (e.g., `Share2`, `Users`, `UserPlus`)
5. **Styling**: Tailwind CSS classes consistent with existing components

### Dependencies

- No new package dependencies required
- Uses existing Shadcn/ui components: Dialog, Input, Select, Button, Table
- Existing ApiClient handles authentication/tokens

### Backend Dependencies

- PR #732 backend endpoints must be merged and deployed
- RBAC scopes must be configured in platform
- User email must be available in auth context

### Out of Scope (for this iteration)

- Email notifications (handled by backend)
- Invitation acceptance flow (auto-granted on backend)
- Project access requests (users are directly added)
- Bulk collaborator management
- Project templates or sharing presets

## Success Metrics

### User Experience

- Time to share a project: < 30 seconds
- Clear visual feedback for all sharing actions
- No confusion about permission levels

### Technical

- All API calls complete in < 2 seconds
- Zero console errors during sharing flow
- TypeScript strict mode compliance
- Build succeeds: `npm run build-package && npm run lint`

### Business

- Enable team collaboration on shared knowledge bases
- Audit trail of project access (backend responsibility)
- Compliance-ready access control

## References

- Backend POC: https://github.com/SolaceLabs/solace-agent-mesh/pull/732
- Epic Plan: Feature Objective document (provided)
- POC Environment: `/Users/jamie.karam/Desktop/project-sharing-poc-ws`
- Role Config: `config/project-roles.yaml`
