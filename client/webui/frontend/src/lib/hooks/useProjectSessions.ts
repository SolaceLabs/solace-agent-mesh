import { useState, useEffect, useCallback } from "react";

import type { Session } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

interface UseProjectSessionsReturn {
    sessions: Session[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

/**
 * Custom hook to fetch sessions filtered by project_id.
 * @param projectId - The project ID to filter sessions by.
 * @returns Object containing sessions data, loading state, error state, and refetch function.
 */
export const useProjectSessions = (projectId?: string | null): UseProjectSessionsReturn => {
    const { configServerUrl } = useConfigContext();
    const [sessions, setSessions] = useState<Session[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchSessions = useCallback(async () => {
        if (!projectId) {
            setSessions([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);
        
        try {
            const url = `${apiPrefix}/sessions?project_id=${projectId}&pageNumber=1&pageSize=100`;
            const response = await authenticatedFetch(url, { credentials: "include" });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    detail: `Failed to fetch sessions. ${response.statusText}` 
                }));
                throw new Error(errorData.detail || `Failed to fetch sessions. ${response.statusText}`);
            }
            
            const data = await response.json();
            setSessions(data.data || []);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch sessions.";
            setError(errorMessage);
            setSessions([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix, projectId]);

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
