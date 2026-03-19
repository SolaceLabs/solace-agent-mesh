/**
 * API functions for model configuration management.
 */

import { api } from "@/lib/api/client";
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
    const response = await api.platform.get(`/api/v1/platform/models/${alias}`);
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
        authType?: string;
        apiKey?: string;
        clientId?: string;
        clientSecret?: string;
        tokenUrl?: string;
    }
): Promise<Array<{ id: string; label: string }>> {
    const body: Record<string, unknown> = {
        provider,
    };

    if (modelAlias) {
        body.modelAlias = modelAlias;
    } else if (options?.authType) {
        // Creating mode - pass credentials
        body.authType = options.authType;

        if (options.apiBase) {
            body.apiBase = options.apiBase;
        }

        if (options.authType === "apikey" && options.apiKey) {
            body.apiKey = options.apiKey;
        } else if (options.authType === "oauth2") {
            if (options.clientId) body.clientId = options.clientId;
            if (options.clientSecret) body.clientSecret = options.clientSecret;
            if (options.tokenUrl) body.tokenUrl = options.tokenUrl;
        }
    }

    const response = await api.platform.post("/api/v1/platform/supported-models", body);
    return response.data || [];
}

/**
 * Fetch models from an OpenAI-compatible endpoint via the backend.
 * Used for new model creation with user-provided credentials.
 * Credentials are sent to the backend which queries the provider directly.
 */
export async function fetchModelsFromCustomEndpoint(apiBase: string, authType: string, apiKey?: string, clientId?: string, clientSecret?: string, tokenUrl?: string): Promise<Array<{ id: string; label: string }>> {
    return fetchSupportedModelsByProvider("openai_compatible", undefined, {
        apiBase,
        authType,
        apiKey,
        clientId,
        clientSecret,
        tokenUrl,
    });
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
    const response = await api.platform.put(`/api/v1/platform/models/${alias}`, data);
    return response.data;
}
