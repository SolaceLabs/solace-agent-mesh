import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { agentCardKeys } from "@/lib/api/agent-cards/keys";
import { modelKeys } from "./keys";
import { createModelConfig, deleteModel, fetchModelById, fetchModelConfigs, fetchModelConfigStatus, fetchSupportedModelsByProvider, testModelConnection, updateModelConfig } from "./service";
import type { TestConnectionRequest } from "./service";

export interface SupportedModelsQueryParams {
    provider: string;
    modelId?: string;
    apiBase?: string;
    authConfig?: Record<string, unknown>;
    modelParams?: Record<string, unknown>;
}

/**
 * Hook to fetch the list of model configurations.
 */
export function useModelConfigs() {
    return useQuery({
        queryKey: modelKeys.lists(),
        queryFn: fetchModelConfigs,
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
 */
export function useModelConfigStatus() {
    return useQuery({
        queryKey: modelKeys.status(),
        queryFn: fetchModelConfigStatus,
        retry: 1,
    });
}

/**
 * Hook to fetch a single model configuration by ID.
 */
export function useModelById(id: string | undefined) {
    return useQuery({
        queryKey: modelKeys.detail(id!),
        queryFn: () => fetchModelById(id!),
        enabled: !!id,
    });
}

/**
 * Hook to test a model connection before saving.
 */
export function useTestModelConnection() {
    return useMutation({
        mutationFn: (data: TestConnectionRequest) => testModelConnection(data),
    });
}
