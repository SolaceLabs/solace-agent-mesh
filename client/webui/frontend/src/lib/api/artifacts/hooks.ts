import { skipToken, useQuery } from "@tanstack/react-query";

import { artifactKeys } from "./keys";
import * as artifactService from "./service";
import type { ArtifactWithSession, BulkArtifactsResponse } from "./types";

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
export function useAllArtifacts() {
    return useQuery({
        queryKey: artifactKeys.lists(),
        queryFn: artifactService.getAllArtifacts,
        refetchOnMount: "always",
        select: (data: BulkArtifactsResponse): ArtifactWithSession[] =>
            data.artifacts
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
                    source: artifact.source ?? undefined,
                })),
    });
}

/**
 * Hook to fetch artifact content for preview.
 * Returns base64 content and mimeType for the specified artifact.
 *
 * @param projectId - The project ID (null disables the query)
 * @param filename - The filename to fetch (null disables the query)
 * @returns React Query result with content and mimeType
 */
export function useArtifactContent(projectId: string | null, filename: string | null) {
    return useQuery({
        queryKey: projectId && filename ? artifactKeys.content(projectId, filename) : ["artifacts", "content", "empty"],
        queryFn: projectId && filename ? () => artifactService.getArtifactContent(projectId, filename) : skipToken,
        enabled: !!projectId && !!filename,
        staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    });
}

/**
 * Hook to fetch PDF artifact as a blob URL for rendering.
 * Uses React Query for caching and the api client for authenticated fetching.
 *
 * @param url - The artifact URL to fetch (null disables the query)
 * @returns React Query result with blob URL and error state
 */
export function usePdfBlob(url: string | null) {
    return useQuery({
        queryKey: url ? artifactKeys.pdfBlob(url) : ["artifacts", "pdf-blob", "empty"],
        queryFn: url ? () => artifactService.fetchPdfBlob(url) : skipToken,
        enabled: !!url,
        staleTime: 10 * 60 * 1000, // Cache for 10 minutes
        gcTime: 30 * 60 * 1000, // Keep in cache for 30 minutes after last use
        retry: 1, // Only retry once on failure
    });
}
