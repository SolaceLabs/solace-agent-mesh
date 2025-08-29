import { useState, useEffect, useCallback } from "react";

import type { ArtifactInfo } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

interface UseArtifactsReturn {
    artifacts: ArtifactInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

/**
 * Custom hook to fetch and manage artifact data
 * @param sessionId - The session ID to fetch artifacts for
 * @returns Object containing artifacts data, loading state, error state, and refetch function
 */
export const useArtifacts = (sessionId?: string): UseArtifactsReturn => {
    const { configServerUrl } = useConfigContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchArtifacts = useCallback(async () => {
        if (!sessionId) {
            setArtifacts([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch(`${apiPrefix}/artifacts/${sessionId}`, { credentials: "include" });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Failed to fetch artifacts. ${response.statusText}` }));
                throw new Error(errorData.message || `Failed to fetch artifacts. ${response.statusText}`);
            }
            const data: ArtifactInfo[] = await response.json();
            setArtifacts(data);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix, sessionId]);

    useEffect(() => {
        fetchArtifacts();
    }, [fetchArtifacts]);

    return {
        artifacts,
        isLoading,
        error,
        refetch: fetchArtifacts,
    };
};
