/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const modelKeys = {
    all: ["models"] as const,
    lists: () => [...modelKeys.all, "list"] as const,
    status: () => [...modelKeys.all, "status"] as const,
};
