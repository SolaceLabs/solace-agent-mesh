import React, { useEffect, useMemo, useState, type ReactNode } from "react";
import { ThemeContext, type ThemeContextValue } from "@/lib/contexts";
import { solace, solaceDark as solaceDarkLegacy, type ThemePalette } from "./themes/palettes";
import { generateFallbackVariables } from "./themes/themeMapping";

const LOCAL_STORAGE_KEY = "sam-theme";

function paletteToCSSVariables(themePalette: ThemePalette): Record<string, string> {
    const variables: Record<string, string> = {};

    // Brand colors
    if (themePalette.brand.wMain) variables["--brand-wMain"] = themePalette.brand.wMain;
    if (themePalette.brand.wMain30) variables["--brand-wMain30"] = themePalette.brand.wMain30;
    if (themePalette.brand.w100) variables["--brand-w100"] = themePalette.brand.w100;
    if (themePalette.brand.w60) variables["--brand-w60"] = themePalette.brand.w60;
    if (themePalette.brand.w30) variables["--brand-w30"] = themePalette.brand.w30;
    if (themePalette.brand.w10) variables["--brand-w10"] = themePalette.brand.w10;

    // Primary colors
    if (themePalette.primary.wMain) variables["--primary-wMain"] = themePalette.primary.wMain;
    if (themePalette.primary.w100) variables["--primary-w100"] = themePalette.primary.w100;
    if (themePalette.primary.w90) variables["--primary-w90"] = themePalette.primary.w90;
    if (themePalette.primary.w60) variables["--primary-w60"] = themePalette.primary.w60;
    if (themePalette.primary.w40) variables["--primary-w40"] = themePalette.primary.w40;
    if (themePalette.primary.w20) variables["--primary-w20"] = themePalette.primary.w20;
    if (themePalette.primary.w10) variables["--primary-w10"] = themePalette.primary.w10;

    // Primary text colors
    if (themePalette.primary.text.wMain) variables["--primary-text-wMain"] = themePalette.primary.text.wMain;
    if (themePalette.primary.text.w100) variables["--primary-text-w100"] = themePalette.primary.text.w100;
    if (themePalette.primary.text.w10) variables["--primary-text-w10"] = themePalette.primary.text.w10;

    // Secondary colors
    if (themePalette.secondary.wMain) variables["--secondary-wMain"] = themePalette.secondary.wMain;
    if (themePalette.secondary.w100) variables["--secondary-w100"] = themePalette.secondary.w100;
    if (themePalette.secondary.w80) variables["--secondary-w80"] = themePalette.secondary.w80;
    if (themePalette.secondary.w8040) variables["--secondary-w8040"] = themePalette.secondary.w8040;
    if (themePalette.secondary.w70) variables["--secondary-w70"] = themePalette.secondary.w70;
    if (themePalette.secondary.w40) variables["--secondary-w40"] = themePalette.secondary.w40;
    if (themePalette.secondary.w20) variables["--secondary-w20"] = themePalette.secondary.w20;
    if (themePalette.secondary.w10) variables["--secondary-w10"] = themePalette.secondary.w10;

    // Secondary text colors
    if (themePalette.secondary.text.wMain) variables["--secondary-text-wMain"] = themePalette.secondary.text.wMain;
    if (themePalette.secondary.text.w50) variables["--secondary-text-w50"] = themePalette.secondary.text.w50;

    // Background colors
    if (themePalette.background.wMain) variables["--background-wMain"] = themePalette.background.wMain;
    if (themePalette.background.w100) variables["--background-w100"] = themePalette.background.w100;
    if (themePalette.background.w20) variables["--background-w20"] = themePalette.background.w20;
    if (themePalette.background.w10) variables["--background-w10"] = themePalette.background.w10;

    // Info colors
    if (themePalette.info?.wMain) variables["--info-wMain"] = themePalette.info.wMain;
    if (themePalette.info?.w100) variables["--info-w100"] = themePalette.info.w100;
    if (themePalette.info?.w70) variables["--info-w70"] = themePalette.info.w70;
    if (themePalette.info?.w30) variables["--info-w30"] = themePalette.info.w30;
    if (themePalette.info?.w20) variables["--info-w20"] = themePalette.info.w20;
    if (themePalette.info?.w10) variables["--info-w10"] = themePalette.info.w10;

    // Error colors
    if (themePalette.error?.wMain) variables["--error-wMain"] = themePalette.error.wMain;
    if (themePalette.error?.w100) variables["--error-w100"] = themePalette.error.w100;
    if (themePalette.error?.w70) variables["--error-w70"] = themePalette.error.w70;
    if (themePalette.error?.w30) variables["--error-w30"] = themePalette.error.w30;
    if (themePalette.error?.w20) variables["--error-w20"] = themePalette.error.w20;
    if (themePalette.error?.w10) variables["--error-w10"] = themePalette.error.w10;

    // Warning colors
    if (themePalette.warning?.wMain) variables["--warning-wMain"] = themePalette.warning.wMain;
    if (themePalette.warning?.w100) variables["--warning-w100"] = themePalette.warning.w100;
    if (themePalette.warning?.w70) variables["--warning-w70"] = themePalette.warning.w70;
    if (themePalette.warning?.w30) variables["--warning-w30"] = themePalette.warning.w30;
    if (themePalette.warning?.w20) variables["--warning-w20"] = themePalette.warning.w20;
    if (themePalette.warning?.w10) variables["--warning-w10"] = themePalette.warning.w10;

    // Success colors
    if (themePalette.success?.wMain) variables["--success-wMain"] = themePalette.success.wMain;
    if (themePalette.success?.w100) variables["--success-w100"] = themePalette.success.w100;
    if (themePalette.success?.w70) variables["--success-w70"] = themePalette.success.w70;
    if (themePalette.success?.w30) variables["--success-w30"] = themePalette.success.w30;
    if (themePalette.success?.w20) variables["--success-w20"] = themePalette.success.w20;
    if (themePalette.success?.w10) variables["--success-w10"] = themePalette.success.w10;

    // StateLayer colors
    if (themePalette.stateLayer?.w10) variables["--stateLayer-w10"] = themePalette.stateLayer.w10;
    if (themePalette.stateLayer?.w20) variables["--stateLayer-w20"] = themePalette.stateLayer.w20;

    // Accent colors (n0-n9)
    if (themePalette.accent?.n0?.wMain) variables["--accent-n0-wMain"] = themePalette.accent.n0.wMain;
    if (themePalette.accent?.n0?.w100) variables["--accent-n0-w100"] = themePalette.accent.n0.w100;
    if (themePalette.accent?.n0?.w30) variables["--accent-n0-w30"] = themePalette.accent.n0.w30;
    if (themePalette.accent?.n0?.w10) variables["--accent-n0-w10"] = themePalette.accent.n0.w10;

    if (themePalette.accent?.n1?.wMain) variables["--accent-n1-wMain"] = themePalette.accent.n1.wMain;
    if (themePalette.accent?.n1?.w100) variables["--accent-n1-w100"] = themePalette.accent.n1.w100;
    if (themePalette.accent?.n1?.w60) variables["--accent-n1-w60"] = themePalette.accent.n1.w60;
    if (themePalette.accent?.n1?.w30) variables["--accent-n1-w30"] = themePalette.accent.n1.w30;
    if (themePalette.accent?.n1?.w20) variables["--accent-n1-w20"] = themePalette.accent.n1.w20;
    if (themePalette.accent?.n1?.w10) variables["--accent-n1-w10"] = themePalette.accent.n1.w10;

    if (themePalette.accent?.n2?.wMain) variables["--accent-n2-wMain"] = themePalette.accent.n2.wMain;
    if (themePalette.accent?.n2?.w100) variables["--accent-n2-w100"] = themePalette.accent.n2.w100;
    if (themePalette.accent?.n2?.w30) variables["--accent-n2-w30"] = themePalette.accent.n2.w30;
    if (themePalette.accent?.n2?.w20) variables["--accent-n2-w20"] = themePalette.accent.n2.w20;
    if (themePalette.accent?.n2?.w10) variables["--accent-n2-w10"] = themePalette.accent.n2.w10;

    if (themePalette.accent?.n3?.wMain) variables["--accent-n3-wMain"] = themePalette.accent.n3.wMain;
    if (themePalette.accent?.n3?.w100) variables["--accent-n3-w100"] = themePalette.accent.n3.w100;
    if (themePalette.accent?.n3?.w30) variables["--accent-n3-w30"] = themePalette.accent.n3.w30;
    if (themePalette.accent?.n3?.w10) variables["--accent-n3-w10"] = themePalette.accent.n3.w10;

    if (themePalette.accent?.n4?.wMain) variables["--accent-n4-wMain"] = themePalette.accent.n4.wMain;
    if (themePalette.accent?.n4?.w100) variables["--accent-n4-w100"] = themePalette.accent.n4.w100;
    if (themePalette.accent?.n4?.w30) variables["--accent-n4-w30"] = themePalette.accent.n4.w30;

    if (themePalette.accent?.n5?.wMain) variables["--accent-n5-wMain"] = themePalette.accent.n5.wMain;
    if (themePalette.accent?.n5?.w100) variables["--accent-n5-w100"] = themePalette.accent.n5.w100;
    if (themePalette.accent?.n5?.w60) variables["--accent-n5-w60"] = themePalette.accent.n5.w60;
    if (themePalette.accent?.n5?.w30) variables["--accent-n5-w30"] = themePalette.accent.n5.w30;

    if (themePalette.accent?.n6?.wMain) variables["--accent-n6-wMain"] = themePalette.accent.n6.wMain;
    if (themePalette.accent?.n6?.w100) variables["--accent-n6-w100"] = themePalette.accent.n6.w100;
    if (themePalette.accent?.n6?.w30) variables["--accent-n6-w30"] = themePalette.accent.n6.w30;

    if (themePalette.accent?.n7?.wMain) variables["--accent-n7-wMain"] = themePalette.accent.n7.wMain;
    if (themePalette.accent?.n7?.w100) variables["--accent-n7-w100"] = themePalette.accent.n7.w100;
    if (themePalette.accent?.n7?.w30) variables["--accent-n7-w30"] = themePalette.accent.n7.w30;

    if (themePalette.accent?.n8?.wMain) variables["--accent-n8-wMain"] = themePalette.accent.n8.wMain;
    if (themePalette.accent?.n8?.w100) variables["--accent-n8-w100"] = themePalette.accent.n8.w100;
    if (themePalette.accent?.n8?.w30) variables["--accent-n8-w30"] = themePalette.accent.n8.w30;

    if (themePalette.accent?.n9?.wMain) variables["--accent-n9-wMain"] = themePalette.accent.n9.wMain;

    // Learning colors
    if (themePalette.learning?.wMain) variables["--learning-wMain"] = themePalette.learning.wMain;
    if (themePalette.learning?.w100) variables["--learning-w100"] = themePalette.learning.w100;
    if (themePalette.learning?.w90) variables["--learning-w90"] = themePalette.learning.w90;
    if (themePalette.learning?.w20) variables["--learning-w20"] = themePalette.learning.w20;
    if (themePalette.learning?.w10) variables["--learning-w10"] = themePalette.learning.w10;

    // Dark surface colors (nav sidebar, tooltips, toasts, etc.)
    if (themePalette.darkSurface?.bg) variables["--darkSurface-bg"] = themePalette.darkSurface.bg;
    if (themePalette.darkSurface?.bgHover) variables["--darkSurface-bgHover"] = themePalette.darkSurface.bgHover;
    if (themePalette.darkSurface?.bgActive) variables["--darkSurface-bgActive"] = themePalette.darkSurface.bgActive;
    if (themePalette.darkSurface?.text) variables["--darkSurface-text"] = themePalette.darkSurface.text;
    if (themePalette.darkSurface?.textMuted) variables["--darkSurface-textMuted"] = themePalette.darkSurface.textMuted;
    if (themePalette.darkSurface?.accent) variables["--darkSurface-accent"] = themePalette.darkSurface.accent;
    if (themePalette.darkSurface?.accentLight) variables["--darkSurface-accentLight"] = themePalette.darkSurface.accentLight;
    if (themePalette.darkSurface?.border) variables["--darkSurface-border"] = themePalette.darkSurface.border;

    // Temporary shim colors
    if (themePalette.temporary?.background?.w10) variables["--temporary-background-w10"] = themePalette.temporary.background.w10;
    if (themePalette.temporary?.primary?.wMain) variables["--temporary-primary-wMain"] = themePalette.temporary.primary.wMain;

    return variables;
}

