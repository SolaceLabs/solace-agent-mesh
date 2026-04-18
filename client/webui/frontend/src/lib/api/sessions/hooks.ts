import { useEffect } from "react";
import { useQuery, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { sessionKeys } from "./keys";
import * as sessionService from "./service";
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
