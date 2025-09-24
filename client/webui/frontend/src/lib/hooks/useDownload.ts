import type { ArtifactInfo } from "../types";
import { authenticatedFetch } from "../utils/api";
import { downloadBlob } from "../utils/download";
import { useProjectContext } from "@/lib/providers";

import { useChatContext } from "./useChatContext";
import { useConfigContext } from "./useConfigContext";

/**
 * Downloads an artifact file from the server
 * @param apiPrefix - The API prefix URL
 * @param sessionId - The session ID to download artifacts from (optional)
 * @param projectId - The project ID to download artifacts from (optional)
 * @param artifact - The artifact to download
 */
const downloadArtifactFile = async (
    apiPrefix: string, 
    sessionId: string | undefined, 
    projectId: string | undefined, 
    artifact: ArtifactInfo
) => {
    let downloadUrl: string;
    
    if (sessionId && sessionId.trim()) {
        // Priority 1: Session artifacts
        downloadUrl = `${apiPrefix}/api/v1/artifacts/${sessionId}/${encodeURIComponent(artifact.filename)}`;
    } else if (projectId) {
        // Priority 2: Project artifacts
        downloadUrl = `${apiPrefix}/api/v1/projects/${projectId}/artifacts/${encodeURIComponent(artifact.filename)}`;
    } else {
        throw new Error("No valid context for downloading artifact");
    }

    const response = await authenticatedFetch(downloadUrl, {
        credentials: "include",
    });

    if (!response.ok) {
        throw new Error(`Failed to download artifact: ${artifact.filename}. Status: ${response.status}`);
    }

    const blob = await response.blob();
    downloadBlob(blob, artifact.filename);
};

/**
 * Custom hook to handle artifact downloads
 * @returns Object containing download handler function
 */
export const useDownload = () => {
    const { configServerUrl } = useConfigContext();
    const { addNotification, sessionId } = useChatContext();
    const { activeProject } = useProjectContext();

    const onDownload = async (artifact: ArtifactInfo) => {
        // Determine context for download
        if (!sessionId && !activeProject?.id) {
            addNotification(`Cannot download artifact: No active session or project.`, "error");
            return;
        }

        try {
            await downloadArtifactFile(configServerUrl, sessionId, activeProject?.id, artifact);
            addNotification(`Downloaded artifact: ${artifact.filename}.`);
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : "Unknown error";
            addNotification(`Failed to download artifact: ${artifact.filename}. ${errorMessage}`, "error");
        }
    };

    return {
        onDownload,
    };
};
