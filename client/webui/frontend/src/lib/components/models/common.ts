import type { ModelConfig } from "@/lib/api/models/types";

export const DEFAULT_MODEL_ALIASES = ["general", "planning"];

/**
 * Returns true if the model has a real provider configured (not a placeholder).
 * Default models (general, planning) are seeded with null provider until configured.
 */
export const isModelConfigured = (model: ModelConfig): boolean => {
    return !!model.provider;
};

import { PROVIDER_DISPLAY_NAMES, AUTH_TYPE_LABELS } from "./modelProviderUtils";

// Re-export from single source of truth
export { PROVIDER_DISPLAY_NAMES, AUTH_TYPE_LABELS };

/**
 * Returns the human-readable display name for a provider, or null if not configured.
 * e.g., "openai" → "OpenAI", null → null
 */
export const getProviderDisplayName = (provider: string | null | undefined): string | null => {
    if (!provider) return null;
    return PROVIDER_DISPLAY_NAMES[provider] || provider;
};

/**
 * Strip LiteLLM provider prefix from model name for display purposes.
 * LiteLLM prefixes model names with the provider routing path (e.g., "openai/", "anthropic/").
 * e.g., "openai/gpt-4o" → "gpt-4o", "anthropic/claude-sonnet" → "claude-sonnet"
 */
export const getDisplayModelName = (modelName: string | null | undefined): string => {
    if (!modelName) return "";
    const slashIndex = modelName.indexOf("/");
    if (slashIndex > 0 && slashIndex < modelName.length - 1) {
        return modelName.substring(slashIndex + 1);
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
