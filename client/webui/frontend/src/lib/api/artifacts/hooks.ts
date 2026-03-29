import { skipToken, useQuery } from "@tanstack/react-query";

import { validIdOrUndefined } from "@/lib/utils/file";
import { artifactKeys } from "./keys";
import * as artifactService from "./service";
import type { ArtifactWithSession, BulkArtifactsResponse } from "./types";

/**
 * Hook to fetch all artifacts across all sessions and projects.
 * Uses the bulk /api/v1/artifacts/all endpoint to fetch all artifacts in a single request,
 * eliminating the N+1 API call pattern.
 * Note: web_content_ artifacts are now tagged with __working on the backend and hidden
 * via the tag-based filter in ArtifactsPage rather than filename matching.
 */
export function useAllArtifacts() {
    return useQuery({
        queryKey: artifactKeys.lists(),
        queryFn: artifactService.getAllArtifacts,
        refetchOnMount: "always",
        select: (data: BulkArtifactsResponse): ArtifactWithSession[] =>
            data.artifacts.map(artifact => ({
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
                tags: artifact.tags ?? undefined,
            })),
    });
}

/**
 * Hook to fetch artifact content for preview.
 * Returns base64 content and mimeType for the specified project artifact.
 *
 * @param projectId - The project ID (null disables the query)
 * @param filename - The filename to fetch (null disables the query)
 * @param version - Optional specific version number (defaults to "latest")
 * @returns React Query result with content and mimeType
 */
export function useProjectArtifactContent(projectId: string | null, filename: string | null, version?: number) {
    const validProjectId = validIdOrUndefined(projectId);
    return useQuery({
        queryKey: validProjectId && filename ? artifactKeys.content(null, validProjectId, filename, version) : ["artifacts", "content", "empty"],
        queryFn: validProjectId && filename ? () => artifactService.getArtifactContent({ projectId: validProjectId, filename, version }) : skipToken,
        enabled: !!validProjectId && !!filename,
        staleTime: 5 * 60 * 1000, // Cache for 5 minutes
        retry: 1,
    });
}

/**
 * Hook to fetch session-scoped artifact content for preview.
 * Returns base64 content and mimeType for the specified session artifact.
 *
 * @param sessionId - The session ID (null disables the query)
 * @param filename - The filename to fetch (null disables the query)
 * @param version - Optional specific version number (defaults to "latest")
 * @returns React Query result with content and mimeType
 */
export function useSessionArtifactContent(sessionId: string | null, filename: string | null, version?: number) {
    const validSessionId = validIdOrUndefined(sessionId);
    return useQuery({
        queryKey: validSessionId && filename ? artifactKeys.content(validSessionId, null, filename, version) : ["artifacts", "session", "empty"],
        queryFn: validSessionId && filename ? () => artifactService.getArtifactContent({ sessionId: validSessionId, filename, version }) : skipToken,
        enabled: !!validSessionId && !!filename,
        staleTime: 5 * 60 * 1000, // Cache for 5 minutes
        retry: 1,
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
