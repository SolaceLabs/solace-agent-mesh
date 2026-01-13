/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const peopleKeys = {
    all: ["people"] as const,
    searches: () => [...peopleKeys.all, "search"] as const,
    search: (query: string, limit?: number) => [...peopleKeys.searches(), { query, limit }] as const,
};
