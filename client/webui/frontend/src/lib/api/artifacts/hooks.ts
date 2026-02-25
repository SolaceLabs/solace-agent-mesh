import { skipToken, useQuery } from "@tanstack/react-query";

import { artifactKeys } from "./keys";
import * as artifactService from "./service";

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
