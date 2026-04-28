import { useMemo } from "react";
import { skipToken, useQuery, useInfiniteQuery } from "@tanstack/react-query";

import { validIdOrUndefined } from "@/lib/utils/file";
import { artifactKeys } from "./keys";
import * as artifactService from "./service";
import type { ArtifactWithSession, BulkArtifactsResponse } from "./types";

// Must match the backend default in artifacts.py list_all_artifacts (page_size Query param)
const ARTIFACTS_PAGE_SIZE = 50;

/**
 * Transform a single page of bulk artifacts response into ArtifactWithSession[].
 */
function transformArtifacts(artifacts: BulkArtifactsResponse["artifacts"]): ArtifactWithSession[] {
    return artifacts.map(artifact => ({
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
    }));
}

/**
 * Hook to fetch all artifacts across all sessions and projects with pagination.
 * Uses the paginated /api/v1/artifacts/all endpoint with useInfiniteQuery
 * to support "Load More" functionality.
 *
 * @param search - Optional server-side search query. When provided, the backend
 *   disables early termination and searches across ALL sessions/projects.
 * @returns Flattened artifacts from all loaded pages, plus pagination controls.
 */
export function useAllArtifacts(search?: string) {
    const query = useInfiniteQuery({
        // Include search in the query key so changing the search resets pagination
        queryKey: [...artifactKeys.lists(), { search: search || undefined }],
        queryFn: ({ pageParam = 1 }) => artifactService.getAllArtifacts(pageParam, ARTIFACTS_PAGE_SIZE, search || undefined),
        initialPageParam: 1,
        getNextPageParam: lastPage => lastPage.nextPage ?? undefined,
        refetchOnMount: "always",
    });

    // Flatten all pages into a single deduplicated array of artifacts.
    // useMemo avoids creating a new array reference on every render (issue: unnecessary
    // re-renders of ArtifactGridCard children). Cross-page dedup by filename+sessionId
    // guards against offset drift when artifacts are added/removed between page fetches.
    const pages = query.data?.pages;
    const artifacts = useMemo<ArtifactWithSession[]>(() => {
        if (!pages) return [];
        const all = pages.flatMap(page => transformArtifacts(page.artifacts));
        const seen = new Set<string>();
        return all.filter(a => {
            const key = `${a.filename}::${a.sessionId}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }, [pages]);

    const totalCount = pages?.[pages.length - 1]?.totalCount ?? 0;

    return {
        ...query,
        data: artifacts,
        totalCount,
        hasMore: query.hasNextPage ?? false,
        loadMore: query.fetchNextPage,
        isLoadingMore: query.isFetchingNextPage,
    };
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
        queryFn: validProjectId && filename ? () => artifactService.getArtifactContentWithValidation({ projectId: validProjectId, filename, version }) : skipToken,
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
        queryFn: validSessionId && filename ? () => artifactService.getArtifactContentWithValidation({ sessionId: validSessionId, filename, version }) : skipToken,
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
