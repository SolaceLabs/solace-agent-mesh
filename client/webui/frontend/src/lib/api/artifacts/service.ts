import { api } from "@/lib/api";
import { getArtifactContent as getArtifactContentUtil } from "@/lib/utils/file";

/**
 * Retrieves artifact content for a file in a project.
 * Uses the unified artifact utility with version "latest" to fetch actual file content.
 *
 * @param projectId - The project ID containing the artifact
 * @param filename - The filename of the artifact
 * @returns Promise with content (base64) and mimeType
 */
export async function getArtifactContent(projectId: string, filename: string): Promise<{ content: string; mimeType: string }> {
    // Use the unified utility from @/lib/utils/file.ts
    // This supports both session-scoped and project-scoped artifacts
    return getArtifactContentUtil({
        filename,
        projectId,
        version: "latest", // Fetch latest version
    });
}

/**
 * Fetches a PDF artifact as a blob and returns a blob URL.
 * Uses the api client which handles Bearer token auth + token refresh.
 * Falls back to cookie auth when no token is present (community mode).
 *
 * @param url - The artifact URL to fetch
 * @returns Promise with blob URL string
 * @throws Error if fetch fails or response is not ok
 */
export async function fetchPdfBlob(url: string): Promise<string> {
    // Handle data URLs directly - convert to blob URL without HTTP fetch
    // PDF.js cannot handle data: URLs directly; we must convert to blob URL
    if (url.startsWith("data:")) {
        const [header, base64Data] = url.split(",");
        const mimeMatch = header.match(/data:([^;]+)/);
        const mimeType = mimeMatch ? mimeMatch[1] : "application/pdf";
        const binaryString = atob(base64Data);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: mimeType });
        return URL.createObjectURL(blob);
    }

    const response = await api.webui.get(url, { fullResponse: true });
    if (!response.ok) {
        throw new Error(`Failed to fetch PDF: ${response.statusText}`);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
}
