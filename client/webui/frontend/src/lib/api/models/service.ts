/**
 * API functions for model configuration management.
 */

import { api } from "@/lib/api";
import { AUTH_FIELDS } from "@/lib/components/models/modelProviderUtils";
import type { AuthType } from "@/lib/components/models/modelProviderUtils";
import type { ModelConfig } from "./types";

interface ModelData {
    alias: string;
    provider: string;
    modelName: string;
    apiBase: string | null;
    description: string | null;
    authType: string;
    authConfig: Record<string, unknown>;
    modelParams: Record<string, unknown>;
}

/**
 * Fetch all model configurations.
 */
export async function fetchModelConfigs(): Promise<ModelConfig[]> {
    const response = await api.platform.get("/api/v1/platform/models");
    return response.data || [];
}

/**
 * Fetch a single model configuration by alias.
 */
export async function fetchModelByAlias(alias: string): Promise<ModelConfig> {
    const response = await api.platform.get(`/api/v1/platform/models/${encodeURIComponent(alias)}`);
    return response.data;
}

/**
 * Fetch supported models for a specific provider.
 *
 * Two modes:
 * 1. Editing (modelAlias provided): Uses stored credentials from database
 * 2. Creating (credentials provided): Uses credentials from request
 */
export async function fetchSupportedModelsByProvider(
    provider: string,
    modelAlias?: string,
    options?: {
        apiBase?: string;
        authType?: AuthType;
        modelParams?: Record<string, unknown>;
    } & Record<string, unknown>
): Promise<Array<{ id: string; label: string }>> {
    const body: Record<string, unknown> = {
        provider,
    };

    if (modelAlias) {
        body.modelAlias = modelAlias;
    } else if (options?.authType) {
        // Creating mode - pass credentials
        body.authType = options.authType;

        if (options.apiBase != null) {
            body.apiBase = options.apiBase;
        }

        if (options.modelParams != null) {
            body.modelParams = options.modelParams;
        }

        // Copy auth fields for the selected auth type
        for (const field of AUTH_FIELDS[options.authType] ?? []) {
            const value = options[field.name];
            if (value != null) {
                body[field.name] = value;
            }
        }
    }

    const response = await api.platform.post("/api/v1/platform/supported-models", body);
    return response.data || [];
}

/**
 * Create a new model configuration.
 */
export async function createModelConfig(data: ModelData): Promise<ModelConfig> {
    const response = await api.platform.post("/api/v1/platform/models", data);
    return response.data;
}

/**
 * Update an existing model configuration.
 */
export async function updateModelConfig(alias: string, data: ModelData): Promise<ModelConfig> {
    const response = await api.platform.put(`/api/v1/platform/models/${encodeURIComponent(alias)}`, data);
    return response.data;
}
