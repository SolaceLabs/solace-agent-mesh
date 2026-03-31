import { createContext } from "react";
import type { ThemeDefinition } from "@/lib/providers/themes/palettes/themePalette";

export interface ThemeContextValue {
    currentTheme: string;
    themes: ThemeDefinition[];
    setTheme: (themeId: string) => void;
    toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
