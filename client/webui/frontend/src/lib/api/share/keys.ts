/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const shareKeys = {
    all: ["shares"] as const,
    links: () => [...shareKeys.all, "link"] as const,
    link: (sessionId: string) => [...shareKeys.links(), sessionId] as const,
    lists: () => [...shareKeys.all, "list"] as const,
    list: (filters?: { page?: number; pageSize?: number; search?: string }) => [...shareKeys.lists(), { filters }] as const,
    users: (shareId: string) => [...shareKeys.all, "users", shareId] as const,
    sharedWithMe: () => [...shareKeys.all, "shared-with-me"] as const,
    view: (shareId: string) => [...shareKeys.all, "view", shareId] as const,
};
