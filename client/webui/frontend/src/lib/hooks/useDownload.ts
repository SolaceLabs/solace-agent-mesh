import type { ArtifactInfo } from "../types";
import { fetchWithError, getErrorMessage } from "../utils/api";
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
const downloadArtifactFile = async (apiPrefix: string, sessionId: string | null, activeProjectId: string | null, artifact: ArtifactInfo) => {
    const hasSessionContext = sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined";

    let url: string;
    // Priority 1: Session context (active chat)
    if (hasSessionContext) {
        url = `${apiPrefix}/api/v1/artifacts/${sessionId.trim()}/${encodeURIComponent(artifact.filename)}`;
    }
    // Priority 2: Project context (pre-session, project artifacts)
    else if (activeProjectId) {
        url = `${apiPrefix}/api/v1/artifacts/null/${encodeURIComponent(artifact.filename)}?project_id=${activeProjectId}`;
    }
    // No valid context
    else {
        throw new Error("No valid session or project context for downloading artifact.");
    }

    const response = await fetchWithError(url);
    const blob = await response.blob();

    downloadBlob(blob, artifact.filename);
};

/**
 * Custom hook to handle artifact downloads
 * @returns Object containing download handler function
 */
export const useDownload = (projectIdOverride?: string | null) => {
    const { configServerUrl } = useConfigContext();
    const { addNotification, sessionId, displayError } = useChatContext();
    const { activeProject } = useProjectContext();

    const onDownload = async (artifact: ArtifactInfo) => {
        try {
            const effectiveProjectId = projectIdOverride || activeProject?.id || null;

            await downloadArtifactFile(configServerUrl, sessionId, effectiveProjectId, artifact);
            addNotification(`Downloaded artifact: ${artifact.filename}.`, "success");
        } catch (error) {
            displayError({ title: "Failed to Download Artifact", error: getErrorMessage(error, "An unknown error occurred while downloading the artifact.") });
        }
    };

    return {
        onDownload,
    };
};
