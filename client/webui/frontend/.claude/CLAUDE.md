# Frontend Development Guidelines

## Theming

All colors must come from CSS variables defined by the theme palette. Never hardcode hex colors or use dark mode detection logic.

### Rules

- Use CSS variables like `--primary-text-wMain`, `--secondary-w40`, `--background-w10` for all colors
- Never use `dark:`, `isDark`, `currentTheme === "dark"`, or `classList.contains("dark")` to branch on theme
- Never hardcode hex color values in components — use the palette variables instead. If a hex value is unavoidable, add a comment explaining why (e.g. third-party library requirement, SVG spec limitation)
- Each theme palette defines its own values, so the same variable works across all themes
- The `darkSurface` palette group is for content on guaranteed-dark backgrounds (nav sidebar, tooltips, toasts)
- Prefer Tailwind classes with CSS variables (e.g. `text-(--primary-text-wMain)`) over inline `style` props where possible

### Variable naming

Variables follow the palette structure: `--{group}-{shade}` or `--{group}-{subgroup}-{shade}`

Common groups: `brand`, `primary`, `secondary`, `background`, `info`, `error`, `warning`, `success`, `accent`, `darkSurface`

Common shades: `wMain`, `w10`, `w20`, `w30`, `w40`, `w60`, `w70`, `w80`, `w100`

Examples:

- `--primary-text-wMain` — main text color
- `--secondary-w40` — secondary color at 40% weight
- `--background-w10` — lightest/darkest background
- `--brand-wMain` — brand accent color
- `--darkSurface-bg` — dark surface background (nav, tooltips, toasts)

## Styling

- Use standard UI components (`Button`, `Input`, `Select`, etc.) — never native `<button>`, `<input>`, `<select>`
- Use `cn()` for merging class names — never template literal concatenation
- Use Tailwind v4 `(--var)` syntax: `text-(--primary-text-wMain)` — not bracket notation `text-[var(--primary-text-wMain)]`
