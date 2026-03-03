# Navigation Sidebar Feature Flag

## Overview

The navigation sidebar now supports switching between the new collapsible navigation (from `amir/feat-nav` branch) and the legacy simple navigation (from `main` branch) using a feature flag.

## Feature Flag

**Flag Name:** `newNavigation`

**Location:** Backend configuration under `frontend_feature_enablement`

**Default Value:** `false` (uses legacy navigation)

## Usage

### Enabling New Navigation (Default)

To use the new collapsible navigation sidebar with recent chats, user account menu, and expandable sections:

```yaml
# In your backend configuration
frontend_feature_enablement:
    newNavigation: true # or omit this line (defaults to true)
```

### Enabling Legacy Navigation

To use the old simple icon-based navigation from the main branch:

```yaml
# In your backend configuration
frontend_feature_enablement:
    newNavigation: false
```

## Differences Between Navigation Versions

### New Navigation (newNavigation: true)

- **Collapsible sidebar** - Can expand/collapse with chevron button
- **Recent chats list** - Shows recent chat sessions in the sidebar
- **User account dropdown** - Full account menu with settings, theme toggle, etc.
- **Expandable sections** - Assets and System Management have submenu items
- **Notifications section** - Dedicated notifications button
- **Persistent state** - Collapse/expand state saved to localStorage
- **Width:** 64px (collapsed) / 256px (expanded)

### Legacy Navigation (newNavigation: false)

- **Fixed width sidebar** - Always 100px wide, no collapse/expand
- **Icon-only navigation** - Simple icon buttons for main sections
- **No recent chats** - Must navigate to /chats to see chat history
- **Basic navigation** - Direct navigation to: Agent Mesh, Chat, Projects, Prompts, Artifacts
- **Simpler UI** - Minimal design matching original main branch

## Implementation Details

### Components

1. **NavigationSidebarWrapper** - Main wrapper component that checks the feature flag
2. **NavigationSidebar** - New collapsible navigation (current branch)
3. **LegacyNavigationSidebar** - Old simple navigation (from main branch)

### File Structure

```
client/webui/frontend/src/lib/components/navigation/
├── NavigationSidebar.tsx           # New navigation implementation
├── LegacyNavigationSidebar.tsx     # Legacy navigation implementation
├── NavigationSidebarWrapper.tsx    # Feature flag wrapper
├── NavigationHeader.tsx            # Shared header component
├── NavigationList.tsx              # Shared list component (legacy)
├── NavigationButton.tsx            # Shared button component (legacy)
└── index.ts                        # Exports
```

### Backend Configuration

The feature flag is read from the backend `/api/v1/config` endpoint:

```json
{
    "frontend_feature_enablement": {
        "newNavigation": true
    }
}
```

## Testing

### Test New Navigation

1. Set `newNavigation: true` in backend config (or omit it)
2. Restart backend
3. Refresh frontend
4. Verify collapsible sidebar with recent chats appears

### Test Legacy Navigation

1. Set `newNavigation: false` in backend config
2. Restart backend
3. Refresh frontend
4. Verify simple 100px icon-based sidebar appears

## Migration Notes

- The feature flag defaults to `true`, so existing deployments will use the new navigation
- To maintain the old navigation behavior, explicitly set `newNavigation: false`
- Both navigation versions support the same core features (Projects, Agents, Prompts, Artifacts)
- Enterprise features (System Management, additional nav items) only work with new navigation

## Backwards Compatibility

The implementation maintains full backwards compatibility:

- Existing code importing `NavigationSidebar` will automatically get the wrapper
- The wrapper handles all feature flag logic internally
- No changes needed to existing code that uses the navigation sidebar
