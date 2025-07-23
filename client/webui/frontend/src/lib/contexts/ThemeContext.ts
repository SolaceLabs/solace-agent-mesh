import { createContext } from "react";

export interface ThemeContextValue {
    currentTheme: "light" | "dark";
    toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
