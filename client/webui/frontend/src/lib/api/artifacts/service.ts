import { api, getErrorFromResponse } from "@/lib/api";
import { getArtifactContent as getArtifactContentUtil, validIdOrUndefined } from "@/lib/utils/file";
import type { BulkArtifactsResponse } from "./types";

/**
 * Retrieves artifact content for preview, with ID validation and a "latest" version default.
 * Thin wrapper around `getArtifactContent` from `@/lib/utils/file`.
 * Supports both session-scoped and project-scoped artifacts (sessionId takes priority).
 *
 * @param options.sessionId - Optional session ID for session-scoped artifacts
 * @param options.projectId - Optional project ID for project-scoped artifacts
 * @param options.filename - The filename of the artifact
 * @param options.version - Optional specific version number (defaults to "latest")
 * @returns Promise with content (base64) and mimeType
 */
export async function getArtifactContentWithValidation({ sessionId, projectId, filename, version }: { sessionId?: string; projectId?: string; filename: string; version?: number }): Promise<{ content: string; mimeType: string }> {
    const validSession = validIdOrUndefined(sessionId);
    const validProject = validIdOrUndefined(projectId);
    return getArtifactContentUtil({
        filename,
        ...(validSession ? { sessionId: validSession } : {}),
        ...(validProject ? { projectId: validProject } : {}),
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

/**
 * Fetches a page of artifacts across all sessions and projects using the bulk endpoint.
 *
 * @param pageNumber - Page number (1-based, defaults to 1)
 * @param pageSize - Number of artifacts per page (defaults to 50)
 * @returns Promise with the paginated bulk artifacts response
 */
// pageSize default must match backend artifacts.py list_all_artifacts (page_size Query param)
export async function getAllArtifacts(pageNumber: number = 1, pageSize: number = 50, search?: string): Promise<BulkArtifactsResponse> {
    const params = new URLSearchParams({
        pageNumber: String(pageNumber),
        pageSize: String(pageSize),
    });
    if (search) {
        params.set("search", search);
    }
    return api.webui.get<BulkArtifactsResponse>(`/api/v1/artifacts/all?${params.toString()}`);
}
