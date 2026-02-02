import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { ArtifactInfo, Session, Project } from "@/lib/types";

interface ArtifactWithSession extends ArtifactInfo {
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

interface ProjectsResponse {
    projects: Project[];
    total: number;
}

/**
 * Hook to fetch all artifacts across all sessions and projects.
 * This aggregates artifacts from multiple sessions and projects into a single list.
 */
export const useAllArtifacts = (): UseAllArtifactsReturn => {
    const [artifacts, setArtifacts] = useState<ArtifactWithSession[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAllArtifacts = useCallback(async () => {
        setIsLoading(true);
        setError(null);

        try {
            const allArtifacts: ArtifactWithSession[] = [];
            const concurrencyLimit = 5;

            // Fetch all sessions (paginated) and all projects in parallel
            const [sessionsPromise, projectsPromise] = await Promise.allSettled([
                (async () => {
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
                    return allSessions;
                })(),
                api.webui.get<ProjectsResponse>("/api/v1/projects?include_artifact_count=true"),
            ]);

            // Process session artifacts
            if (sessionsPromise.status === "fulfilled") {
                const allSessions = sessionsPromise.value;

                for (let i = 0; i < allSessions.length; i += concurrencyLimit) {
                    const batch = allSessions.slice(i, i + concurrencyLimit);
                    const batchResults = await Promise.allSettled(
                        batch.map(async session => {
                            try {
                                const sessionArtifacts: ArtifactInfo[] = await api.webui.get(`/api/v1/artifacts/${session.id}`);
                                // Filter out intermediate artifacts and project artifact copies (source === "project")
                                // Project artifacts are shown separately from the canonical project source
                                return sessionArtifacts
                                    .filter(artifact => !isIntermediateWebContentArtifact(artifact.filename) && artifact.source !== "project")
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
            }

            // Process project artifacts
            if (projectsPromise.status === "fulfilled") {
                const allProjects = projectsPromise.value.projects;

                // Track which artifacts we've already added from sessions to avoid duplicates
                const sessionArtifactKeys = new Set(allArtifacts.map(a => `${a.sessionId}:${a.filename}`));

                for (let i = 0; i < allProjects.length; i += concurrencyLimit) {
                    const batch = allProjects.slice(i, i + concurrencyLimit);
                    const batchResults = await Promise.allSettled(
                        batch.map(async project => {
                            try {
                                const projectArtifacts: ArtifactInfo[] = await api.webui.get(`/api/v1/projects/${project.id}/artifacts`);
                                // Filter out intermediate artifacts and add project info
                                return projectArtifacts
                                    .filter(artifact => !isIntermediateWebContentArtifact(artifact.filename))
                                    .map(artifact => ({
                                        ...artifact,
                                        // Project artifacts don't have a session, use project ID as a pseudo-session
                                        sessionId: `project:${project.id}`,
                                        sessionName: null,
                                        projectId: project.id,
                                        projectName: project.name,
                                        source: artifact.source || "project",
                                        uri: artifact.uri || `artifact://project:${project.id}/${artifact.filename}`,
                                    }));
                            } catch {
                                // Project might not have artifacts or might have been deleted
                                return [];
                            }
                        })
                    );

                    // Collect successful results, avoiding duplicates
                    for (const result of batchResults) {
                        if (result.status === "fulfilled") {
                            for (const artifact of result.value) {
                                // Only add if not already present from a session
                                const key = `${artifact.sessionId}:${artifact.filename}`;
                                if (!sessionArtifactKeys.has(key)) {
                                    allArtifacts.push(artifact);
                                    sessionArtifactKeys.add(key);
                                }
                            }
                        }
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
