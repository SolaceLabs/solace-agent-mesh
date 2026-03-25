/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const featureKeys = {
    all: ["features"] as const,
    list: () => [...featureKeys.all, "list"] as const,
};
