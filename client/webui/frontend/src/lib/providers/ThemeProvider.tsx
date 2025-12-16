import React, { useEffect, useMemo, useState, type ReactNode } from "react";
import { ThemeContext, type ThemeContextValue } from "@/lib/contexts";
import { solace, type ThemePalette } from "./themes/palettes";
import { generateThemeVariables } from "./themes/themeMapping";

const LOCAL_STORAGE_KEY = "sam-theme";

function paletteToCSSVariables(themePalette: ThemePalette): Record<string, string> {
    const variables: Record<string, string> = {};

    // Brand colors
    if (themePalette.brand.wMain) variables["--color-brand-wMain"] = themePalette.brand.wMain;
    if (themePalette.brand.wMain30) variables["--color-brand-wMain30"] = themePalette.brand.wMain30;
    if (themePalette.brand.w100) variables["--color-brand-w100"] = themePalette.brand.w100;
    if (themePalette.brand.w60) variables["--color-brand-w60"] = themePalette.brand.w60;
    if (themePalette.brand.w30) variables["--color-brand-w30"] = themePalette.brand.w30;
    if (themePalette.brand.w10) variables["--color-brand-w10"] = themePalette.brand.w10;

    // Primary colors
    if (themePalette.primary.wMain) variables["--color-primary-wMain"] = themePalette.primary.wMain;
    if (themePalette.primary.w100) variables["--color-primary-w100"] = themePalette.primary.w100;
    if (themePalette.primary.w90) variables["--color-primary-w90"] = themePalette.primary.w90;
    if (themePalette.primary.w60) variables["--color-primary-w60"] = themePalette.primary.w60;
    if (themePalette.primary.w40) variables["--color-primary-w40"] = themePalette.primary.w40;
    if (themePalette.primary.w20) variables["--color-primary-w20"] = themePalette.primary.w20;
    if (themePalette.primary.w10) variables["--color-primary-w10"] = themePalette.primary.w10;

    // Primary text colors
    if (themePalette.primary.text.wMain) variables["--color-primary-text-wMain"] = themePalette.primary.text.wMain;
    if (themePalette.primary.text.w100) variables["--color-primary-text-w100"] = themePalette.primary.text.w100;
    if (themePalette.primary.text.w10) variables["--color-primary-text-w10"] = themePalette.primary.text.w10;

    // Secondary colors
    if (themePalette.secondary.wMain) variables["--color-secondary-wMain"] = themePalette.secondary.wMain;
    if (themePalette.secondary.w100) variables["--color-secondary-w100"] = themePalette.secondary.w100;
    if (themePalette.secondary.w80) variables["--color-secondary-w80"] = themePalette.secondary.w80;
    if (themePalette.secondary.w8040) variables["--color-secondary-w8040"] = themePalette.secondary.w8040;
    if (themePalette.secondary.w70) variables["--color-secondary-w70"] = themePalette.secondary.w70;
    if (themePalette.secondary.w40) variables["--color-secondary-w40"] = themePalette.secondary.w40;
    if (themePalette.secondary.w20) variables["--color-secondary-w20"] = themePalette.secondary.w20;
    if (themePalette.secondary.w10) variables["--color-secondary-w10"] = themePalette.secondary.w10;

    // Secondary text colors
    if (themePalette.secondary.text.wMain) variables["--color-secondary-text-wMain"] = themePalette.secondary.text.wMain;
    if (themePalette.secondary.text.w50) variables["--color-secondary-text-w50"] = themePalette.secondary.text.w50;

    // Background colors
    if (themePalette.background.wMain) variables["--color-background-wMain"] = themePalette.background.wMain;
    if (themePalette.background.w100) variables["--color-background-w100"] = themePalette.background.w100;
    if (themePalette.background.w20) variables["--color-background-w20"] = themePalette.background.w20;
    if (themePalette.background.w10) variables["--color-background-w10"] = themePalette.background.w10;

    // Info colors
    if (themePalette.info?.wMain) variables["--color-info-wMain"] = themePalette.info.wMain;
    if (themePalette.info?.w100) variables["--color-info-w100"] = themePalette.info.w100;
    if (themePalette.info?.w70) variables["--color-info-w70"] = themePalette.info.w70;
    if (themePalette.info?.w30) variables["--color-info-w30"] = themePalette.info.w30;
    if (themePalette.info?.w20) variables["--color-info-w20"] = themePalette.info.w20;
    if (themePalette.info?.w10) variables["--color-info-w10"] = themePalette.info.w10;

    // Error colors
    if (themePalette.error?.wMain) variables["--color-error-wMain"] = themePalette.error.wMain;
    if (themePalette.error?.w100) variables["--color-error-w100"] = themePalette.error.w100;
    if (themePalette.error?.w70) variables["--color-error-w70"] = themePalette.error.w70;
    if (themePalette.error?.w30) variables["--color-error-w30"] = themePalette.error.w30;
    if (themePalette.error?.w20) variables["--color-error-w20"] = themePalette.error.w20;
    if (themePalette.error?.w10) variables["--color-error-w10"] = themePalette.error.w10;

    // Warning colors
    if (themePalette.warning?.wMain) variables["--color-warning-wMain"] = themePalette.warning.wMain;
    if (themePalette.warning?.w100) variables["--color-warning-w100"] = themePalette.warning.w100;
    if (themePalette.warning?.w70) variables["--color-warning-w70"] = themePalette.warning.w70;
    if (themePalette.warning?.w30) variables["--color-warning-w30"] = themePalette.warning.w30;
    if (themePalette.warning?.w20) variables["--color-warning-w20"] = themePalette.warning.w20;
    if (themePalette.warning?.w10) variables["--color-warning-w10"] = themePalette.warning.w10;

    // Success colors
    if (themePalette.success?.wMain) variables["--color-success-wMain"] = themePalette.success.wMain;
    if (themePalette.success?.w100) variables["--color-success-w100"] = themePalette.success.w100;
    if (themePalette.success?.w70) variables["--color-success-w70"] = themePalette.success.w70;
    if (themePalette.success?.w30) variables["--color-success-w30"] = themePalette.success.w30;
    if (themePalette.success?.w20) variables["--color-success-w20"] = themePalette.success.w20;
    if (themePalette.success?.w10) variables["--color-success-w10"] = themePalette.success.w10;

    // StateLayer colors
    if (themePalette.stateLayer?.w10) variables["--color-stateLayer-w10"] = themePalette.stateLayer.w10;
    if (themePalette.stateLayer?.w20) variables["--color-stateLayer-w20"] = themePalette.stateLayer.w20;

    // Accent colors (n0-n9)
    if (themePalette.accent?.n0?.wMain) variables["--color-accent-n0-wMain"] = themePalette.accent.n0.wMain;
    if (themePalette.accent?.n0?.w100) variables["--color-accent-n0-w100"] = themePalette.accent.n0.w100;
    if (themePalette.accent?.n0?.w30) variables["--color-accent-n0-w30"] = themePalette.accent.n0.w30;
    if (themePalette.accent?.n0?.w10) variables["--color-accent-n0-w10"] = themePalette.accent.n0.w10;

    if (themePalette.accent?.n1?.wMain) variables["--color-accent-n1-wMain"] = themePalette.accent.n1.wMain;
    if (themePalette.accent?.n1?.w100) variables["--color-accent-n1-w100"] = themePalette.accent.n1.w100;
    if (themePalette.accent?.n1?.w60) variables["--color-accent-n1-w60"] = themePalette.accent.n1.w60;
    if (themePalette.accent?.n1?.w30) variables["--color-accent-n1-w30"] = themePalette.accent.n1.w30;
    if (themePalette.accent?.n1?.w20) variables["--color-accent-n1-w20"] = themePalette.accent.n1.w20;
    if (themePalette.accent?.n1?.w10) variables["--color-accent-n1-w10"] = themePalette.accent.n1.w10;

    if (themePalette.accent?.n2?.wMain) variables["--color-accent-n2-wMain"] = themePalette.accent.n2.wMain;
    if (themePalette.accent?.n2?.w100) variables["--color-accent-n2-w100"] = themePalette.accent.n2.w100;
    if (themePalette.accent?.n2?.w30) variables["--color-accent-n2-w30"] = themePalette.accent.n2.w30;
    if (themePalette.accent?.n2?.w20) variables["--color-accent-n2-w20"] = themePalette.accent.n2.w20;
    if (themePalette.accent?.n2?.w10) variables["--color-accent-n2-w10"] = themePalette.accent.n2.w10;

    if (themePalette.accent?.n3?.wMain) variables["--color-accent-n3-wMain"] = themePalette.accent.n3.wMain;
    if (themePalette.accent?.n3?.w100) variables["--color-accent-n3-w100"] = themePalette.accent.n3.w100;
    if (themePalette.accent?.n3?.w30) variables["--color-accent-n3-w30"] = themePalette.accent.n3.w30;
    if (themePalette.accent?.n3?.w10) variables["--color-accent-n3-w10"] = themePalette.accent.n3.w10;

    if (themePalette.accent?.n4?.wMain) variables["--color-accent-n4-wMain"] = themePalette.accent.n4.wMain;
    if (themePalette.accent?.n4?.w100) variables["--color-accent-n4-w100"] = themePalette.accent.n4.w100;
    if (themePalette.accent?.n4?.w30) variables["--color-accent-n4-w30"] = themePalette.accent.n4.w30;

    if (themePalette.accent?.n5?.wMain) variables["--color-accent-n5-wMain"] = themePalette.accent.n5.wMain;
    if (themePalette.accent?.n5?.w100) variables["--color-accent-n5-w100"] = themePalette.accent.n5.w100;
    if (themePalette.accent?.n5?.w60) variables["--color-accent-n5-w60"] = themePalette.accent.n5.w60;
    if (themePalette.accent?.n5?.w30) variables["--color-accent-n5-w30"] = themePalette.accent.n5.w30;

    if (themePalette.accent?.n6?.wMain) variables["--color-accent-n6-wMain"] = themePalette.accent.n6.wMain;
    if (themePalette.accent?.n6?.w100) variables["--color-accent-n6-w100"] = themePalette.accent.n6.w100;
    if (themePalette.accent?.n6?.w30) variables["--color-accent-n6-w30"] = themePalette.accent.n6.w30;

    if (themePalette.accent?.n7?.wMain) variables["--color-accent-n7-wMain"] = themePalette.accent.n7.wMain;
    if (themePalette.accent?.n7?.w100) variables["--color-accent-n7-w100"] = themePalette.accent.n7.w100;
    if (themePalette.accent?.n7?.w30) variables["--color-accent-n7-w30"] = themePalette.accent.n7.w30;

    if (themePalette.accent?.n8?.wMain) variables["--color-accent-n8-wMain"] = themePalette.accent.n8.wMain;
    if (themePalette.accent?.n8?.w100) variables["--color-accent-n8-w100"] = themePalette.accent.n8.w100;
    if (themePalette.accent?.n8?.w30) variables["--color-accent-n8-w30"] = themePalette.accent.n8.w30;

    if (themePalette.accent?.n9?.wMain) variables["--color-accent-n9-wMain"] = themePalette.accent.n9.wMain;

    // Learning colors
    if (themePalette.learning?.wMain) variables["--color-learning-wMain"] = themePalette.learning.wMain;
    if (themePalette.learning?.w100) variables["--color-learning-w100"] = themePalette.learning.w100;
    if (themePalette.learning?.w90) variables["--color-learning-w90"] = themePalette.learning.w90;
    if (themePalette.learning?.w20) variables["--color-learning-w20"] = themePalette.learning.w20;
    if (themePalette.learning?.w10) variables["--color-learning-w10"] = themePalette.learning.w10;

    return variables;
}

