import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { ArtifactInfo, Session } from "@/lib/types";

interface ArtifactWithSession extends ArtifactInfo {
    sessionId: string;
    sessionName: string | null;
}

interface UseAllArtifactsReturn {
    artifacts: ArtifactWithSession[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

interface PaginatedSessionsResponse {
    data: Session[];
    meta: {
        pagination: {
            pageNumber: number;
            count: number;
            pageSize: number;
            nextPage: number | null;
            totalPages: number;
        };
    };
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
 * Hook to fetch all artifacts across all sessions.
 * This aggregates artifacts from multiple sessions into a single list.
 */
export const useAllArtifacts = (): UseAllArtifactsReturn => {
    const [artifacts, setArtifacts] = useState<ArtifactWithSession[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAllArtifacts = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            // First, fetch all sessions (paginated)
            const allSessions: Session[] = [];
            let pageNumber = 1;
            let hasMore = true;

            while (hasMore) {
                const result: PaginatedSessionsResponse = await api.webui.get(`/api/v1/sessions?pageNumber=${pageNumber}&pageSize=50`);
                allSessions.push(...result.data);
                hasMore = result.meta.pagination.nextPage !== null;
                pageNumber++;

                // Safety limit to prevent infinite loops
                if (pageNumber > 100) break;
            }

            // Now fetch artifacts for each session in parallel (with concurrency limit)
            const allArtifacts: ArtifactWithSession[] = [];
            const concurrencyLimit = 5;

            for (let i = 0; i < allSessions.length; i += concurrencyLimit) {
                const batch = allSessions.slice(i, i + concurrencyLimit);
                const batchResults = await Promise.allSettled(
                    batch.map(async session => {
                        try {
                            const sessionArtifacts: ArtifactInfo[] = await api.webui.get(`/api/v1/artifacts/${session.id}`);
                            // Filter out intermediate artifacts and add session info
                            return sessionArtifacts
                                .filter(artifact => !isIntermediateWebContentArtifact(artifact.filename))
                                .map(artifact => ({
                                    ...artifact,
                                    sessionId: session.id,
                                    sessionName: session.name,
                                    uri: artifact.uri || `artifact://${session.id}/${artifact.filename}`,
                                }));
                        } catch {
                            // Session might not have artifacts or might have been deleted
                            return [];
                        }
                    })
                );

                // Collect successful results
                for (const result of batchResults) {
                    if (result.status === "fulfilled") {
                        allArtifacts.push(...result.value);
                    }
                }
            }

            // Sort by last_modified (most recent first)
            allArtifacts.sort((a, b) => {
                const dateA = new Date(a.last_modified).getTime();
                const dateB = new Date(b.last_modified).getTime();
                return dateB - dateA;
            });

            setArtifacts(allArtifacts);
        } catch (err: unknown) {
            const errorMessage = err instanceof Error ? err.message : "Failed to fetch artifacts.";
            setError(errorMessage);
            setArtifacts([]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAllArtifacts();
    }, [fetchAllArtifacts]);

    return {
        artifacts,
        isLoading,
        error,
        refetch: fetchAllArtifacts,
    };
};
