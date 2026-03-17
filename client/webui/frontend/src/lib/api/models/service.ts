/**
 * API functions for model configuration management.
 */

import { api } from "@SolaceLabs/solace-agent-mesh-ui";
import type { ModelConfig } from "./types";

/**
 * Fetch all model configurations.
 */
export async function fetchModelConfigs(): Promise<ModelConfig[]> {
    const response = await api.platform.get("/api/v1/platform/models");
    return response.data || [];
}
