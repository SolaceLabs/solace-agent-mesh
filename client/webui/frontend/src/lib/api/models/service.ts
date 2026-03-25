/**
 * API functions for model configuration management.
 */

import { api } from "@/lib/api";
import type { ModelConfig, ModelConfigStatus } from "./types";

/**
 * Fetch all model configurations.
 */
export async function fetchModelConfigs(): Promise<ModelConfig[]> {
    const response = await api.platform.get("/api/v1/platform/models");
    return response.data || [];
}

/**
 * Check if default LLM models are configured.
 */
export async function fetchModelConfigStatus(): Promise<ModelConfigStatus> {
    const response = await api.platform.get("/api/v1/platform/models/status");
    return response.data;
}
