import { useEffect, useMemo } from "react";
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { sessionKeys } from "./keys";
import * as sessionService from "./service";
import { getSessionContextUsage, compactSession } from "./context-usage";
import type { CompactSessionRequest, CompactSessionResponse, ContextUsage } from "@/lib/types";
import { fetchModelConfigs } from "@/lib/api/models/service";
import type { ModelConfig } from "@/lib/api/models/types";
import { MAX_RECENT_CHATS } from "@/lib/constants/ui";

/**
 * Hook to fetch recent sessions for the navigation sidebar.
 * Automatically invalidates on session events (new session, session updated, session moved, title updated).
 */
export function useRecentSessions(maxItems: number = MAX_RECENT_CHATS) {
    const queryClient = useQueryClient();

    // Set up event listeners for automatic invalidation
    useEffect(() => {
        const handleSessionEvent = () => {
            queryClient.invalidateQueries({ queryKey: sessionKeys.recent(maxItems) });
        };

        const events = ["new-chat-session", "session-updated", "session-title-updated", "background-task-completed"];
        events.forEach(e => window.addEventListener(e, handleSessionEvent));
        return () => events.forEach(e => window.removeEventListener(e, handleSessionEvent));
    }, [maxItems, queryClient]);

    return useQuery({
        queryKey: sessionKeys.recent(maxItems),
        queryFn: () => sessionService.getRecentSessions(maxItems),
        refetchOnMount: "always",
    });
}

/**
 * Hook to fetch paginated sessions with infinite scroll support.
 * Automatically invalidates on session events (new session, session updated, title updated, background task completed).
 */
export function useInfiniteSessions(pageSize: number = 20, source?: string) {
    const queryClient = useQueryClient();

    useEffect(() => {
        const invalidate = () => queryClient.invalidateQueries({ queryKey: sessionKeys.lists() });
        const events = ["new-chat-session", "session-updated", "session-title-updated", "background-task-completed"];
        events.forEach(e => window.addEventListener(e, invalidate));
        return () => events.forEach(e => window.removeEventListener(e, invalidate));
    }, [queryClient]);

    return useInfiniteQuery({
        queryKey: [...sessionKeys.lists(), "infinite", pageSize, source],
        queryFn: ({ pageParam }) => sessionService.getPaginatedSessions(pageParam, pageSize, source),
        getNextPageParam: lastPage => lastPage.meta.pagination.nextPage ?? undefined,
        initialPageParam: 1,
        refetchOnMount: "always",
    });
}

/**
 * Mark a session as viewed — clears the "unseen updates" indicator.
 * Optimistically patches `lastViewedAt` into cached session lists so the dot
 * disappears immediately.
 */
export function useMarkSessionViewed() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (sessionId: string) => sessionService.markSessionViewed(sessionId),
        onSuccess: ({ lastViewedAt }, sessionId) => {
            const patch = (session: { id: string; lastViewedAt?: number | null }) => (session.id === sessionId ? { ...session, lastViewedAt } : session);

            // Patch any cached list/infinite variants. `sessionKeys.lists()` is a
            // prefix of `sessionKeys.recent(...)` and the infinite list key, so
            // setQueriesData's partial-match filter covers both shapes.
            queryClient.setQueriesData<{ id: string; lastViewedAt?: number | null }[]>({ queryKey: sessionKeys.lists() }, data => {
                if (!data) return data;
                if (Array.isArray(data)) return data.map(patch);
                const paged = data as unknown as { pages?: { data: { id: string; lastViewedAt?: number | null }[] }[] };
                if (paged?.pages) {
                    return {
                        ...paged,
                        pages: paged.pages.map(p => ({ ...p, data: p.data.map(patch) })),
                    } as unknown as { id: string; lastViewedAt?: number | null }[];
                }
                return data;
            });
        },
    });
}

/**
 * Mutation to fetch chat tasks for a session (used in rename-with-AI flow).
 */
export function useRenameSessionWithAI() {
    return useMutation({
        mutationFn: async (sessionId: string) => {
            return sessionService.getSessionChatTasks(sessionId);
        },
    });
}

/**
 * Hook to fetch context window usage for a session. Returns null data silently
 * on fetch failure so the indicator can hide rather than surface an error.
 *
 * The context-window limit (`maxInputTokens`) is composed client-side from
 * two sources, in priority order:
 *   1. Platform-service `model_configurations` table (authoritative when set)
 *   2. Whatever the gateway returns (agent-stamped value or LiteLLM registry)
 */
export function useSessionContextUsage(sessionId: string | undefined, agentName?: string) {
    const usageQuery = useQuery<ContextUsage | null>({
        queryKey: sessionId ? sessionKeys.contextUsage(sessionId, agentName) : ["sessions", "context-usage", "disabled"],
        queryFn: async () => {
            if (!sessionId) return null;
            try {
                return await getSessionContextUsage(sessionId, undefined, agentName);
            } catch (err) {
                if (process.env.NODE_ENV === "development") {
                    console.warn("useSessionContextUsage: failed to fetch usage", err);
                }
                return null;
            }
        },
        enabled: !!sessionId,
    });

    // Cached long — model configs change rarely. Swallow errors so deployments
    // without a reachable platform service (e.g. community standalone with
    // the platform endpoint disabled) simply fall back to the gateway's value.
    const modelsQuery = useQuery<ModelConfig[]>({
        queryKey: ["platform", "models", "for-context-usage"],
        queryFn: async () => {
            try {
                return await fetchModelConfigs();
            } catch {
                return [];
            }
        },
        staleTime: 5 * 60 * 1000,
        enabled: !!sessionId,
    });

    const merged = useMemo<ContextUsage | null>(() => {
        const usage = usageQuery.data;
        if (!usage) return usage ?? null;
        // Match by modelName first (the raw name agents emit into
        // token_usage_details.by_model), then by alias. Only consider rows
        // with a configured max_input_tokens — duplicates on the same
        // model_name with NULL values must not win.
        const configuredMax = modelsQuery.data?.find(m => m.maxInputTokens != null && (m.modelName === usage.model || m.alias === usage.model))?.maxInputTokens ?? null;
        const effectiveMax = configuredMax ?? usage.maxInputTokens;
        const usagePercentage = effectiveMax && usage.currentContextTokens > 0 ? Math.min(100, Math.round((usage.currentContextTokens / effectiveMax) * 1000) / 10) : 0;
        return { ...usage, maxInputTokens: effectiveMax, usagePercentage };
    }, [usageQuery.data, modelsQuery.data]);

    return { ...usageQuery, data: merged };
}

/**
 * Mutation to manually compact a session. Invalidates the session's chat tasks
 * (so the backend-persisted compaction_notification task renders) and context
 * usage (so the post-compaction drop is reflected).
 */
export function useCompactSession(sessionId: string) {
    const queryClient = useQueryClient();
    return useMutation<CompactSessionResponse, Error, CompactSessionRequest | undefined>({
        mutationFn: (request?: CompactSessionRequest) => compactSession(sessionId, request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: sessionKeys.chatTasks(sessionId) });
            queryClient.invalidateQueries({ queryKey: [...sessionKeys.detail(sessionId), "context-usage"] });
        },
    });
}