function generateThemeVariables(themePalette: ThemePalette): Record<string, string> {
    const variables = paletteToCSSVariables(themePalette);
    const fallbackVars = generateFallbackVariables(themePalette);
    Object.assign(variables, fallbackVars);

    return variables;
}

function getInitialTheme(): "light" | "dark" {
    const storedTheme = localStorage.getItem(LOCAL_STORAGE_KEY);
    if (storedTheme === "dark" || storedTheme === "light") {
        return storedTheme;
    }

    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
    }

    return "light";
}

function applyThemeToDOM(themePalette: ThemePalette, theme: "light" | "dark"): void {
    const variables = generateThemeVariables(themePalette);
    const root = document.documentElement;

    for (const [property, value] of Object.entries(variables)) {
        root.style.setProperty(property, value);
    }

    requestAnimationFrame(() => {
        if (process.env.NODE_ENV === "development") {
            console.log(`Applying ${theme} theme with palette`);
        }
        root.classList.remove("light", "dark");
        localStorage.setItem(LOCAL_STORAGE_KEY, theme);
    });
}

interface ThemeProviderProps {
    children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
    const [currentTheme, setCurrentTheme] = useState<"light" | "dark">(() => {
        return getInitialTheme();
    });

    const themePalette: ThemePalette = useMemo(() => (currentTheme === "dark" ? solaceDarkLegacy : solace), [currentTheme]);

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
        document.documentElement.classList.remove("light", "dark");
        applyThemeToDOM(themePalette, currentTheme);
    }, [currentTheme, themePalette]);

    return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
};
