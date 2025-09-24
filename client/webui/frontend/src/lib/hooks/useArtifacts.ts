import { useState, useEffect, useCallback, useRef } from "react";

import type { ArtifactInfo } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";
import { useProjectContext } from "@/lib/providers";

import { useConfigContext } from "./useConfigContext";

interface UseArtifactsReturn {
    artifacts: ArtifactInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

/**
 * Custom hook to fetch and manage artifact data
 * Automatically determines data source based on session and project context:
 * 1. If sessionId exists -> fetch from session artifacts
 * 2. Else if activeProject exists -> fetch from project artifacts  
 * 3. Else -> return empty array
 * 
 * @param sessionId - The session ID to fetch artifacts for (optional)
 * @returns Object containing artifacts data, loading state, error state, and refetch function
 */
export const useArtifacts = (sessionId?: string): UseArtifactsReturn => {
    const { configServerUrl } = useConfigContext();
    const { activeProject } = useProjectContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    
    // Use ref to track current request to handle race conditions
    const currentRequestRef = useRef<AbortController | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchArtifacts = useCallback(async () => {
        // Cancel any existing request
        if (currentRequestRef.current) {
            currentRequestRef.current.abort();
        }

        // Create new abort controller for this request
        const abortController = new AbortController();
        currentRequestRef.current = abortController;

        // Determine data source based on context
        let fetchUrl: string | null = null;
        let dataSource: string = "none";

        if (sessionId && sessionId.trim()) {
            // Priority 1: Session artifacts
            fetchUrl = `${apiPrefix}/artifacts/${sessionId}`;
            dataSource = "session";
        } else if (activeProject?.id) {
            // Priority 2: Project artifacts - use unified endpoint
            fetchUrl = `${apiPrefix}/artifacts/null?project_id=${activeProject.id}`;
            dataSource = "project";
        }

        if (!fetchUrl) {
            // No data source available
            setArtifacts([]);
            setIsLoading(false);
            setError(null);
            currentRequestRef.current = null;
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const response = await authenticatedFetch(fetchUrl, { 
                credentials: "include",
                signal: abortController.signal
            });

            // Check if request was aborted
            if (abortController.signal.aborted) {
                return;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    message: `Failed to fetch ${dataSource} artifacts. ${response.statusText}` 
                }));
                throw new Error(errorData.message || `Failed to fetch ${dataSource} artifacts. ${response.statusText}`);
            }

            const data: ArtifactInfo[] = await response.json();
            
            // Only update state if request wasn't aborted
            if (!abortController.signal.aborted) {
                setArtifacts(data);
                setError(null);
            }
        } catch (err: unknown) {
            // Don't set error state for aborted requests
            if (err instanceof Error && err.name === 'AbortError') {
                return;
            }

            const errorMessage = err instanceof Error ? err.message : `Failed to fetch ${dataSource} artifacts.`;
            console.error(`Error fetching ${dataSource} artifacts:`, err);
            
            if (!abortController.signal.aborted) {
                setError(errorMessage);
                setArtifacts([]);
            }
        } finally {
            if (!abortController.signal.aborted) {
                setIsLoading(false);
            }
            // Clear the current request ref if this was the active request
            if (currentRequestRef.current === abortController) {
                currentRequestRef.current = null;
            }
        }
    }, [apiPrefix, sessionId, activeProject?.id]);

    useEffect(() => {
        fetchArtifacts();
        
        // Cleanup function to abort any pending requests
        return () => {
            if (currentRequestRef.current) {
                currentRequestRef.current.abort();
                currentRequestRef.current = null;
            }
        };
    }, [fetchArtifacts]);

    return {
        artifacts,
        isLoading,
        error,
        refetch: fetchArtifacts,
    };
};
