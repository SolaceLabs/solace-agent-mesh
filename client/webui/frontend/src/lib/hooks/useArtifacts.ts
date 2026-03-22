import { useState, useEffect, useCallback, useMemo } from "react";
import type { Dispatch, SetStateAction } from "react";
import { api } from "@/lib/api";
import type { ArtifactInfo } from "@/lib/types";
import { useProjectContext } from "../providers/ProjectProvider";
import { ARTIFACT_TAG_WORKING } from "@/lib/constants";

const STORAGE_KEY = "sam_show_working_artifacts";

interface UseArtifactsReturn {
    artifacts: ArtifactInfo[];
    allArtifacts: ArtifactInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
    setArtifacts: Dispatch<SetStateAction<ArtifactInfo[]>>;
    showWorkingArtifacts: boolean;
    toggleShowWorkingArtifacts: () => void;
    workingArtifactCount: number;
}

/**
 * Checks if an artifact has the working system tag (case-insensitive).
 * Working artifacts are hidden from users by default.
 *
 * @param tags The tags array of the artifact.
 * @returns True if the artifact has the working system tag.
 */
const hasWorkingTag = (tags: string[] | undefined): boolean => {
    return tags?.some(t => t.toLowerCase() === ARTIFACT_TAG_WORKING.toLowerCase()) ?? false;
};

export const useArtifacts = (sessionId?: string): UseArtifactsReturn => {
    const { activeProject } = useProjectContext();
    const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [showWorkingArtifacts, setShowWorkingArtifacts] = useState<boolean>(() => {
        try {
            return localStorage.getItem(STORAGE_KEY) === "true";
        } catch {
            return false;
        }
    });

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

            type RawArtifactInfo = Omit<ArtifactInfo, "sourceProjectId"> & { source_project_id?: string };
            const data: RawArtifactInfo[] = await api.webui.get(endpoint);
            // Note: web_content_ artifacts are now tagged with __working on the backend,
            // so they are hidden via the working-tag filter below rather than filename matching.
            const artifactsWithUris = data.map(({ source_project_id, ...artifact }) => ({
                ...artifact,
                sourceProjectId: source_project_id,
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

    const toggleShowWorkingArtifacts = useCallback(() => {
        setShowWorkingArtifacts(prev => {
            const newValue = !prev;
            try {
                localStorage.setItem(STORAGE_KEY, String(newValue));
            } catch {
                // Ignore localStorage errors
            }
            return newValue;
        });
    }, []);

    // Filter out working artifacts unless the toggle is on
    const filteredArtifacts = useMemo(() => {
        if (showWorkingArtifacts) {
            return artifacts;
        }
        return artifacts.filter(artifact => !hasWorkingTag(artifact.tags));
    }, [artifacts, showWorkingArtifacts]);

    // Count working artifacts for display in toggle
    const workingArtifactCount = useMemo(() => {
        return artifacts.filter(artifact => hasWorkingTag(artifact.tags)).length;
    }, [artifacts]);

    return {
        artifacts: filteredArtifacts,
        allArtifacts: artifacts,
        isLoading,
        error,
        refetch: fetchArtifacts,
        setArtifacts,
        showWorkingArtifacts,
        toggleShowWorkingArtifacts,
        workingArtifactCount,
    };
};
