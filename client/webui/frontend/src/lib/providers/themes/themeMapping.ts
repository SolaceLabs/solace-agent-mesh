import type { ThemePalette } from "./palettes/themePalette";

export interface ThemeMapping {
    [key: string]: string;
}

/**
 * Maps semantic CSS custom property names to palette paths.
 * A single unified mapping — the active palette (light or dark) provides the correct values.
 */
export const customThemeMapping: ThemeMapping = {
    background: "background.w10",
    "card-background": "background.w20",
    foreground: "primary.text.wMain",
    card: "background.w10",
    "card-foreground": "primary.text.wMain",
    popover: "background.w10",
    "popover-foreground": "primary.text.wMain",
    primary: "primary.wMain",
    "primary-foreground": "primary.text.w10",
    secondary: "secondary.w10",
    "secondary-foreground": "secondary.text.wMain",
    muted: "secondary.w10",
    "muted-foreground": "secondary.text.wMain",
    placeholder: "secondary.wMain",
    accent: "secondary.w40",
    "accent-foreground": "secondary.text.wMain",
    destructive: "error.wMain",
    border: "secondary.w40",
    input: "secondary.w40",
    ring: "brand.wMain",
    "ring-offset": "brand.wMain",
    "accent-background": "background.w20",
    "message-background": "secondary.w20",
    "edge-hover-color": "secondary.w70",
    "shadow-color": "primary.w90",
    "scrollbar-thumb": "primary.w20",

    // Sidebar colors
    sidebar: "background.w20",
    "sidebar-foreground": "primary.text.wMain",
    "sidebar-primary": "primary.wMain",
    "sidebar-primary-foreground": "primary.text.w10",
    "sidebar-accent": "secondary.w10",
    "sidebar-accent-foreground": "secondary.text.wMain",
    "sidebar-border": "secondary.w40",
    "sidebar-ring": "brand.wMain",
};

/**
 * Legacy dual mapping — used when the feature flag is off.
 * Selects different palette paths for light vs dark themes from a single palette.
 */
export const legacyThemeMapping: { light: ThemeMapping; dark: ThemeMapping } = {
    light: {
        background: "background.w10",
        "card-background": "background.w20",
        foreground: "primary.text.wMain",
        card: "background.w10",
        "card-foreground": "primary.text.wMain",
        popover: "background.w10",
        "popover-foreground": "primary.text.wMain",
        primary: "primary.wMain",
        "primary-foreground": "primary.text.w10",
        secondary: "secondary.w10",
        "secondary-foreground": "secondary.text.wMain",
        muted: "secondary.w10",
        "muted-foreground": "secondary.text.wMain",
        placeholder: "secondary.wMain",
        accent: "secondary.w40",
        "accent-foreground": "secondary.text.wMain",
        destructive: "error.wMain",
        border: "secondary.w40",
        input: "secondary.w40",
        ring: "brand.wMain",
        "ring-offset": "brand.wMain",
        "accent-background": "background.w20",
        "message-background": "secondary.w20",
        "edge-hover-color": "secondary.w70",
        "scrollbar-thumb": "primary.w20",
        sidebar: "background.w20",
        "sidebar-foreground": "primary.text.wMain",
        "sidebar-primary": "primary.wMain",
        "sidebar-primary-foreground": "primary.text.w10",
        "sidebar-accent": "secondary.w10",
        "sidebar-accent-foreground": "secondary.text.wMain",
        "sidebar-border": "secondary.w40",
        "sidebar-ring": "brand.wMain",
    },
    dark: {
        background: "background.w100",
        "card-background": "background.w100",
        foreground: "primary.text.w10",
        card: "background.wMain",
        "card-foreground": "primary.text.w10",
        popover: "background.wMain",
        "popover-foreground": "primary.text.w10",
        primary: "primary.w60",
        "primary-foreground": "primary.text.wMain",
        secondary: "secondary.w80",
        "secondary-foreground": "secondary.text.w50",
        muted: "secondary.w80",
        "muted-foreground": "secondary.text.w50",
        placeholder: "secondary.w70",
        accent: "secondary.w80",
        "accent-foreground": "secondary.text.w50",
        destructive: "error.wMain",
        border: "secondary.w70",
        input: "secondary.w70",
        ring: "brand.w60",
        "ring-offset": "brand.w60",
        "accent-background": "primary.w90",
        "message-background": "secondary.w70",
        "edge-hover-color": "secondary.w20",
        "shadow-color": "primary.w90",
        "scrollbar-thumb": "primary.wMain",
        sidebar: "background.wMain",
        "sidebar-foreground": "primary.text.w10",
        "sidebar-primary": "primary.w60",
        "sidebar-primary-foreground": "primary.text.wMain",
        "sidebar-accent": "secondary.w80",
        "sidebar-accent-foreground": "secondary.text.w50",
        "sidebar-border": "secondary.w70",
        "sidebar-ring": "brand.w60",
    },
};

/**
 * Fallback colors for missing mappings
 * These will use the same color for both light and dark themes
 */
export const fallbackColors: ThemeMapping = {
    // Error text colors (not in Solace palette)
    "error-text-wMain": "error.wMain",
    "error-text-w50": "error.w70",

    // Warning text colors (not in Solace palette)
    "warning-text-wMain": "warning.wMain",
    "warning-text-w50": "warning.w70",

    // Success text colors (not in Solace palette)
    "success-text-wMain": "success.wMain",
    "success-text-w50": "success.w70",

    // Info text colors (not in Solace palette)
    "info-text-wMain": "info.wMain",
    "info-text-w50": "info.w70",
};

export function resolveColorPath(themePalette: ThemePalette, path: string): string {
    const pathParts = path.split(".");
    let current = themePalette;

    for (const part of pathParts) {
        if (current && typeof current === "object" && part in current) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            current = (current as Record<string, any>)[part];
        } else {
            console.warn(`Color path not found: ${path}`);
            return "#000000";
        }
    }

    return typeof current === "string" ? current : "#000000";
}

export function generateThemeVariables(themePalette: ThemePalette, theme?: "light" | "dark"): Record<string, string> {
    const variables: Record<string, string> = {};
    const mapping = theme ? legacyThemeMapping[theme] : customThemeMapping;

    for (const [cssVar, customPath] of Object.entries(mapping)) {
        variables[`--${cssVar}`] = resolveColorPath(themePalette, customPath);
    }

    for (const [cssVar, customPath] of Object.entries(fallbackColors)) {
        variables[`--color-${cssVar}`] = resolveColorPath(themePalette, customPath);
    }

    return variables;
}
