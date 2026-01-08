import type { FileAttachment } from "@/lib/types";
import { authenticatedFetch } from "./api";

// Helper function to parse the custom artifact URI
export const parseArtifactUri = (uri: string): { filename: string; version: string | null } | null => {
    try {
        const url = new URL(uri);
        if (url.protocol !== "artifact:") {
            return null;
        }
        const pathParts = url.pathname.split("/").filter(p => p);
        const filename = pathParts[pathParts.length - 1];
        const version = url.searchParams.get("version");
        return { filename, version };
    } catch (e) {
        console.error("Invalid artifact URI:", e);
        return null;
    }
};

export const downloadBlob = (blob: Blob, filename?: string) => {
    try {
        // Create download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "download"; // Use file name or default
        document.body.appendChild(a);
        a.click();

        // Clean up
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
            // Handle inline base64 content
            const byteCharacters = atob(file.content);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            blob = new Blob([byteArray], { type: file.mime_type || "application/octet-stream" });
        } else if (file.uri) {
            // Handle URI content by fetching it from the backend
            const parsedUri = parseArtifactUri(file.uri);
            if (!parsedUri) {
                throw new Error(`Invalid or unhandled URI format: ${file.uri}`);
            }

            filename = parsedUri.filename;
            const version = parsedUri.version || "latest";

            // Construct the API URL to fetch the artifact content
            // Priority 1: Session context (active chat)
            let apiUrl: string;
            if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
                apiUrl = `/api/v1/artifacts/${encodeURIComponent(sessionId)}/${encodeURIComponent(filename)}/versions/${version}`;
            }
            // Priority 2: Project context (pre-session, project artifacts)
            else if (projectId) {
                apiUrl = `/api/v1/artifacts/null/${encodeURIComponent(filename)}/versions/${version}?project_id=${projectId}`;
            }
            // Fallback: no context (will likely fail but let backend handle it)
            else {
                apiUrl = `/api/v1/artifacts/null/${encodeURIComponent(filename)}/versions/${version}`;
            }

            const response = await authenticatedFetch(apiUrl, { credentials: "include" });
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
        // You could add a user-facing notification here if desired
    }
};
