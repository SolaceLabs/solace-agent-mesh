import { useQuery } from "@tanstack/react-query";

import { modelKeys } from "./keys";
import { fetchModelConfigs, fetchModelConfigStatus } from "./service";

/**
 * Hook to fetch all model configurations.
 * Uses React Query to manage loading, error, and cache states.
 */
export function useModelConfigs() {
    return useQuery({
        queryKey: modelKeys.lists(),
        queryFn: fetchModelConfigs,
        refetchOnMount: "always",
        retry: 0,
    });
}

/**
 * Hook to check if default LLM models are configured.
 * Fetches once and caches indefinitely for the session.
 */
export function useModelConfigStatus() {
    return useQuery({
        queryKey: modelKeys.status(),
        queryFn: fetchModelConfigStatus,
        staleTime: Infinity,
        refetchOnWindowFocus: false,
        retry: 1,
    });
}
