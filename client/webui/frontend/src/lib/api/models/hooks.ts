import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { modelKeys } from "./keys";
import { deleteModel, fetchModelConfigs } from "./service";

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
