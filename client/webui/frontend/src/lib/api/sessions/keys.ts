/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const sessionKeys = {
    all: ["sessions"] as const,
    lists: () => [...sessionKeys.all, "list"] as const,
    list: (filters?: { pageNumber?: number; pageSize?: number }) => [...sessionKeys.lists(), { filters }] as const,
    recent: (maxItems: number) => [...sessionKeys.lists(), "recent", maxItems] as const,
    details: () => [...sessionKeys.all, "detail"] as const,
    detail: (id: string) => [...sessionKeys.details(), id] as const,
};
