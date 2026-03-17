/**
 * Model configuration types for LLM model management.
 */

export interface ModelConfig {
    id: string;
    alias: string;
    provider: string;
    modelName: string;
    apiBase: string | null;
    hasCredentials: boolean;
    authType: string | null;
    modelParams: Record<string, unknown>;
    description: string | null;
    createdBy: string;
    updatedBy: string;
    createdTime: number;
    updatedTime: number;
}
