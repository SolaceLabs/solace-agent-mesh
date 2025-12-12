/**
 * Model context window limits configuration
 * Based on ASSIST project's token limits
 * Values are slightly reduced from max to account for system prompts and safety margins
 */

export interface ModelContextLimits {
    [modelName: string]: number;
}

const openAIModels: ModelContextLimits = {
    "o4-mini": 200000,
    "o3-mini": 195000,
    o3: 200000,
    o1: 195000,
    "o1-mini": 127500,
    "o1-preview": 127500,
    "gpt-4": 8187,
    "gpt-4-0613": 8187,
    "gpt-4-32k": 32758,
    "gpt-4-32k-0314": 32758,
    "gpt-4-32k-0613": 32758,
    "gpt-4-1106": 127500,
    "gpt-4-0125": 127500,
    "gpt-4.1": 1047576,
    "gpt-4.1-mini": 1047576,
    "gpt-4.1-nano": 1047576,
    "gpt-5": 400000,
    "gpt-5-mini": 400000,
    "gpt-5-nano": 400000,
    "gpt-4o": 127500,
    "gpt-4o-mini": 127500,
    "gpt-4o-2024-05-13": 127500,
    "gpt-4o-2024-08-06": 127500,
    "gpt-4-turbo": 127500,
    "gpt-4-vision": 127500,
    "gpt-3.5-turbo": 16375,
    "gpt-3.5-turbo-0613": 4092,
    "gpt-3.5-turbo-0301": 4092,
    "gpt-3.5-turbo-16k": 16375,
    "gpt-3.5-turbo-16k-0613": 16375,
    "gpt-3.5-turbo-1106": 16375,
    "gpt-3.5-turbo-0125": 16375,
};

const anthropicModels: ModelContextLimits = {
    "claude-": 100000,
    "claude-instant": 100000,
    "claude-2": 100000,
    "claude-2.1": 200000,
    "claude-3": 200000,
    "claude-3-haiku": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-opus": 200000,
    "claude-3.5-haiku": 200000,
    "claude-haiku-4-5": 200000,
    "claude-3-5-sonnet": 200000,
    "claude-3.5-sonnet": 200000,
    "claude-3-7-sonnet": 200000,
    "claude-3.7-sonnet": 200000,
    "claude-3-5-sonnet-latest": 200000,
    "claude-3.5-sonnet-latest": 200000,
    "claude-sonnet-4": 200000,
    "claude-sonnet-4-0": 200000,
    "claude-sonnet-4-5": 200000,
    "claude-sonnet-4-5-20250929": 200000,
    "anthropic.claude-sonnet-4-5": 200000,
    "anthropic.claude-haiku-4-5": 200000,
    "claude-4-sonnet": 200000,
    "claude-4-sonnet-20250514": 200000,
    "claude-opus-4": 200000,
    "claude-opus-4-0": 200000,
    "claude-4-opus": 200000,
    "claude-4-opus-20250514": 200000,
    "claude-4": 200000,
};

const googleModels: ModelContextLimits = {
    gemini: 30720,
    "gemini-pro-vision": 12288,
    "gemini-exp": 2000000,
    "gemini-2.5": 1000000,
    "gemini-2.5-flash": 1000000,
    "gemini-2.5-flash-lite-preview-06-17": 1000000,
    "gemini-2.5-flash-lite": 1000000,
    "gemini-2.5-pro": 1000000,
    "gemini-2.0": 2000000,
    "gemini-2.0-flash": 1000000,
    "gemini-2.0-flash-lite": 1000000,
    "gemini-1.5": 1000000,
    "gemini-1.5-flash": 1000000,
    "gemini-1.5-flash-8b": 1000000,
};

const deepseekModels: ModelContextLimits = {
    "deepseek-reasoner": 63000,
    deepseek: 63000,
};

const metaModels: ModelContextLimits = {
    "llama3.1": 127500,
    "llama3.2": 127500,
    "llama3.3": 127500,
    llama3: 8000,
    llama2: 4000,
};

// Aggregate all models
const allModels: ModelContextLimits = {
    ...openAIModels,
    ...anthropicModels,
    ...googleModels,
    ...deepseekModels,
    ...metaModels,
};

// Default context limit for unknown models
const DEFAULT_CONTEXT_LIMIT = 128000;

/**
 * Finds the first matching pattern in the model name
 */
function findMatchingPattern(modelName: string, limitsMap: ModelContextLimits): string | null {
    const keys = Object.keys(limitsMap);
    // Check from most specific to least specific
    for (let i = keys.length - 1; i >= 0; i--) {
        const modelKey = keys[i];
        if (modelName.toLowerCase().includes(modelKey.toLowerCase())) {
            return modelKey;
        }
    }
    return null;
}

/**
 * Get the context window limit for a given model
 * @param modelName - The model name to look up
 * @returns The context limit in tokens
 */
export function getModelContextLimit(modelName: string): number {
    if (!modelName || typeof modelName !== "string") {
        return DEFAULT_CONTEXT_LIMIT;
    }

    // Direct match
    if (allModels[modelName]) {
        return allModels[modelName];
    }

    // Pattern matching
    const matchedPattern = findMatchingPattern(modelName, allModels);
    if (matchedPattern) {
        return allModels[matchedPattern];
    }

    // Default fallback
    return DEFAULT_CONTEXT_LIMIT;
}

/**
 * Format token count with K/M suffix
 */
export function formatTokenCount(tokens: number): string {
    if (tokens >= 1000000) {
        return `${(tokens / 1000000).toFixed(1)}M`;
    }
    if (tokens >= 1000) {
        return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
}

/**
 * Calculate percentage of context used
 */
export function calculateContextPercentage(usedTokens: number, totalTokens: number): number {
    if (totalTokens === 0) return 0;
    return Math.min(100, Math.round((usedTokens / totalTokens) * 100));
}

/**
 * Get color based on usage percentage
 */
export function getUsageColor(percentage: number): string {
    if (percentage >= 90) return "text-red-600 dark:text-red-400";
    if (percentage >= 75) return "text-orange-600 dark:text-orange-400";
    if (percentage >= 50) return "text-yellow-600 dark:text-yellow-400";
    return "text-green-600 dark:text-green-400";
}

/**
 * Get background color based on usage percentage
 */
export function getUsageBgColor(percentage: number): string {
    if (percentage >= 90) return "bg-red-100 dark:bg-red-900/20";
    if (percentage >= 75) return "bg-orange-100 dark:bg-orange-900/20";
    if (percentage >= 50) return "bg-yellow-100 dark:bg-yellow-900/20";
    return "bg-gray-100 dark:bg-gray-800/50";
}
