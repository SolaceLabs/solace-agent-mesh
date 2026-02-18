import { api } from "@/lib/api";
import { blobToBase64 } from "@/lib/utils/file";

/**
 * Retrieves document content for a file in a project.
 * Uses the artifact API with version "latest" to fetch actual file content.
 *
 * @param projectId - The project ID containing the document
 * @param filename - The filename of the document
 * @returns Promise with content (base64) and mimeType
 */
export async function getDocumentContent(projectId: string, filename: string): Promise<{ content: string; mimeType: string }> {
    // Use "latest" version to fetch actual content (without version, endpoint returns version list as JSON)
    const encodedFilename = encodeURIComponent(filename);
    const contentUrl = `/api/v1/artifacts/null/${encodedFilename}/versions/latest?project_id=${projectId}`;

    const contentResponse = await api.webui.get(contentUrl, { fullResponse: true });
    if (!contentResponse.ok) {
        throw new Error(`Failed to fetch document content: ${contentResponse.statusText}`);
    }

    const contentType = contentResponse.headers.get("Content-Type") || "application/octet-stream";
    const mimeType = contentType.split(";")[0].trim();
    const blob = await contentResponse.blob();
    const content = await blobToBase64(blob);

    return { content, mimeType };
}
