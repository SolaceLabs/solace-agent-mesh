/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 *
 * List keys include `userId` so cached results from one user can never be
 * served to another. Existing `lists()` prefix-invalidations still match
 * because userId is appended after the "list" segment.
 */
export const sessionKeys = {
    all: ["sessions"] as const,
    lists: () => [...sessionKeys.all, "list"] as const,
    recent: (userId: string, maxItems: number) => [...sessionKeys.lists(), "recent", userId, maxItems] as const,
    infinite: (userId: string, pageSize: number, source?: string) => [...sessionKeys.lists(), "infinite", userId, pageSize, source] as const,
    details: () => [...sessionKeys.all, "detail"] as const,
    detail: (id: string) => [...sessionKeys.details(), id] as const,
    chatTasks: (id: string) => [...sessionKeys.detail(id), "chat-tasks"] as const,
    contextUsage: (id: string, agentName?: string) => [...sessionKeys.detail(id), "context-usage", agentName ?? null] as const,
};
