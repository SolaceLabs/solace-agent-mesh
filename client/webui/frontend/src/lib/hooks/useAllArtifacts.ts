import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { ArtifactInfo } from "@/lib/types";

/**
 * Extended artifact type with session and project information.
 * Exported for use in components that display artifacts.
 */
export interface ArtifactWithSession extends ArtifactInfo {
    sessionId: string;
    sessionName: string | null;
    projectId?: string;
    projectName?: string | null;
}

interface UseAllArtifactsReturn {
    artifacts: ArtifactWithSession[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

/**
 * Response from the bulk artifacts endpoint.
 */
interface BulkArtifactsResponse {
    artifacts: Array<{
        filename: string;
        size: number;
        mimeType: string | null;
        lastModified: string | null;
        uri: string | null;
        sessionId: string;
        sessionName: string | null;
        projectId: string | null;
        projectName: string | null;
    }>;
    totalCount: number;
}

/**
 * Checks if an artifact is an intermediate web content artifact from deep research.
 * These are temporary files that should not be shown in the files tab.
 */
const isIntermediateWebContentArtifact = (filename: string | undefined): boolean => {
    if (!filename) return false;
    return filename.startsWith("web_content_");
};

/**
 * Hook to fetch all artifacts across all sessions and projects.
 * Uses the bulk /api/v1/artifacts/all endpoint to fetch all artifacts in a single request,
 * eliminating the N+1 API call pattern.
 */
export const useAllArtifacts = (): UseAllArtifactsReturn => {
    const [artifacts, setArtifacts] = useState<ArtifactWithSession[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    const fetchAllArtifacts = useCallback(async () => {
        // Cancel any in-flight request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();
        const signal = abortControllerRef.current.signal;

        setIsLoading(true);
        setError(null);

        try {
            // Use the bulk endpoint to fetch all artifacts in a single request
            const response = await api.webui.get<BulkArtifactsResponse>("/api/v1/artifacts/all");

            // Only update state if not aborted
            if (signal.aborted) return;

            // Transform the response to match ArtifactWithSession interface
            const transformedArtifacts: ArtifactWithSession[] = response.artifacts
                .filter(artifact => !isIntermediateWebContentArtifact(artifact.filename))
                .map(artifact => ({
                    filename: artifact.filename,
                    size: artifact.size,
                    mime_type: artifact.mimeType ?? "application/octet-stream",
                    last_modified: artifact.lastModified ?? new Date().toISOString(),
                    uri: artifact.uri ?? "",
                    sessionId: artifact.sessionId,
                    sessionName: artifact.sessionName,
                    projectId: artifact.projectId ?? undefined,
                    projectName: artifact.projectName,
                }));

            setArtifacts(transformedArtifacts);
        } catch (err: unknown) {
            // Ignore abort errors
            if (err instanceof Error && err.name === "AbortError") {
                return;
            }
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            if (!signal.aborted) {
                setIsLoading(false);
            }
        }
    }, []);

    useEffect(() => {
        fetchAllArtifacts();

        // Cleanup: abort any in-flight request when component unmounts
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, [fetchAllArtifacts]);

    return {
        artifacts,
        isLoading,
        error,
        refetch: fetchAllArtifacts,
    };
};
