import type { ExecutableAction } from "./types";

export type SettingsSection = "general" | "speech" | "about";

/**
 * Settings action for opening the settings dialog
 * Dispatches a custom event to trigger the settings dialog
 */
export class SettingsAction implements ExecutableAction {
    id: string;
    label: string;
    description?: string;
    keywords?: string[];
    category = "settings";
    private section?: SettingsSection;

    constructor(config: { id: string; label: string; section?: SettingsSection; description?: string; keywords?: string[] }) {
        this.id = config.id;
        this.label = config.label;
        this.section = config.section;
        this.description = config.description;
        this.keywords = config.keywords;
    }

    execute(): void {
        // Dispatch custom event to open settings dialog
        window.dispatchEvent(
            new CustomEvent("open-settings-dialog", {
                detail: { section: this.section },
            })
        );
    }
}

/**
 * Factory function to create settings actions
 */
export function createSettingsAction(config: { id: string; label: string; section?: SettingsSection; description?: string; keywords?: string[] }): SettingsAction {
    return new SettingsAction(config);
}
