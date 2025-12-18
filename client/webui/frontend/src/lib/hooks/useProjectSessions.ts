import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { Session } from "@/lib/types";

interface UseProjectSessionsReturn {
    sessions: Session[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

export const useProjectSessions = (projectId?: string | null): UseProjectSessionsReturn => {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchSessions = useCallback(async () => {
        if (!projectId) {
            setSessions([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const data = await api.webui.get(`/api/v1/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`);
            setSessions(data.data || []);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch sessions.";
            setError(errorMessage);
            setSessions([]);
        } finally {
            setIsLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchSessions();

        // Listen for session-moved events to refresh the list
        const handleSessionMoved = () => {
            fetchSessions();
        };

        // Listen for new-chat-session events to refresh the list
        const handleNewSession = () => {
            fetchSessions();
        };

        window.addEventListener("session-moved", handleSessionMoved);
        window.addEventListener("new-chat-session", handleNewSession);

        return () => {
            window.removeEventListener("session-moved", handleSessionMoved);
            window.removeEventListener("new-chat-session", handleNewSession);
        };
    }, [fetchSessions]);

    return {
        sessions,
        isLoading,
        error,
        refetch: fetchSessions,
    };
};
