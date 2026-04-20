/**
 * API functions for model configuration management.
 */

import { api } from "@/lib/api";
import type { ModelConfig, ModelConfigStatus } from "./types";

export interface ModelData {
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
 * Fetch a single model configuration by ID.
 */
export async function fetchModelById(id: string): Promise<ModelConfig> {
    const response = await api.platform.get(`/api/v1/platform/models/${encodeURIComponent(id)}`);
    return response.data;
}

/**
 * Fetch supported models for a specific provider.
 *
 * Two modes:
 * 1. Editing (modelId provided): Uses stored credentials from database
 * 2. Creating (credentials provided): Uses credentials from request
 */
export async function fetchSupportedModelsByProvider(
    provider: string,
    modelId?: string,
    options?: {
        apiBase?: string;
        authConfig?: Record<string, unknown>;
        modelParams?: Record<string, unknown>;
    }
): Promise<Array<{ id: string; label: string }>> {
    const body: Record<string, unknown> = {};

    // Pass modelId for stored credential fallback (editing mode)
    if (modelId) {
        body.modelId = modelId;
    }

    // Pass request credentials — server merges with stored when both provided
    if (options?.authConfig) {
        body.authConfig = options.authConfig;
    }
    if (options?.apiBase != null) {
        body.apiBase = options.apiBase;
    }
    if (options?.modelParams != null) {
        body.modelParams = options.modelParams;
    }

    const response = await api.platform.post(`/api/v1/platform/providers/${encodeURIComponent(provider)}/models`, body);
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
export async function updateModelConfig(id: string, data: ModelData): Promise<ModelConfig> {
    const response = await api.platform.patch(`/api/v1/platform/models/${encodeURIComponent(id)}`, data);
    return response.data;
}

/**
 * Delete a model configuration by ID.
 */
export async function deleteModel(id: string): Promise<void> {
    await api.platform.delete(`/api/v1/platform/models/${encodeURIComponent(id)}`);
}

export interface TestConnectionRequest {
    modelId?: string;
    provider?: string;
    modelName?: string;
    apiBase?: string;
    authConfig: Record<string, unknown>;
    modelParams: Record<string, unknown>;
}

export interface TestConnectionResponse {
    success: boolean;
    message: string;
}

/**
 * Test a model configuration connection.
 *
 * Uses POST /models?validateOnly=true to test connectivity without persisting.
 */
export async function testModelConnection(data: TestConnectionRequest): Promise<TestConnectionResponse> {
    const response = await api.platform.post("/api/v1/platform/models?validateOnly=true", data);
    return response.data;
}

/**
 * Fetch supported advanced parameters for a model.
 *
 * Uses litellm's internal registry — no credentials needed.
 * Returns a list of parameter names the model supports.
 * Empty list means litellm doesn't recognize the model (no warnings shown).
 */
export async function fetchSupportedParams(provider: string, modelName: string): Promise<string[]> {
    const response = await api.platform.post(`/api/v1/platform/providers/${encodeURIComponent(provider)}/params`, { modelName });
    return response.data?.supportedParams || [];
}

/**
 * Check if default LLM models are configured.
 */
export async function fetchModelConfigStatus(): Promise<ModelConfigStatus> {
    const response = await api.platform.get("/api/v1/platform/models/status");
    return response.data;
}
