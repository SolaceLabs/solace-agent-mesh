import React, { useEffect, useMemo, useState, type ReactNode } from "react";
import { ThemeContext, type ThemeContextValue } from "@/lib/contexts";
import { themes, themeMap, type ThemePalette } from "./themes/palettes";
import { generateFallbackVariables } from "./themes/themeMapping";

const LOCAL_STORAGE_KEY = "sam-theme";

function paletteToCSSVariables(obj: Record<string, unknown>, prefix = "-"): Record<string, string> {
    const variables: Record<string, string> = {};
    for (const [key, value] of Object.entries(obj)) {
        const varName = `${prefix}-${key}`;
        if (typeof value === "string") {
            variables[varName] = value;
        } else if (value && typeof value === "object") {
            Object.assign(variables, paletteToCSSVariables(value as Record<string, unknown>, varName));
        }
    }
    return variables;
}

function generateThemeVariables(themePalette: ThemePalette): Record<string, string> {
    const variables = paletteToCSSVariables(themePalette as unknown as Record<string, unknown>);
    const fallbackVars = generateFallbackVariables(themePalette);
    Object.assign(variables, fallbackVars);

    return variables;
}

function getInitialTheme(): string {
    const storedTheme = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (storedTheme && themeMap.has(storedTheme)) {
        return storedTheme;
    }

    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
    }

    return themes[0].id;
}

function applyThemeToDOM(themePalette: ThemePalette, theme: string): void {
    const variables = generateThemeVariables(themePalette);
    const root = document.documentElement;

    for (const [property, value] of Object.entries(variables)) {
        root.style.setProperty(property, value);
    }

    requestAnimationFrame(() => {
        if (process.env.NODE_ENV === "development") {
            console.log(`Applying ${theme} theme with palette`);
        }
        root.classList.remove(...themes.map(t => t.id));
        localStorage.setItem(LOCAL_STORAGE_KEY, theme);
    });
}

interface ThemeProviderProps {
    children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
    const [currentTheme, setCurrentTheme] = useState<string>(() => {
        return getInitialTheme();
    });

    const themePalette: ThemePalette = useMemo(() => {
        return themeMap.get(currentTheme)?.palette ?? themes[0].palette;
    }, [currentTheme]);

    const contextValue: ThemeContextValue = useMemo(
        () => ({
            currentTheme,
            themes,
            setTheme: (themeId: string) => {
                if (themeMap.has(themeId)) {
                    setCurrentTheme(themeId);
                    localStorage.setItem(LOCAL_STORAGE_KEY, themeId);
                }
            },
            toggleTheme: () => {
                const currentIndex = themes.findIndex(t => t.id === currentTheme);
                const nextIndex = (currentIndex + 1) % themes.length;
                const nextId = themes[nextIndex].id;
                setCurrentTheme(nextId);
                localStorage.setItem(LOCAL_STORAGE_KEY, nextId);
            },
        }),
        [currentTheme]
    );

    useEffect(() => {
        const hasUserPreference = localStorage.getItem(LOCAL_STORAGE_KEY) !== null;
        if (!hasUserPreference) {
            const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

            const handleChange = (e: MediaQueryListEvent) => {
                setCurrentTheme(e.matches ? "dark" : "light");
            };

            if (mediaQuery.addEventListener) {
                mediaQuery.addEventListener("change", handleChange);
            } else {
                mediaQuery.addListener(handleChange);
            }

            return () => {
                if (mediaQuery.removeEventListener) {
                    mediaQuery.removeEventListener("change", handleChange);
                } else {
                    mediaQuery.removeListener(handleChange);
                }
            };
        }
    }, []);

    useEffect(() => {
        applyThemeToDOM(themePalette, currentTheme);
    }, [currentTheme, themePalette]);

    return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
};
