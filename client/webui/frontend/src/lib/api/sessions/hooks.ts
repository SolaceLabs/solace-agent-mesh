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

        window.addEventListener("new-chat-session", handleSessionEvent);
        window.addEventListener("session-updated", handleSessionEvent);
        window.addEventListener("session-title-updated", handleSessionEvent);

        return () => {
            window.removeEventListener("new-chat-session", handleSessionEvent);
            window.removeEventListener("session-updated", handleSessionEvent);
            window.removeEventListener("session-title-updated", handleSessionEvent);
        };
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
 * Mutation to fetch chat tasks for a session (used in rename-with-AI flow).
 */
export function useRenameSessionWithAI() {
    return useMutation({
        mutationFn: async (sessionId: string) => {
            return sessionService.getSessionChatTasks(sessionId);
        },
    });
}
