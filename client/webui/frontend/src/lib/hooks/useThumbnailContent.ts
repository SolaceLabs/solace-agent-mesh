import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { parseArtifactUri } from "@/lib/utils/download";

interface UseThumbnailContentOptions {
    /** Artifact URI to fetch content from */
    uri?: string;
    /** Filename for the artifact */
    filename: string;
    /** MIME type of the artifact */
    mimeType?: string;
    /** Session ID for API calls */
    sessionId?: string;
    /** Project ID for API calls */
    projectId?: string;
    /** Whether to enable fetching (can be used to delay fetch) */
    enabled?: boolean;
}

interface UseThumbnailContentResult {
    /** Base64-encoded content */
    content: string | null;
    /** Whether content is currently loading */
    isLoading: boolean;
    /** Error message if fetch failed */
    error: string | null;
    /** Function to manually trigger fetch */
    refetch: () => void;
}

// Cache for fetched content to avoid re-fetching
const contentCache = new Map<string, string>();

// Check if file type supports thumbnail
const supportsThumbnailType = (filename: string, mimeType?: string): boolean => {
    const ext = filename.toLowerCase().split(".").pop();
    const thumbnailExtensions = ["pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt", "odp", "ods"];
    if (ext && thumbnailExtensions.includes(ext)) return true;

    const thumbnailMimeTypes = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.spreadsheet",
    ];
    return mimeType ? thumbnailMimeTypes.includes(mimeType) : false;
};

/**
 * Hook to fetch artifact content for thumbnail generation.
 * Only fetches content for file types that support thumbnails (PDF, DOCX, PPTX, etc.)
 * Caches results to avoid re-fetching.
 */
export const useThumbnailContent = ({ uri, filename, mimeType, sessionId, projectId, enabled = true }: UseThumbnailContentOptions): UseThumbnailContentResult => {
    const [content, setContent] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const mountedRef = useRef(true);
    const fetchingRef = useRef(false);

    // Check if this file type supports thumbnails
    const supportsThumbnail = supportsThumbnailType(filename, mimeType);

    // Generate cache key
    const cacheKey = uri || `${sessionId}:${filename}`;

    const fetchContent = useCallback(async () => {
        // Don't fetch if not enabled, no URI, or file type doesn't support thumbnails
        if (!enabled || !uri || !supportsThumbnail) {
            return;
        }

        // Check cache first
        const cached = contentCache.get(cacheKey);
        if (cached) {
            setContent(cached);
            return;
        }

        // Prevent duplicate fetches
        if (fetchingRef.current) {
            return;
        }

        fetchingRef.current = true;
        setIsLoading(true);
        setError(null);

        try {
            const parsedUri = parseArtifactUri(uri);
            if (!parsedUri) {
                throw new Error("Invalid artifact URI");
            }

            const { sessionId: uriSessionId, filename: uriFilename, version } = parsedUri;

            // Construct API URL
            let apiUrl: string;
            const effectiveSessionId = uriSessionId || sessionId;

            if (effectiveSessionId && effectiveSessionId.trim() && effectiveSessionId !== "null" && effectiveSessionId !== "undefined") {
                apiUrl = `/api/v1/artifacts/${effectiveSessionId}/${encodeURIComponent(uriFilename)}/versions/${version || "latest"}`;
            } else if (projectId) {
                apiUrl = `/api/v1/artifacts/null/${encodeURIComponent(uriFilename)}/versions/${version || "latest"}?project_id=${projectId}`;
            } else {
                apiUrl = `/api/v1/artifacts/null/${encodeURIComponent(uriFilename)}/versions/${version || "latest"}`;
            }

            const response = await api.webui.get(apiUrl, { fullResponse: true });
            if (!response.ok) {
                throw new Error(`Failed to fetch artifact: ${response.statusText}`);
            }

            const blob = await response.blob();
            const base64data = await new Promise<string>((resolve, reject) => {
                const reader = new FileReader();
                reader.onloadend = () => {
                    if (typeof reader.result === "string") {
                        resolve(reader.result.split(",")[1]);
                    } else {
                        reject(new Error("Failed to read content as data URL"));
                    }
                };
                reader.onerror = () => {
                    reject(reader.error || new Error("Unknown error reading file"));
                };
                reader.readAsDataURL(blob);
            });

            if (mountedRef.current) {
                // Cache the result
                contentCache.set(cacheKey, base64data);
                setContent(base64data);
            }
        } catch (err) {
            console.warn("Failed to fetch thumbnail content:", err);
            if (mountedRef.current) {
                setError(err instanceof Error ? err.message : "Unknown error");
            }
        } finally {
            if (mountedRef.current) {
                setIsLoading(false);
            }
            fetchingRef.current = false;
        }
    }, [uri, enabled, supportsThumbnail, cacheKey, sessionId, projectId]);

    // Fetch content on mount or when dependencies change
    useEffect(() => {
        mountedRef.current = true;
        fetchContent();

        return () => {
            mountedRef.current = false;
        };
    }, [fetchContent]);

    return {
        content,
        isLoading,
        error,
        refetch: fetchContent,
    };
};

export default useThumbnailContent;
