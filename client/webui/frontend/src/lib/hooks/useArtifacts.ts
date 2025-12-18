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

export const useArtifacts = (sessionId?: string): UseArtifactsReturn => {
    const { activeProject } = useProjectContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchArtifacts = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            let endpoint: string;

            if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                endpoint = `/api/v1/artifacts/${sessionId}`;
            } else if (activeProject?.id) {
                endpoint = `/api/v1/artifacts/null?project_id=${activeProject.id}`;
            } else {
                setArtifacts([]);
                setIsLoading(false);
                return;
            }

            const data: ArtifactInfo[] = await api.webui.get(endpoint);
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
    }, [sessionId, activeProject?.id]);

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