function generateCustomTheme(themePalette: ThemePalette, theme: "light" | "dark" = "light"): Record<string, string> {
    const variables: Record<string, string> = {};

    if (themePalette) {
        const directVariables = paletteToCSSVariables(themePalette);
        Object.assign(variables, directVariables);
    }

    const themeVariables = generateThemeVariables(themePalette, theme);
    Object.assign(variables, themeVariables);

    return variables;
}

function getInitialTheme(): "light" | "dark" {
    // First check if there's a saved preference in localStorage
    const storedTheme = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (storedTheme === "dark" || storedTheme === "light") {
        return storedTheme;
    }

    // If no saved preference, check system preference
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
    }

    // Default to light theme
    return "light";
}

function applyThemeToDOM(themePalette: ThemePalette, theme: "light" | "dark"): void {
    const variables = generateCustomTheme(themePalette, theme);
    const root = document.documentElement;

    // Apply all CSS variables to :root
    for (const [property, value] of Object.entries(variables)) {
        root.style.setProperty(property, value);
    }

    // Atomic class update to prevent race conditions
    requestAnimationFrame(() => {
        if (process.env.NODE_ENV === "development") {
            console.log(`Applying ${theme} theme with palette`);
        }
        root.classList.remove("light", "dark");
        root.classList.add(theme);

        localStorage.setItem(LOCAL_STORAGE_KEY, theme);
    });
}

