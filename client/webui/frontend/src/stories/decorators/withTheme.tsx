import type { Decorator, StoryContext, StoryFn } from "@storybook/react";
import { useEffect } from "react";

/**
 * Theme wrapper component that syncs Storybook's theme with the app's ThemeProvider
 */
function ThemeWrapper({ theme, children }: { theme: string; children: React.ReactNode }) {
    useEffect(() => {
        // Write to the same localStorage key that ThemeProvider uses
        localStorage.setItem("sam-theme", theme);

        // Also sync background colour
        document.body.style.backgroundColor = "var(--background)";
    }, [theme]);

    return <>{children}</>;
}

/**
 * A Storybook decorator that syncs Storybook's theme global with the app's theme system.
 * This bridges the Storybook toolbar theme toggle to the ThemeProvider by writing to
 * localStorage and dispatching a custom event.
 */
export const withTheme: Decorator = (Story: StoryFn, context: StoryContext) => {
    const theme = context.globals.theme || "light";

    return <ThemeWrapper theme={theme}>{Story(context.args, context)}</ThemeWrapper>;
};
