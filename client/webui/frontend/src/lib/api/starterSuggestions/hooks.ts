import { useQuery } from "@tanstack/react-query";
import { starterSuggestionsKeys } from "./keys";
import * as starterSuggestionsService from "./service";

/**
 * Hook to fetch LLM-generated starter card suggestions.
 * Uses a long staleTime (5 min) since suggestions don't change frequently.
 */
export function useStarterSuggestions() {
    return useQuery({
        queryKey: starterSuggestionsKeys.suggestions(),
        queryFn: starterSuggestionsService.fetchStarterSuggestions,
        staleTime: 5 * 60 * 1000, // 5 minutes
        gcTime: 10 * 60 * 1000, // 10 minutes garbage collection
        retry: 1, // Only retry once on failure
        refetchOnWindowFocus: false,
    });
}
