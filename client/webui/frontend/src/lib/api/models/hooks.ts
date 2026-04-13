import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { modelKeys } from "./keys";
import { deleteModel, fetchModelConfigs, fetchModelConfigStatus, fetchSupportedModelsByProvider } from "./service";

export interface SupportedModelsQueryParams {
    provider: string;
    modelId?: string;
    apiBase?: string;
    authConfig?: Record<string, unknown>;
    modelParams?: Record<string, unknown>;
}

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
 * Hook to delete a model configuration by ID.
 */
export function useDeleteModel() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => deleteModel(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
        },
    });
}

/**
 * Hook to fetch supported models for a given provider + credential combination.
 */
export function useSupportedModels(params: SupportedModelsQueryParams | null) {
    return useQuery({
        queryKey: modelKeys.supportedModels(params),
        queryFn: () =>
            fetchSupportedModelsByProvider(params!.provider, params?.modelId, {
                apiBase: params?.apiBase,
                authConfig: params?.authConfig,
                modelParams: params?.modelParams,
            }),
        enabled: !!params,
        retry: 0,
        staleTime: 30_000,
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
