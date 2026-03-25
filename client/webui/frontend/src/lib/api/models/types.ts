/**
 * Model configuration types for LLM model management.
 */

export interface ModelConfig {
    id: string;
    alias: string;
    provider: string;
    modelName: string;
    apiBase: string | null;
    authType: string | null;
    authConfig: Record<string, unknown>;
    modelParams: Record<string, unknown>;
    description: string | null;
    createdBy: string;
    updatedBy: string;
    createdTime: number;
    updatedTime: number;
}

export interface ModelConfigurationListResponse {
    data: ModelConfig[];
    total: number;
}

export interface ModelConfigStatus {
    configured: boolean;
}
