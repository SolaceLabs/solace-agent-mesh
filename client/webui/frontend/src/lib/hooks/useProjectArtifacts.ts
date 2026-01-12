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
 * Checks if an artifact is an intermediate web content artifact from deep research.
 * These are temporary files that should not be shown in the files tab.
 *
 * @param filename The filename of the artifact to check.
 * @returns True if the artifact is an intermediate web content artifact.
 */
const isIntermediateWebContentArtifact = (filename: string | undefined): boolean => {
    if (!filename) return false;
    // Skip web_content_ artifacts (temporary files from deep research)
    return filename.startsWith("web_content_");
};

/**
 * Custom hook to fetch and manage project-specific artifact data.
 * @param projectId - The project ID to fetch artifacts for.
 * @returns Object containing artifacts data, loading state, error state, and refetch function.
 */
export const useProjectArtifacts = (projectId?: string): UseProjectArtifactsReturn => {
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchArtifacts = useCallback(async () => {
        if (!projectId) {
            setArtifacts([]);
            setIsLoading(false);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const data: ArtifactInfo[] = await api.webui.get(`/api/v1/projects/${projectId}/artifacts`);
            // Filter out intermediate web content artifacts from deep research
            const filteredData = data.filter(artifact => !isIntermediateWebContentArtifact(artifact.filename));
            setArtifacts(filteredData);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch project artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            setIsLoading(false);
        }
    }, [projectId]);

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
