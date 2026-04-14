import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { agentCardKeys } from "@/lib/api/agent-cards/keys";
import { modelKeys } from "./keys";
import { createModelConfig, deleteModel, fetchModelConfigs, fetchModelConfigStatus, fetchSupportedModelsByProvider, updateModelConfig } from "./service";

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
 * Hook to create a new model configuration.
 * Invalidates model list and status caches so the UI reflects the new state
 * (e.g. banner dismisses, chat input enables) without a page refresh.
 */
export function useCreateModel() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: Parameters<typeof createModelConfig>[0]) => createModelConfig(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
            queryClient.invalidateQueries({ queryKey: modelKeys.status() });
            queryClient.invalidateQueries({ queryKey: agentCardKeys.lists() });
        },
    });
}

/**
 * Hook to update an existing model configuration.
 * Invalidates model list and status caches on success.
 */
export function useUpdateModel() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateModelConfig>[1] }) => updateModelConfig(id, data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
            queryClient.invalidateQueries({ queryKey: modelKeys.status() });
            queryClient.invalidateQueries({ queryKey: agentCardKeys.lists() });
        },
    });
}

/**
 * Hook to delete a model configuration by ID.
 * Invalidates both list and status caches — deleting a model may change configured state.
 */
export function useDeleteModel() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (id: string) => deleteModel(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: modelKeys.lists() });
            queryClient.invalidateQueries({ queryKey: modelKeys.status() });
            queryClient.invalidateQueries({ queryKey: agentCardKeys.lists() });
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
