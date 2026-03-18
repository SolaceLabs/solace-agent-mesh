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

interface ModelResponse {
    id?: string;
    data?: Array<{ id?: string; name?: string; label?: string }>;
    models?: Array<{ id: string; name?: string }>;
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
 * For openai_compatible providers, optionally pass modelAlias to use stored credentials (edit mode).
 */
export async function fetchSupportedModelsByProvider(provider: string, modelAlias?: string): Promise<Array<{ id: string; label: string }>> {
    let url = `/api/v1/platform/supported-models/${provider}`;
    if (modelAlias) {
        url += `?model_alias=${encodeURIComponent(modelAlias)}`;
    }
    const response = await api.platform.get(url);
    return response.data || [];
}

/**
 * Fetch models from an OpenAI-compatible endpoint directly from the browser.
 * Used for new model creation before saving.
 */
export async function fetchModelsFromCustomEndpoint(apiBase: string, authType: string, apiKey?: string, clientId?: string, clientSecret?: string, tokenUrl?: string): Promise<Array<{ id: string; label: string }>> {
    try {
        const baseUrl = apiBase.endsWith("/") ? apiBase : `${apiBase}/`;

        // Prepare headers based on auth type
        const headers: HeadersInit = {
            "Content-Type": "application/json",
        };

        if (authType === "apikey" && apiKey) {
            headers["Authorization"] = `Bearer ${apiKey}`;
        } else if (authType === "oauth2" && clientId && clientSecret && tokenUrl) {
            // For OAuth2, we'd need to get a token from tokenUrl first
            // For now, we can't support OAuth2 directly from browser without a proxy
            console.warn("OAuth2 model fetching not supported directly from browser");
            return [];
        }

        const response = await fetch(`${baseUrl}v1/models`, {
            method: "GET",
            headers,
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch models: ${response.status}`);
        }

        const data = await response.json();

        // Handle different response formats
        const modelResponse = data as ModelResponse;
        let models: Array<{ id: string; label: string }> = [];

        if (modelResponse.data && Array.isArray(modelResponse.data)) {
            // Extract id from objects, use label if available, fall back to id as label
            models = modelResponse.data
                .filter(item => item.id ?? item.name)
                .map(item => ({
                    id: (item.id ?? item.name) as string,
                    label: item.label ?? item.id ?? item.name ?? "",
                }));
        } else if (modelResponse.models && Array.isArray(modelResponse.models)) {
            models = modelResponse.models
                .filter(model => model.id ?? model.name)
                .map(model => ({
                    id: model.id ?? (model.name as string),
                    label: model.id ?? (model.name as string),
                }));
        } else if (Array.isArray(data)) {
            const arrayData = data as Array<{ id?: string; name?: string }>;
            models = arrayData
                .filter(model => model.id ?? model.name)
                .map(model => ({
                    id: (model.id ?? model.name) as string,
                    label: (model.id ?? model.name) as string,
                }));
        }

        return models;
    } catch (error) {
        console.error("Error fetching models from custom endpoint:", error);
        return [];
    }
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
