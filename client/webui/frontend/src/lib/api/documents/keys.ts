/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const documentKeys = {
    all: ["documents"] as const,
    content: (projectId: string, filename: string) => [...documentKeys.all, "content", projectId, filename] as const,
};
