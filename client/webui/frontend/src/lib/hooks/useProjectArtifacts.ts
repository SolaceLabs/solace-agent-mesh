import { useState, useEffect, useCallback } from "react";

import type { ArtifactInfo } from "@/lib/types";
import { fetchJsonWithError } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

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
    const { configServerUrl } = useConfigContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchArtifacts = useCallback(async () => {
        if (!projectId) {
            setArtifacts([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const url = `${apiPrefix}/projects/${projectId}/artifacts`;
            const data: ArtifactInfo[] = await fetchJsonWithError(url);
            setArtifacts(data);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch project artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix, projectId]);

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
