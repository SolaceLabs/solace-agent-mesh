import { getArtifactContent } from "@/lib/utils/file";

/**
 * Retrieves document content for a file in a project.
 * Reuses the existing artifact fetching infrastructure.
 *
 * @param projectId - The project ID containing the document
 * @param filename - The filename of the document
 * @returns Promise with content (base64) and mimeType
 */
export async function getDocumentContent(projectId: string, filename: string): Promise<{ content: string; mimeType: string }> {
    return getArtifactContent({
        filename,
        projectId,
    });
}
