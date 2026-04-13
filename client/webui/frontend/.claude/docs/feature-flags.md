# Feature Flags

Feature flags are defined in YAML and served to the frontend via `/api/v1/config/features`. The frontend uses **OpenFeature SDK** with a custom `SamFeatureProvider`.

## Architecture

```text
features.yaml (Python backend)
    ↓  GET /api/v1/config/features
FeatureFlagProvider (src/lib/providers/FeatureFlagProvider.tsx)
    ↓  OpenFeature.setProvider(new SamFeatureProvider(flags))
useBooleanFlagValue / useBooleanFlagDetails  (@openfeature/react-sdk)
    ↓  wrapped by
useIs<Feature>Enabled  (src/lib/hooks/feature-flags/)
    ↓  consumed by
Components
```

`FeatureFlagProvider` sits early in the provider tree (wraps `ConfigProvider`), so flags are available everywhere. Flags are fetched once at startup with `staleTime: Infinity` and default to `false` on fetch failure.

## Flag definitions

- **Community**: `src/solace_agent_mesh/common/features/features.yaml` (in the Python root)

Each flag entry has: `key`, `name`, `release_phase`, `default`, `jira`, and optional `description`. The environment variable `SAM_FEATURE_<UPPER_KEY>` overrides the YAML default.

## Hook convention

Every feature flag consumed in the frontend **must** have a dedicated wrapper hook in `src/lib/hooks/feature-flags/`:

```text
src/lib/hooks/feature-flags/
├── index.ts                              # barrel re-export
├── useIsMentionsEnabled.ts
├── useIsProjectSharingEnabled.ts
├── useIsProjectIndexingEnabled.ts
├── useIsAutoTitleGenerationEnabled.ts
├── useIsChatSharingEnabled.ts
└── useIsInlineActivityTimelineEnabled.ts
```

### Simple flag

```typescript
import { useBooleanFlagValue } from "@openfeature/react-sdk";

/**
 * Feature: Project Sharing
 * Flag key: project_sharing
 * Jira: DATAGO-115145
 */
export function useIsProjectSharingEnabled(): boolean {
    return useBooleanFlagValue("project_sharing", false);
}
```

### Compound flag (flag + prerequisite)

When a feature requires both the flag and a runtime condition, keep that logic in the hook:

```typescript
import { useBooleanFlagValue } from "@openfeature/react-sdk";
import { useConfigContext } from "../useConfigContext";

/**
 * Feature: Mentions
 * Flag key: mentions
 * Jira: DATAGO-121076
 */
export function useIsMentionsEnabled(): boolean {
    const { identityServiceType } = useConfigContext();
    const flagEnabled = useBooleanFlagValue("mentions", false);
    return flagEnabled && identityServiceType !== null;
}
```

### Rules

- **Never call `useBooleanFlagValue` / `useBooleanFlagDetails` directly in components.** Always go through a wrapper hook.
- The JSDoc header must include the feature name, flag key, and Jira epic.
- Re-export every hook from `feature-flags/index.ts`.

## Adding a new feature flag

1. Create `src/lib/hooks/feature-flags/useIs<FeatureName>Enabled.ts`
2. Re-export from `feature-flags/index.ts`
3. Import the hook in components

## Removing a feature flag

1. Search for the hook name (`useIs<FeatureName>Enabled`) to find all call sites
2. Replace conditional rendering with the enabled branch (or remove the gated code entirely)
3. Delete the hook file and remove from `feature-flags/index.ts`

## Testing

Use `OpenFeatureTestProvider` from `@openfeature/react-sdk` in tests and Storybook:

```typescript
import { OpenFeatureTestProvider } from "@openfeature/react-sdk";

<OpenFeatureTestProvider flagValueMap={{ project_sharing: true }}>
    <ComponentUnderTest />
</OpenFeatureTestProvider>
```

For unit tests that mock the hook directly:

```typescript
vi.mock("@/lib/hooks/feature-flags", () => ({
    useIsProjectSharingEnabled: vi.fn(() => true),
}));
```

## Deprecated: configFeatureEnablement

`useConfigContext().configFeatureEnablement` is **deprecated**. Do not use it for new features. Existing usages should be migrated to OpenFeature wrapper hooks over time.
