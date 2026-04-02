/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const starterSuggestionsKeys = {
    all: ["starter-suggestions"] as const,
    suggestions: () => [...starterSuggestionsKeys.all, "list"] as const,
};
