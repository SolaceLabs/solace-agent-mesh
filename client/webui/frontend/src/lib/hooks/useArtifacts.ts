import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { ArtifactInfo } from "@/lib/types";
import { useProjectContext } from "../providers/ProjectProvider";

interface UseArtifactsReturn {
    artifacts: ArtifactInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
    setArtifacts: React.Dispatch<React.SetStateAction<ArtifactInfo[]>>;
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

export const useArtifacts = (sessionId?: string, agentName?: string): UseArtifactsReturn => {
    const { activeProject } = useProjectContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchArtifacts = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            let endpoint: string;
            const params = new URLSearchParams();

            if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                endpoint = `/api/v1/artifacts/${sessionId}`;
            } else if (activeProject?.id) {
                endpoint = `/api/v1/artifacts/null`;
                params.append("project_id", activeProject.id);
            } else {
                setArtifacts([]);
                setIsLoading(false);
                return;
            }

            // Add agent_name parameter to include agent's default artifacts
            if (agentName) {
                params.append("agent_name", agentName);
            }

            // Append query parameters if any
            const queryString = params.toString();
            if (queryString) {
                endpoint += `?${queryString}`;
            }

            const data: ArtifactInfo[] = await api.webui.get(endpoint);
            // Filter out intermediate web content artifacts from deep research
            const filteredData = data.filter(artifact => !isIntermediateWebContentArtifact(artifact.filename));
            const artifactsWithUris = filteredData.map(artifact => ({
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
    }, [sessionId, activeProject?.id, agentName]);

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
