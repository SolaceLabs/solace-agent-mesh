import { api, getErrorFromResponse } from "@/lib/api";
import { getArtifactContent as getArtifactContentUtil } from "@/lib/utils/file";

/**
 * Retrieves artifact content for preview.
 * Supports both session-scoped and project-scoped artifacts (sessionId takes priority).
 *
 * @param options.sessionId - Optional session ID for session-scoped artifacts
 * @param options.projectId - Optional project ID for project-scoped artifacts
 * @param options.filename - The filename of the artifact
 * @param options.version - Optional specific version number (defaults to "latest")
 * @returns Promise with content (base64) and mimeType
 */
export async function getArtifactContent({ sessionId, projectId, filename, version }: { sessionId?: string; projectId?: string; filename: string; version?: number }): Promise<{ content: string; mimeType: string }> {
    return getArtifactContentUtil({
        filename,
        ...(sessionId ? { sessionId } : {}),
        ...(projectId ? { projectId } : {}),
        version: version ?? "latest",
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
        try {
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
        } catch (e) {
            throw new Error(`Failed to decode data URL: ${e instanceof Error ? e.message : String(e)}`);
        }
    }

    const response = await api.webui.get(url, { fullResponse: true });
    if (!response.ok) {
        throw new Error(await getErrorFromResponse(response));
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
}
