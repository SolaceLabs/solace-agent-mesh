# Operational Knowledge - Solace Agent Mesh UI

This file contains operational learnings for Ralph. Keep it LEAN - only operational knowledge, NOT status updates or progress notes.

## Project Context

- **Project root**: `/Users/jamie.karam/git/solace-agent-mesh/client/webui/frontend`
- **Stack**: React 19, TypeScript, Vite, TailwindCSS
- **Testing**: Build validation via `npm run build-package && npm run lint`
- **Component Library**: Radix UI components
- **State Management**: [To be discovered during planning]

## Patterns That Work

- **Type Validation**: Type changes should be validated with both build and lint to ensure strict type safety and code quality.
- **Storybook & Context**: When writing stories for components that use complex Context Providers (like ProjectProvider), if mocking is difficult, document the dependency in the story parameters/docs rather than over-engineering a mock provider.

## Patterns That Don't Work

[Ralph will update this as needed]

## Code Conventions to Follow

- **Type Centralization**: Keep all domain-specific types in `src/lib/types/{domain}.ts`
- **Strict Typing**: Use strict typing (no `any`) and optional fields (?) for properties that may not always be present (like `role` on Project list vs detail)

## Testing Strategy

- **Build Validation** (ALWAYS REQUIRED): Run `npm run build-package && npm run lint` after every change
- **Storybook Tests** (REQUIRED only for ShareDialog.stories.tsx):
    - Run `npx vitest --project=storybook src/stories/ShareDialog.stories.tsx` when creating or updating ShareDialog story
    - Validates that the ShareDialog story renders without errors
    - Must pass before task is considered complete
    - Fix any rendering errors or test failures immediately
    - Skip Storybook tests for other stories to save tokens
- **Storybook Stories**: Write `.stories.tsx` files for new UI components (Dialogs, Sections, Cards, etc.)
    - Keep stories simple - 1-2 basic variants (Default + one other state)
    - Follow pattern from `src/stories/Button.stories.tsx`
    - Use mock data (no real API calls)
    - Mock contexts/providers as needed (e.g., ProjectProvider, AuthContext)
    - Generic visual verification, not comprehensive testing
    - Skip stories for: API services, types, utilities, hooks, or updates to existing components
- **TypeScript**: Strict mode is enabled - types must be correct
- **Test Updates**: If a task modifies behavior, update relevant tests before considering task complete
- All tests (build, lint, storybook) must pass before task is considered complete

## Important Reminders

- VERIFY before assuming something is missing
- Follow existing patterns in the codebase
- No placeholders or stubs - implement completely
- Keep this file lean - status updates go in IMPLEMENTATION_PLAN.md
- All implementation code goes in project root, NOT in ralph/ directory
