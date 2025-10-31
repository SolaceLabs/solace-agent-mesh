import { useState, useEffect, useCallback } from "react";

import type { ArtifactInfo } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";
import { useProjectContext } from "../providers/ProjectProvider";

interface UseArtifactsReturn {
    artifacts: ArtifactInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
    setArtifacts: React.Dispatch<React.SetStateAction<ArtifactInfo[]>>;
}

/**
 * Custom hook to fetch and manage artifact data
 * Automatically handles both session and project contexts
 * @param sessionId - The session ID to fetch artifacts for (optional)
 * @returns Object containing artifacts data, loading state, error state, and refetch function
 */
export const useArtifacts = (sessionId?: string): UseArtifactsReturn => {
    const { configServerUrl } = useConfigContext();
    const { activeProject } = useProjectContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchArtifacts = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        
        try {
            let url: string;
            
            // Priority 1: Session context (active chat)
            if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                url = `${apiPrefix}/artifacts/${sessionId}`;
            }
            // Priority 2: Project context (pre-session, project artifacts)
            else if (activeProject?.id) {
                url = `${apiPrefix}/artifacts/null?project_id=${activeProject.id}`;
            }
            // No valid context
            else {
                setArtifacts([]);
                setIsLoading(false);
                return;
            }

            const response = await authenticatedFetch(url, { credentials: "include" });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ 
                    message: `Failed to fetch artifacts. ${response.statusText}` 
                }));
                throw new Error(errorData.message || `Failed to fetch artifacts. ${response.statusText}`);
            }
            
            const data: ArtifactInfo[] = await response.json();
            // Ensure all artifacts have URIs
            const artifactsWithUris = data.map(artifact => ({
                ...artifact,
                uri: artifact.uri || `artifact://${sessionId}/${artifact.filename}`,
            }));
            setArtifacts(artifactsWithUris);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix, sessionId, activeProject?.id]);

    useEffect(() => {
        fetchArtifacts();
    }, [fetchArtifacts]);

    return {
        artifacts,
        isLoading,
        error,
        refetch: fetchArtifacts,
        setArtifacts,
    };
};
