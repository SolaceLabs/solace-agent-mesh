# Implementation Plan

## Priority Tasks (Sorted by Priority)

### High Priority - Core Typeahead Functionality

- **Implement typeahead search input with debouncing** - Add search input field with search icon, loading spinner, and debounced search using existing `useDebounce` hook (300ms delay). Minimum 2 characters required before triggering search. Use `useSearchPeople` hook for API integration.

- **Create search results dropdown with keyboard navigation** - Implement Popover dropdown below search input showing user results (name on line 1, email + title on line 2). Support arrow key navigation (up/down), Enter to select, Escape to clear. Highlight selected result with background color. Show "No users found" message when search returns empty.

- **Implement pending users list UI** - Add section between search input and collaborators list showing pending users (not yet shared). Display user name, email, "Viewer" badge, and remove button (X icon). Section only visible when `pendingUsers.length > 0`. Header shows "Pending Invitations (X)".

- **Add duplicate prevention logic** - Before adding user to pending list, check against: (1) existing pending users by id/email, (2) current collaborators by email, (3) project owner by email. Show appropriate error notification for each case using `addNotification()` from ChatContext.

- **Implement sequential batch submission** - Add "Share with X user(s)" button (disabled when no pending users). On click, iterate through pending users and call `shareProject` API sequentially (one at a time, not parallel). Collect errors for failed submissions. Show success notification on completion or error notification with failed user names. Clear pending list on full success. Refresh collaborators list after submission.

- **Update ShareDialog to conditionally render email vs typeahead mode** - Refactor ShareDialog JSX to show either email input form (existing) or typeahead search UI based on `useTypeahead` state. Preserve all existing email mode functionality unchanged.

- **Fix addNotification calls to match function signature** - The spec uses object parameter `{ type: "error", message: "..." }` but actual implementation is `addNotification(message, type)`. Update all new notification calls to use correct signature: `addNotification("message", "success")`.

### Medium Priority - Polish & Validation

- **Add reset logic for dialog open state** - In `useEffect` hook that runs when dialog opens, reset: `useTypeahead` to false, `searchQuery` to empty, `searchResults` to empty array, `pendingUsers` to empty array, `selectedIndex` to -1. Ensures clean state each time dialog is opened.

- **Add error handling for search failures** - Wrap `PeopleService.searchPeople()` call in try/catch. On error, show notification "Failed to search users" and set `searchResults` to empty array. Set `isSearching` to false in finally block.

- **Update Storybook stories for ShareDialog** - Add new stories to `src/stories/ShareDialog.stories.tsx`: TypeaheadMode (empty search), TypeaheadWithResults (3-4 mock users), TypeaheadWithPending (2-3 pending users), TypeaheadNoResults ("No users found" message). Mock `PeopleService.searchPeople` with MSW handlers returning fixture data.

- **Run build validation tests** - Execute `npm run build-package && npm run lint` to ensure TypeScript strict mode compliance and no linting errors. Fix any type errors or linting issues before marking task complete.

- **Run Storybook validation tests for ShareDialog** - Execute `npx vitest --project=storybook src/stories/ShareDialog.stories.tsx` to validate ShareDialog stories render without errors. Fix any rendering errors or test failures immediately (required per AGENTS.md testing strategy).

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