interface ThemeProviderProps {
    children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
    const themePalette: ThemePalette = useMemo(() => solace, []);

    const [currentTheme, setCurrentTheme] = useState<"light" | "dark">(() => {
        return getInitialTheme();
    });

    const contextValue: ThemeContextValue = useMemo(
        () => ({
            currentTheme,
            toggleTheme: () => {
                const newTheme = currentTheme === "light" ? "dark" : "light";
                setCurrentTheme(newTheme);
                localStorage.setItem(LOCAL_STORAGE_KEY, newTheme);
            },
        }),
        [currentTheme]
    );

    // Listen for changes in system color scheme preference
    useEffect(() => {
        const hasUserPreference = localStorage.getItem(LOCAL_STORAGE_KEY) !== null;
        if (!hasUserPreference) {
            const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

            const handleChange = (e: MediaQueryListEvent) => {
                setCurrentTheme(e.matches ? "dark" : "light");
            };

            // Add the listener
            if (mediaQuery.addEventListener) {
                mediaQuery.addEventListener("change", handleChange);
            } else {
                // For older browsers
                mediaQuery.addListener(handleChange);
            }

            return () => {
                if (mediaQuery.removeEventListener) {
                    mediaQuery.removeEventListener("change", handleChange);
                } else {
                    // For older browsers
                    mediaQuery.removeListener(handleChange);
                }
            };
        }
    }, []);

    useEffect(() => {
        document.documentElement.classList.remove("light", "dark");
        applyThemeToDOM(themePalette, currentTheme);
    }, [currentTheme, themePalette]);

    return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
};
