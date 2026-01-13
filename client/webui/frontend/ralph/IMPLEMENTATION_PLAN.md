# Implementation Plan - Project Sharing with RBAC

## Priority Tasks (Sorted by Priority)

- [ ] **Type Definitions**: Update `src/lib/types/projects.ts` with `ProjectRole`, `Collaborator` interfaces, and extend `Project` type with `role` and `collaboratorCount`.
    - **Why**: Foundation for all other tasks; ensures type safety across the application.
    - **Acceptance Criteria**: Types match backend API contract (snake_case vs camelCase mapping handled by client/service layer).

- [ ] **Permission Utilities**: Create `src/lib/utils/permissions.ts` with helper functions (`canShareProject`, `canEditProject`, `canDeleteProject`).
    - **Why**: Centralizes logic for UI permission checks; prevents duplicated logic.
    - **Acceptance Criteria**: Unit tests pass for all role combinations (owner, editor, viewer, undefined).

- [ ] **API Service Layer**: Create `src/lib/api/projects/sharing.ts` with methods for `shareProject`, `getCollaborators`, `updateCollaborator`, and `removeCollaborator`.
    - **Why**: Encapsulates API calls; handles FormData conversion required by backend.
    - **Acceptance Criteria**: Methods correctly handle FormData for write operations and return typed responses.

- [ ] **Provider Extension**: Extend `ProjectProvider.tsx` to expose sharing capabilities via context.
    - **Why**: Makes sharing functionality available to components; handles global state updates (e.g., refreshing project list).
    - **Acceptance Criteria**: `useProjectContext` exposes new sharing methods; error handling follows existing provider patterns.

- [ ] **Share Dialog Component**: Create `src/lib/components/projects/ShareDialog.tsx`.
    - **Why**: Main interface for managing project access.
    - **Acceptance Criteria**:
        - Top section allows inviting by email (validated) with role.
        - Bottom section lists collaborators with "Owner" badge for creator.
        - Updating role and removing collaborators works for owner.
        - Loading/error states are handled correctly.

- [ ] **Storybook for ShareDialog**: Create `src/stories/ShareDialog.stories.tsx`.
    - **Why**: Validates UI states (empty, populated, loading) without backend dependency.
    - **Acceptance Criteria**: Stories exist for "Default" (owner view) and "Loading" states.

- [ ] **Project Card Update**: Update `src/lib/components/projects/ProjectCard.tsx` to reflect shared state.
    - **Why**: Visual indication of shared projects in the list view.
    - **Acceptance Criteria**:
        - Shows role badge (e.g., "Shared • Editor") for non-owners.
        - "Delete" option hidden for non-owners.

- [ ] **Detail View Update**: Update `src/lib/components/projects/ProjectDetailView.tsx` with sharing controls and permission checks.
    - **Why**: Entry point for sharing; enforces permissions on project editing.
    - **Acceptance Criteria**:
        - "Share" button visible only to owners.
        - Inputs disabled for "Viewer" role.
        - "Delete" button hidden for non-owners.
        - Edit controls hidden/disabled for Viewers.

- [ ] **Final Integration & Verification**: Run full build and lint check.
    - **Why**: Ensures no regressions or type errors.
    - **Acceptance Criteria**: `npm run build-package && npm run lint` succeeds.

## Notes

- **API Contract**: The backend requires `FormData` for all write operations (share, update role) with snake_case fields (`user_email`, `role`), but returns JSON with camelCase fields. The client must handle this mapping.
- **Permissions**:
    - **Owner**: Full access (share, edit, delete).
    - **Editor**: Can edit content, CANNOT share or delete.
    - **Viewer**: Read-only access.
- **State Management**: Using `ProjectProvider` to manage sharing state ensures that changes (like adding a collaborator) can trigger necessary refreshes of the project list if needed, though most sharing state is local to the dialog.
- **Component Reuse**: Reuse `MessageBanner` for errors and Shadcn UI components (Dialog, Button, Input, Select, Table) to maintain consistency.
