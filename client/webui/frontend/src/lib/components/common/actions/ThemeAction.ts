import type { ExecutableAction, ActionContext } from "./types";

type ThemeMode = "light" | "dark" | "toggle";

/**
 * Theme action for directly changing the application theme
 */
export class ThemeAction implements ExecutableAction {
    id: string;
    label: string;
    description?: string;
    keywords?: string[];
    category = "theme";
    private mode: ThemeMode;

    constructor(config: { id: string; label: string; mode: ThemeMode; description?: string; keywords?: string[] }) {
        this.id = config.id;
        this.label = config.label;
        this.mode = config.mode;
        this.description = config.description;
        this.keywords = config.keywords;
    }

    execute(context: ActionContext): void {
        const { toggleTheme, setTheme } = context;

        if (!toggleTheme || !setTheme) {
            console.error("Theme functions not provided in context");
            return;
        }

        if (this.mode === "toggle") {
            toggleTheme();
        } else {
            setTheme(this.mode);
        }
    }
}

/**
 * Factory function to create theme actions
 */
export function createThemeAction(config: { id: string; label: string; mode: ThemeMode; description?: string; keywords?: string[] }): ThemeAction {
    return new ThemeAction(config);
}
