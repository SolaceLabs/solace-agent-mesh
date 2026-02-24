import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

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
        window.addEventListener("session-moved", handleSessionEvent);
        window.addEventListener("session-title-updated", handleSessionEvent);

        return () => {
            window.removeEventListener("new-chat-session", handleSessionEvent);
            window.removeEventListener("session-updated", handleSessionEvent);
            window.removeEventListener("session-moved", handleSessionEvent);
            window.removeEventListener("session-title-updated", handleSessionEvent);
        };
    }, [maxItems, queryClient]);

    return useQuery({
        queryKey: sessionKeys.recent(maxItems),
        queryFn: () => sessionService.getRecentSessions(maxItems),
        refetchOnMount: "always",
    });
}
