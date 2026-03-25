/**
 * API functions for model configuration management.
 */

import { api } from "@/lib/api";
import type { ModelConfig } from "./types";

/**
 * Fetch all model configurations.
 */
export async function fetchModelConfigs(): Promise<ModelConfig[]> {
    const response = await api.platform.get("/api/v1/platform/models");
    return response.data || [];
}

/**
 * Delete a model configuration by alias.
 */
export async function deleteModel(alias: string): Promise<void> {
    await api.platform.delete(`/api/v1/platform/models/${alias}`);
}
