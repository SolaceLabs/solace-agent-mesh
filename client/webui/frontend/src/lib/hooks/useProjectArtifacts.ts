import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

import type { ArtifactInfo } from "@/lib/types";


interface UseProjectArtifactsReturn {
    artifacts: ArtifactInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

/**
 * Custom hook to fetch and manage project-specific artifact data.
 * @param projectId - The project ID to fetch artifacts for.
 * @returns Object containing artifacts data, loading state, error state, and refetch function.
 */
export const useProjectArtifacts = (projectId?: string): UseProjectArtifactsReturn => {
    // Migrated to api client
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const { chat: chatBaseUrl } = api.getBaseUrls();

    const fetchArtifacts = useCallback(async () => {
        if (!projectId) {
            setArtifacts([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const url = `${chatBaseUrl}/api/v1/projects/${projectId}/artifacts`;
            const data: ArtifactInfo[] = await api.chat.get(url);
            setArtifacts(data);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch project artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            setIsLoading(false);
        }
    }, [ projectId]);

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
