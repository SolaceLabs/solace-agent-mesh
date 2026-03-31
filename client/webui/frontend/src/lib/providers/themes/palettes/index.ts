export * from "./themePalette";
export * from "./solace";
export * from "./solaceDark";

import { solaceTheme } from "./solace";
import { solaceDarkTheme } from "./solaceDark";
import type { ThemeDefinition } from "./themePalette";

export const themes: ThemeDefinition[] = [solaceTheme, solaceDarkTheme];
export const themeMap = new Map(themes.map(t => [t.id, t]));
