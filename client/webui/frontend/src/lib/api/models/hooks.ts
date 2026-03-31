import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { modelKeys } from "./keys";
import { deleteModel, fetchModelConfigs, fetchModelConfigStatus } from "./service";

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
 * Hook to delete a model configuration by alias.
 */
export function useDeleteModel() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (alias: string) => deleteModel(alias),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
        },
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
