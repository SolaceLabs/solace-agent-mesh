# Frontend Development Guidelines

## Theming

- Use CSS variables from the theme palette for all colors (e.g. `--primary-text-wMain`, `--secondary-w40`)
- Never use `currentTheme === "dark"` to branch on theme
- Never hardcode hex values. If unavoidable, add a comment explaining why.
- The `darkSurface` group is for guaranteed-dark backgrounds (nav, tooltips, toasts)

## Components & Styling

- Use standard UI components (`Button`, `Input`, `Select`, etc.) — never native elements
- Use `cn()` for class merging — never template literals
- Use Tailwind v4 `(--var)` syntax — not bracket `[var(--var)]`
