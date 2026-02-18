import { skipToken, useQuery } from "@tanstack/react-query";

import { documentKeys } from "./keys";
import * as documentService from "./service";

/**
 * Hook to fetch document content for preview.
 * Returns base64 content and mimeType for the specified document.
 *
 * @param projectId - The project ID (null disables the query)
 * @param filename - The filename to fetch (null disables the query)
 * @returns React Query result with content and mimeType
 */
export function useDocumentContent(projectId: string | null, filename: string | null) {
    return useQuery({
        queryKey: projectId && filename ? documentKeys.content(projectId, filename) : ["documents", "content", "empty"],
        queryFn: projectId && filename ? () => documentService.getDocumentContent(projectId, filename) : skipToken,
        enabled: !!projectId && !!filename,
        staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    });
}
