import type { ArtifactInfo } from "../types";
import { authenticatedFetch } from "../utils/api";
import { downloadBlob } from "../utils/download";

import { useChatContext } from "./useChatContext";
import { useConfigContext } from "./useConfigContext";
import { useProjectContext } from "../providers/ProjectProvider";

/**
 * Downloads an artifact file from the server
 * @param apiPrefix - The API prefix URL
 * @param sessionId - The session ID to download artifacts from
 * @param activeProjectId - The active project ID (for project context)
 * @param artifact - The artifact to download
 */
const downloadArtifactFile = async (
    apiPrefix: string,
    sessionId: string | null,
    activeProjectId: string | null,
    artifact: ArtifactInfo
) => {
    let url: string;

    // Priority 1: Session context (active chat)
    if (sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined") {
        url = `${apiPrefix}/api/v1/artifacts/${sessionId}/${encodeURIComponent(artifact.filename)}`;
    }
    // Priority 2: Project context (pre-session, project artifacts)
    else if (activeProjectId) {
        url = `${apiPrefix}/api/v1/artifacts/null/${encodeURIComponent(artifact.filename)}?project_id=${activeProjectId}`;
    }
    // No valid context
    else {
        throw new Error("No valid context for artifact download");
    }

    const response = await authenticatedFetch(url, {
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
export const useDownload = (projectIdOverride?: string | null) => {
    const { configServerUrl } = useConfigContext();
    const { addNotification, sessionId } = useChatContext();
    const { activeProject } = useProjectContext();

    const onDownload = async (artifact: ArtifactInfo) => {
        // Check if we have a valid context
        const hasSessionContext = sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined";
        const effectiveProjectId = projectIdOverride || activeProject?.id;
        const hasProjectContext = !!effectiveProjectId;
        
        if (!hasSessionContext && !hasProjectContext) {
            addNotification(`Cannot download artifact: No active session or project.`, "error");
            return;
        }

        try {
            await downloadArtifactFile(configServerUrl, sessionId, effectiveProjectId || null, artifact);
            addNotification(`Downloaded artifact: ${artifact.filename}.`);
        } catch {
            addNotification(`Failed to download artifact: ${artifact.filename}.`, "error");
        }
    };

    return {
        onDownload,
    };
};
