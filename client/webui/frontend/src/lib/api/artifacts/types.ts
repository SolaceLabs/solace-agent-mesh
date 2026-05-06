import type { ArtifactInfo } from "@/lib/types";

/**
 * Response from the bulk artifacts endpoint (paginated).
 */
export interface BulkArtifactsResponse {
    artifacts: Array<{
        filename: string;
        size: number;
        mimeType: string | null;
        lastModified: string | null;
        uri: string | null;
        /** Resolved-latest version reported by the backend at list time. */
        version: number | null;
        sessionId: string;
        sessionName: string | null;
        projectId: string | null;
        projectName: string | null;
        source: string | null;
        tags: string[] | null;
    }>;
    totalCount: number;
    hasMore: boolean;
    nextPage: number | null;
}

/**
 * Extended artifact type with session and project information.
 * Exported for use in components that display artifacts.
 */
export interface ArtifactWithSession extends ArtifactInfo {
    sessionId: string;
    sessionName: string | null;
    projectId?: string;
    projectName?: string | null;
    /** Source type: "upload", "generated", or "project" */
    source?: string;
}
