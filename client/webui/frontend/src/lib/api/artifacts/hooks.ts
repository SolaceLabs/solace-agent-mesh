import { skipToken, useQuery, useInfiniteQuery } from "@tanstack/react-query";

import { validIdOrUndefined } from "@/lib/utils/file";
import { artifactKeys } from "./keys";
import * as artifactService from "./service";
import type { ArtifactWithSession, BulkArtifactsResponse } from "./types";

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
 * Returns flattened artifacts from all loaded pages, plus pagination controls.
 */
export function useAllArtifacts() {
    const query = useInfiniteQuery({
        queryKey: artifactKeys.lists(),
        queryFn: ({ pageParam = 1 }) => artifactService.getAllArtifacts(pageParam, ARTIFACTS_PAGE_SIZE),
        initialPageParam: 1,
        getNextPageParam: lastPage => lastPage.nextPage ?? undefined,
        refetchOnMount: "always",
    });

    // Flatten all pages into a single array of artifacts
    const artifacts: ArtifactWithSession[] = query.data?.pages.flatMap(page => transformArtifacts(page.artifacts)) ?? [];
    const totalCount = query.data?.pages[query.data.pages.length - 1]?.totalCount ?? 0;

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
