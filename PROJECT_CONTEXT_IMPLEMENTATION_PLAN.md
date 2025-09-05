# Project Context Implementation Plan

## Overview
Transform the current project system into a context-driven architecture where selecting a project puts the entire application into that project's scope, filtering all related data (chats, sessions, artifacts, etc.).

## Phase 1: Core Project Context Infrastructure

### 1.1 Create Project Context System
- **ProjectContext**: Manages current project state
- **ProjectProvider**: Wraps the app to provide project context
- **useProjectContext**: Hook to access project context

### 1.2 Replace useProjects Hook
- Integrate project management directly into the context
- Move project CRUD operations into the context provider
- Remove standalone `useProjects` hook

## Phase 2: Data Model Updates

### 2.1 Backend Changes
- Add `project_id` field to sessions/chats table
- Update session creation to associate with current project
- Add project filtering to session queries
- Update API endpoints to support project-scoped operations

### 2.2 Frontend Type Updates
- Add `project_id` to Session/Chat interfaces
- Update API response types to include project associations

## Phase 3: Chat Integration

### 3.1 Update ChatProvider
- Listen for project context changes
- Filter sessions by current project when loading
- Automatically associate new sessions with current project
- Clear/reload chat data when project context changes

### 3.2 Session Management
- Modify session creation to include project_id
- Update session switching to respect project context
- Filter session history by project

## Phase 4: UI/UX Updates

### 4.1 Projects Page Behavior
- **No Project Context**: Show all projects grid (current behavior)
- **In Project Context**: Show project details view with project-specific actions

### 4.2 Navigation Updates
- Add project context indicator in header/navigation
- Add "Exit Project" functionality
- Show current project name in breadcrumbs

### 4.3 Chat Page Integration
- Only show sessions from current project
- Display project context in chat interface
- Handle empty states when no sessions exist in project

## Phase 5: Advanced Features

### 5.1 Project-Scoped Artifacts
- Filter artifacts by project context
- Associate uploaded files with current project
- Project-specific file management

### 5.2 Cross-Project Operations
- Allow moving sessions between projects
- Project templates and copying
- Bulk operations within project scope

## Implementation Flow

```
1. Create ProjectContext + Provider + Hook
2. Update ProjectsPage to use context instead of useProjects
3. Add project selection handler that sets context
4. Update backend to support project_id in sessions
5. Modify ChatProvider to listen for project context changes
6. Update session creation/loading to respect project context
7. Add UI indicators for current project context
8. Test end-to-end flow: select project → see filtered chats
```

## Key Integration Points

### ChatProvider Integration
- Listen to `project-context-changed` events
- Reload sessions when project changes
- Pass project_id when creating new sessions
- Clear current session if it doesn't belong to new project

### Navigation Integration
- Show current project in header
- Provide "Exit Project" button
- Update page titles to include project context

### API Integration
- Add `?project_id=xxx` query parameters
- Update session creation endpoints
- Modify artifact endpoints for project scoping

This approach ensures that once a user selects a project, the entire application operates within that project's scope, providing a focused and organized experience.
