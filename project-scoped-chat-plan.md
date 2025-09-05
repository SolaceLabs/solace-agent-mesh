# Project-Scoped Chat Navigation - High Level Plan

## Overview
Add project context to chat sessions with minimal disruption to existing chat functionality. Users can enter a project workspace from the Projects page and work within that project's isolated chat environment.

## Key Components

### 1. Navigation Flow
- Projects page → Click project → Enter project-scoped ChatPage
- State management tracks current project context
- All existing chat functionality works within project scope

### 2. Project Context Indicator  
- Display project name below header, above chat title
- Include × button to exit project mode and return to normal chat
- Visual: `Project Name ×` as removable chip/badge

### 3. Session Filtering
- When in project mode: only show sessions belonging to current project
- New chats automatically created within current project
- Session sidebar filters by `project_id`

### 4. Exit Behavior
- Click × → clear project context state, return to normal chat mode
- Show all sessions across projects
- Project indicator disappears

## Implementation Areas
- **Frontend**: Project context state management, session filtering logic, project indicator component
- **Backend**: Project-aware session queries
- **Database**: Ensure sessions have `project_id` relationships

## Benefits
- Isolated project workspaces
- Reuses all existing chat logic
- Clean, intuitive UX with obvious exit path
- Non-disruptive to current chat experience