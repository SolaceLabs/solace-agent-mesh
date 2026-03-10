import { createContext } from "react";

export interface ThemeContextValue {
    currentTheme: "light" | "dark";
    toggleTheme: () => void;
    setTheme: (theme: "light" | "dark") => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
