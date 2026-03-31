import type { ThemePalette } from "./palettes/themePalette";

export interface ThemeMapping {
    [key: string]: string;
}

/**
 * Fallback colors that aren't part of the standard palette structure
 * but are needed by components. These are resolved from the active palette.
 */
export const fallbackColors: ThemeMapping = {
    "error-text-wMain": "error.wMain",
    "error-text-w50": "error.w70",
    "warning-text-wMain": "warning.wMain",
    "warning-text-w50": "warning.w70",
    "success-text-wMain": "success.wMain",
    "success-text-w50": "success.w70",
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

export function generateFallbackVariables(themePalette: ThemePalette): Record<string, string> {
    const variables: Record<string, string> = {};

    for (const [cssVar, customPath] of Object.entries(fallbackColors)) {
        variables[`--${cssVar}`] = resolveColorPath(themePalette, customPath);
    }

    return variables;
}
