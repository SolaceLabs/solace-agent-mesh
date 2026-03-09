import { skipToken, useQuery } from "@tanstack/react-query";

import { artifactKeys } from "./keys";
import * as artifactService from "./service";

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
    return useQuery({
        queryKey: projectId && filename ? artifactKeys.content(null, projectId, filename, version) : ["artifacts", "content", "empty"],
        queryFn: projectId && filename ? () => artifactService.getArtifactContent({ projectId, filename, version }) : skipToken,
        enabled: !!projectId && !!filename,
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
    return useQuery({
        queryKey: sessionId && filename ? artifactKeys.content(sessionId, null, filename, version) : ["artifacts", "session", "empty"],
        queryFn: sessionId && filename ? () => artifactService.getArtifactContent({ sessionId, filename, version }) : skipToken,
        enabled: !!sessionId && !!filename,
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
