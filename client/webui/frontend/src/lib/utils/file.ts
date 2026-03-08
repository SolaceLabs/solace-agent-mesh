import { api } from "../api";

/**
 * Converts a File object to a Base64-encoded string.
 * @param file - The file to convert
 * @returns A promise that resolves to the Base64 string
 */
export const fileToBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string).split(",")[1]);
        reader.onerror = error => reject(error);
        reader.readAsDataURL(file);
    });

/**
 * Converts a Blob object to a Base64-encoded string.
 * @param blob
 * @returns A promise that resolves to the Base64 string
 */
export const blobToBase64 = (blob: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result?.toString().split(",")[1] || "");
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
};

/**
 * Generates an artifact URL for fetching either a list of versions or a specific version.
 *
 * @param options - Configuration options for building the artifact URL
 * @param options.filename - The name of the artifact file
 * @param options.sessionId - Optional session ID for session-scoped artifacts
 * @param options.projectId - Optional project ID for project-scoped artifacts (used when no session)
 * @param options.version - Optional version number or "latest". If omitted, returns URL for listing all versions
 * @returns The constructed artifact URL
 * @throws {Error} When neither sessionId nor projectId is provided
 */
export const getArtifactUrl = ({ filename, sessionId, projectId, version }: { filename: string; sessionId?: string; projectId?: string; version?: number | "latest" }): string => {
    const isValidSession = sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined";
    const encodedFilename = encodeURIComponent(filename);

    const basePath = isValidSession ? `/api/v1/artifacts/${sessionId}/${encodedFilename}/versions` : `/api/v1/artifacts/null/${encodedFilename}/versions`;
    const versionPath = version !== undefined ? `/${version}` : "";
    const url = `${basePath}${versionPath}`;

    // Add projectId query param if needed (when no valid session)
    if (!isValidSession && projectId) {
        return `${url}?project_id=${projectId}`;
    }

    if (!isValidSession && !projectId) {
        throw new Error("No valid context for artifact: either sessionId or projectId must be provided");
    }

    return url;
};

/**
 * Retrieves the content and MIME type of a specific artifact version.
 * @param options - Configuration options for fetching the artifact content
 * @param options.filename - The name of the artifact file
 * @param options.sessionId - Optional session ID for session-scoped artifacts
 * @param options.projectId - Optional project ID for project-scoped artifacts (used when no session)
 * @param options.version - Optional version number or "latest". If omitted, fetches the latest version
 * @returns A promise that resolves to an object containing the content as a base64 string and the MIME type
 * @throws {Error} When the fetch operation fails
 */
export const getArtifactContent = async ({ filename, sessionId, projectId, version }: { filename: string; sessionId?: string; projectId?: string; version?: number | "latest" }): Promise<{ content: string; mimeType: string }> => {
    const contentUrl = getArtifactUrl({
        filename,
        sessionId,
        projectId,
        version,
    });

    const contentResponse = await api.webui.get(contentUrl, { fullResponse: true });
    if (!contentResponse.ok) {
        throw new Error(`Failed to fetch artifact content: ${contentResponse.statusText}`);
    }

    const contentType = contentResponse.headers.get("Content-Type") || "application/octet-stream";
    const mimeType = contentType.split(";")[0].trim();
    const blob = await contentResponse.blob();
    const content = await blobToBase64(blob);

    return { content, mimeType };
};

export const parseArtifactUri = (uri: string): { sessionId: string | null; filename: string; version: string | null } | null => {
    try {
        const url = new URL(uri);
        if (url.protocol !== "artifact:") {
            return null;
        }

        // URI format: artifact://{app_name}/{user_id}/{session_id}/{filename}?version={version}
        // hostname = app_name
        // pathname = /{user_id}/{session_id}/{filename}
        const pathParts = url.pathname.split("/").filter(p => p);

        // Expected path parts: [user_id, session_id, filename]
        if (pathParts.length < 3) {
            // Fallback for legacy format: artifact://{session_id}/{filename}
            // In this case, hostname might be session_id and filename is in path
            const sessionId = url.hostname || null;
            const filename = pathParts.length > 0 ? pathParts[pathParts.length - 1] : "";
            if (!filename) {
                return null;
            }
            const version = url.searchParams.get("version");
            return { sessionId, filename, version };
        }

        // Standard format: extract session_id from path (index 1)
        const sessionId = pathParts[1];
        const filename = pathParts[2];

        const version = url.searchParams.get("version");
        return { sessionId, filename, version };
    } catch (e) {
        console.error("Invalid artifact URI:", e);
        return null;
    }
};
