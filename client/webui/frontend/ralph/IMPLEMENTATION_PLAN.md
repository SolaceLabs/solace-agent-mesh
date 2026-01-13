# Implementation Plan

## Priority Tasks (Sorted by Priority)

### High Priority - Core Typeahead Functionality

### Medium Priority - Polish & Validation

### Low Priority - Documentation & Cleanup

- **Remove spec file after implementation** - Delete `ralph/specs/project-sharing-dropdown.md` once feature is fully implemented and tested (per Ralph pattern of removing completed specs from planning directory).

## Notes

### Architecture Decisions

- **Notification System**: Use existing ChatContext `addNotification(message, type)` function, NOT the object-based pattern shown in spec
- **Switch Component**: Use existing custom Switch component at `src/lib/components/ui/switch.tsx` (custom implementation, not Radix-based)
- **Debouncing**: Use existing `useDebounce` hook from `src/lib/hooks/useDebounce.ts`
- **API Pattern**: Follow existing projects API structure with service/hooks/keys separation
- **Sequential Submission**: Backend API only supports one user at a time, so use for-loop with await (not Promise.all)

### Existing Infrastructure Verified

✅ **Available Components**: Switch, Popover, Input, Button, Badge, Dialog, Select, Label, Separator
✅ **Utility Functions**: `cn()` for className merging at `src/lib/utils/cnTailwind.ts`
✅ **Icons**: Lucide React already installed (use Search, X, Loader2, Users icons)
✅ **Hooks**: useDebounce already exists
✅ **React Query**: Already configured with QueryClient in StoryProvider for stories
✅ **MSW**: Mock Service Worker configured in Storybook for API mocking

### Missing Dependencies

❌ **@radix-ui/react-switch**: NOT installed (but using custom Switch component instead, so not needed)

### Implementation Patterns to Follow

1. **Type Safety**: Use strict TypeScript typing (no `any`), optional fields marked with `?`
2. **API Services**: Separate service functions, React Query hooks, and cache keys into dedicated files
3. **State Management**: Use React Query for server state, useState for UI state
4. **Error Handling**: Use try/catch with user-friendly notifications via ChatContext
5. **Story Mocking**: Use MSW handlers in `parameters.msw` for API mocking, StoryProvider for context mocking
6. **Accessibility**: Maintain keyboard navigation, ARIA attributes, screen reader support

### Key Findings

- ShareDialog currently only supports email-based sharing (lines 22-74 in ShareDialog.tsx)
- CollaboratorsResponse API returns `{ collaborators: Collaborator[] }` without owner in array
- React Query hooks use mutations with optimistic updates and cache invalidation
- Dialog resets form state on open via useEffect (lines 40-47)
- Permission check via `canShareProject(project)` returns null if not owner (line 115)
- Storybook stories use comprehensive MSW mocking with play functions for testing
- Build validation ALWAYS required: `npm run build-package && npm run lint`
- Storybook validation REQUIRED for ShareDialog: `npx vitest --project=storybook src/stories/ShareDialog.stories.tsx`

### Out of Scope (Per Spec)

- Role selection in typeahead mode (hardcoded to "viewer")
- Persistent toggle preference across sessions
- Batch share API endpoint (backend doesn't support)
- Progress bar during sequential submission
- Cancel pending submissions functionality
- Advanced search filters or pagination
- User avatars in search results
