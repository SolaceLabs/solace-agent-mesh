import { api } from "@/lib/api";
import type { FeatureFlagInfo } from "./types";

export async function fetchFeatureFlags(): Promise<FeatureFlagInfo[]> {
    const response = await api.webui.get("/api/v1/config/features", {
        credentials: "include",
        headers: { Accept: "application/json" },
        fullResponse: true,
    });
    if (!response.ok) {
        throw new Error(`Features endpoint returned ${response.status}`);
    }
    return response.json();
}
