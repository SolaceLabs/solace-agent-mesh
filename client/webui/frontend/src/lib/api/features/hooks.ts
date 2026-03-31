import { useQuery } from "@tanstack/react-query";

import { featureKeys } from "./keys";
import { fetchFeatureFlags } from "./service";

export function useFeatureFlags() {
    return useQuery({
        queryKey: featureKeys.list(),
        queryFn: fetchFeatureFlags,
        retry: 0,
        staleTime: Infinity,
    });
}
