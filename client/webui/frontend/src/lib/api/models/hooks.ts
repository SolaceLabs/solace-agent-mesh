import { useQuery } from "@tanstack/react-query";

import { modelKeys } from "./keys";
import { fetchModelConfigs } from "./service";

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
