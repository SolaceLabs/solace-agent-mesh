export const DEFAULT_MODEL_ALIASES = ["general", "planning"];

// Re-export from single source of truth
export { PROVIDER_DISPLAY_NAMES, AUTH_TYPE_LABELS } from "./modelProviderUtils";

/**
 * Strip provider prefix from model name for display purposes.
 * e.g., "openai/bedrock-claude-4-5-haiku" → "bedrock-claude-4-5-haiku"
 */
export const getDisplayModelName = (modelName: string): string => {
    if (!modelName) return "";
    if (modelName.startsWith("openai/")) {
        return modelName.substring(7);
    }
    return modelName;
};

/**
 * Convert alias to user-friendly display name for UI tables.
 * Only converts aliases for system-created models to title case.
 * User-created models show their original alias.
 * e.g., "audio_transcription" (system-created) → "Audio Transcription"
 * e.g., "my_custom_model" (user-created) → "my_custom_model"
 */
export const getDisplayAliasName = (alias: string, createdBy?: string): string => {
    if (!alias) return "";

    // Only convert to title case if created by system
    if (createdBy === "system") {
        return alias
            .split("_")
            .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
            .join(" ");
    }

    // Return original alias for user-created models
    return alias;
};
