/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const peopleKeys = {
    all: ["people"] as const,
    search: (query: string) => [...peopleKeys.all, "search", query] as const,
};
