# Implementation Plan - Project Sharing with RBAC (COMPLETED)

## Priority Tasks (Sorted by Priority)

- All planned tasks are done.

## Completed Tasks

- [x] **Final Integration & Verification**: Run full build and lint check.

- [x] **Detail View Update**: Update `src/lib/components/projects/ProjectDetailView.tsx` with sharing controls and permission checks.
    - Updated `ProjectDetailView` to use `ShareDialog` and permission utils.
    - Updated `SystemPromptSection` and `DefaultAgentSection` to support `readOnly` prop.
    - Ensured only owners can share/delete, and only owners/editors can edit.

## Notes

- **API Contract**: The backend requires `FormData` for all write operations (share, update role) with snake_case fields (`user_email`, `role`), but returns JSON with camelCase fields. The client must handle this mapping.
- **Permissions**:
    - **Owner**: Full access (share, edit, delete).
    - **Editor**: Can edit content, CANNOT share or delete.
    - **Viewer**: Read-only access.
- **State Management**: Using `ProjectProvider` to manage sharing state ensures that changes (like adding a collaborator) can trigger necessary refreshes of the project list if needed, though most sharing state is local to the dialog.
- **Component Reuse**: Reuse `MessageBanner` for errors and Shadcn UI components (Dialog, Button, Input, Select, Table) to maintain consistency.
