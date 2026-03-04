# Unified Logo Whitelabeling Design

**Date:** 2026-03-04
**Status:** Approved

## Context

Currently, logo whitelabeling capabilities are split across multiple components in the navigation system:

- **NavigationHeader** (used by `NavigationSidebar`) loads custom logos from the config API and caches them in localStorage, but doesn't support size variants
- **SolaceIcon** (used by `CollapsibleNavigationSidebar`) supports size variants (full/short) for responsive logo display, but is hardcoded to Solace logos only
- **CollapsibleNavigationSidebar** accepts custom header components via props but doesn't automatically integrate with the config API

This fragmentation means that custom logos cannot automatically adapt between full and short variants when the sidebar collapses/expands. This design unifies these capabilities into a single Logo component that supports both whitelabeling and size variants.

## Goals

1. Combine logo whitelabeling with size variant support
2. Create a single source of truth for logo rendering across the app
3. Maintain backwards compatibility with existing navigation components
4. Support future enhancement for variant-specific logo URLs from config API
5. Preserve localStorage caching for instant logo display

## Architecture

### Component Structure

Create a new `Logo.tsx` component in `client/webui/frontend/src/lib/components/common/` that:

- Replaces logo rendering logic from NavigationHeader and SolaceIcon
- Integrates with both NavigationSidebar and CollapsibleNavigationSidebar
- Provides a unified interface for logo display throughout the app

### Logo Selection Priority

The component follows this priority chain:

1. **Custom prop override**: If `customLogoUrl` prop is provided, use it
2. **Config API**: If `config.configLogoUrl` exists, use it
3. **Solace fallback**: Fall back to Solace SVG based on `variant` prop

### Props Interface

```typescript
interface LogoProps {
  variant?: "full" | "short";
  className?: string;
  customLogoUrl?: string; // Optional override for special cases
}
```

### State Management

- Uses `useConfigContext()` to access config API logo URL
- Maintains local `imageError` state for fallback handling
- Uses localStorage caching (key: `webui_logo_url`) for instant display
- Resets error state when logo URL changes

## Components

### New Component: Logo.tsx

**Responsibilities:**
- Load logo URL from config context
- Cache logo URL in localStorage
- Handle image loading errors
- Render custom logos or Solace SVG fallbacks
- Support full and short variants

**Implementation approach:**
- Two useEffect hooks: one for cache loading, one for config updates
- Conditional rendering based on error state
- Import Solace SVG assets for fallback

### Updated: NavigationHeader.tsx

**Changes:**
- Remove all logo loading logic (useState, useEffect hooks)
- Remove localStorage management
- Remove error handling
- Replace conditional rendering with: `<Logo variant="full" />`

**Result:** Component becomes a simple wrapper with ~50% less code

### Updated: CollapsibleNavigationSidebar.tsx

**Changes:**
- Update default header rendering from:
  ```tsx
  <SolaceIcon variant={isCollapsed ? "short" : "full"} />
  ```
  to:
  ```tsx
  <Logo variant={isCollapsed ? "short" : "full"} />
  ```

**Result:** Maintains exact same behavior but now supports whitelabeling

### Deprecated: SolaceIcon.tsx

**Changes:**
- Add deprecation comment pointing to Logo component
- Keep component for backwards compatibility elsewhere in app
- Can be removed in future refactor if no usages remain

## Data Flow

### Initial Load (Fast Path)

1. Logo component mounts
2. Reads cached logo URL from localStorage (`webui_logo_url` key)
3. If cache exists, immediately displays custom logo (no flash of default logo)
4. Config context loads from API in background

### Config Update Flow

1. Config API returns with `configLogoUrl` value
2. useEffect in Logo detects config change
3. Updates local state with new URL
4. Saves to localStorage for next page load
5. Resets `imageError` state
6. Re-renders with new logo

### Error Handling Flow

1. Custom logo img fails to load (broken URL, 404, CORS error, etc.)
2. `onError` handler sets `imageError: true`
3. Component re-renders
4. Falls back to Solace SVG for current variant

### Variant Selection

- **For Solace fallback:** Checks `variant` prop and imports appropriate SVG asset (full or short)
- **For custom logo:** Uses same image for both variants (backend can enhance this later)

### Cache Invalidation

- Cache automatically updates whenever `config.configLogoUrl` changes
- No manual invalidation needed
- localStorage errors are caught and logged (non-critical failures)

## Error Handling

### Image Load Failures

- `onError` event handler on img tag catches all load failures
- Sets `imageError` state to trigger fallback
- Gracefully switches to Solace SVG without user disruption
- No error message shown to user (silent fallback by design)

### localStorage Errors

- All localStorage operations wrapped in try-catch blocks
- Errors logged to console for debugging
- Never crashes the app
- Missing cache only impacts initial load speed (non-critical)

### Config API Failures

- If `config.configLogoUrl` is undefined/null → use Solace fallback immediately
- Config context already handles API errors upstream
- Logo component treats missing config as "use default"

### Invalid URLs

- Malformed URLs cause img load error → caught by onError handler
- Empty string URLs treated as "no custom logo" → use Solace fallback
- Relative URLs supported (relative to app base URL)

### Variant Mismatch

- If custom logo doesn't have variant support, same image shows for both full and short
- This is acceptable: many logos work well at different sizes
- Future enhancement: backend can provide variant-specific URLs (`configLogoUrlFull`, `configLogoUrlShort`)

## Testing

### Manual Testing Scenarios

1. **Custom logo with config API:**
   - Set `configLogoUrl` in backend config
   - Verify logo loads in both NavigationHeader and CollapsibleNavigationSidebar
   - Toggle sidebar collapse → verify logo switches between full/short display sizes

2. **Cache behavior:**
   - Load page with custom logo → reload page → verify instant display (no flash)
   - Clear localStorage → reload → verify logo still appears after API call

3. **Error scenarios:**
   - Set invalid logo URL → verify fallback to Solace logo
   - Set CORS-blocked URL → verify fallback to Solace logo
   - Remove `configLogoUrl` from config → verify Solace logo appears

4. **Variant rendering:**
   - Collapsed sidebar should show short Solace logo (if using fallback)
   - Expanded sidebar should show full Solace logo (if using fallback)
   - Custom logo should appear in both states (same image, scaled appropriately)

### Component Testing (Optional)

- Add Storybook story for Logo component showing all states:
  - Custom logo loaded
  - Error/fallback state
  - Both variants with Solace logos
  - Loading state (if applicable)

### Integration Testing

- Verify NavigationHeader still renders correctly
- Verify CollapsibleNavigationSidebar header still responds to `header` prop override
- Confirm no breaking changes to existing navigation behavior
- Test that custom header components can still be passed to CollapsibleNavigationSidebar

## Implementation Order

1. Create Logo component with all whitelabeling and variant logic
2. Update NavigationHeader to use Logo component
3. Update CollapsibleNavigationSidebar to use Logo component
4. Add deprecation comment to SolaceIcon
5. Manual testing of all scenarios
6. Optional: Add Storybook story

## Future Enhancements

- Backend support for variant-specific URLs (`configLogoUrlFull`, `configLogoUrlShort`)
- Theme-aware logo variants (light/dark mode)
- Logo aspect ratio constraints and sizing guidelines
- Admin UI for uploading and previewing logo variants
- Remove SolaceIcon component entirely if no other usages exist
