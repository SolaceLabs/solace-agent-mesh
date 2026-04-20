# Frontend Development Guidelines

## Stack

React 19, TanStack Query v5, Tailwind v4, Radix UI, Vitest, Playwright

- Import alias: `@/` maps to `src/`
- UI primitives are shadcn-style (Radix + cva) in `src/lib/components/ui/`

## Theming

- Use CSS variables from the theme palette for all colors (e.g. `--primary-text-wMain`, `--secondary-w40`)
- Never use `currentTheme === "dark"` to branch on theme
- Never hardcode hex values. If unavoidable, add a comment explaining why.
- The `darkSurface` group is for guaranteed-dark backgrounds (nav, tooltips, toasts)

## Components & Styling

- Use standard UI components (`Button`, `Input`, `Select`, etc.) — never native elements
- Use `cn()` for class merging — never template literals
- Use Tailwind v4 `(--var)` syntax — not bracket `[var(--var)]`

## Tests

```sh
npm run test:unit          # unit tests (jsdom)
npm run test:storybook     # storybook tests (Playwright browser)
npm run ci:storybook:coverage  # both + coverage
```

## Deep Docs

Read these when working in the relevant area:

- [API Endpoints](docs/api-endpoints.md) — how to add a new API module (service, keys, hooks)
- [Feature Flags](docs/feature-flags.md) — OpenFeature integration, hook convention, adding/removing flags
- [Testing](docs/testing.md) — test framework setup, patterns, and mock utilities
