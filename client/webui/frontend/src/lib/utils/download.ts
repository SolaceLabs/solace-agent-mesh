import type { FileAttachment } from "@/lib/types";
import { api } from "@/lib/api";

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

export const downloadBlob = (blob: Blob, filename?: string) => {
    try {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "download";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Error downloading blob:", error);
    }
};

export const downloadFile = async (file: FileAttachment, sessionId?: string, projectId?: string) => {
    try {
        let blob: Blob;
        let filename = file.name;

        if (file.content) {
            const byteCharacters = atob(file.content);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            blob = new Blob([byteArray], { type: file.mime_type || "application/octet-stream" });
        } else if (file.uri) {
            const parsedUri = parseArtifactUri(file.uri);
            if (!parsedUri) {
                throw new Error(`Invalid or unhandled URI format: ${file.uri}`);
            }

            const { filename: parsedFilename, version: parsedVersion } = parsedUri;
            filename = parsedFilename;
            const version = parsedVersion || "latest";

            let endpoint: string;
            if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                endpoint = `/api/v1/artifacts/${encodeURIComponent(sessionId)}/${encodeURIComponent(filename)}/versions/${version}`;
            } else if (projectId) {
                endpoint = `/api/v1/artifacts/null/${encodeURIComponent(filename)}/versions/${version}?project_id=${projectId}`;
            } else {
                endpoint = `/api/v1/artifacts/null/${encodeURIComponent(filename)}/versions/${version}`;
            }

            const response = await api.webui.get(endpoint, { fullResponse: true });
            if (!response.ok) {
                throw new Error(`Failed to download file: ${response.statusText}`);
            }
            blob = await response.blob();
        } else {
            throw new Error("File has no content or URI to download.");
        }

        downloadBlob(blob, filename);
    } catch (error) {
        console.error("Error creating download link:", error);
    }
};
