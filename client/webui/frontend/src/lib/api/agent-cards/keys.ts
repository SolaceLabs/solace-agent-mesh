/**
 * Query keys for React Query caching and invalidation
 * Following the pattern: ['entity', ...filters/ids]
 */
export const agentCardKeys = {
    all: ["agent-cards"] as const,
    lists: () => [...agentCardKeys.all, "list"] as const,
};
