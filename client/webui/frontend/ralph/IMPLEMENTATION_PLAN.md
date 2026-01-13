# Implementation Plan - Project Sharing with RBAC

## Priority Tasks (Sorted by Priority)

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
