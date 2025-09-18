import type { ArtifactInfo } from "../types";
import { authenticatedFetch } from "../utils/api";
import { downloadBlob } from "../utils/download";

import { useChatContext } from "./useChatContext";
import { useConfigContext } from "./useConfigContext";

/**
 * Downloads an artifact file from the server
 * @param apiPrefix - The API prefix URL
 * @param sessionId - The session ID to download artifacts from
 * @param artifact - The artifact to download
 */
const downloadArtifactFile = async (apiPrefix: string, sessionId: string, artifact: ArtifactInfo) => {
    const response = await authenticatedFetch(`${apiPrefix}/api/v1/artifacts/${sessionId}/${encodeURIComponent(artifact.filename)}`, {
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

    const onDownload = async (artifact: ArtifactInfo) => {
        if (!sessionId) {
            addNotification(`Cannot download artifact: No active session.`, "error");
            return;
        }

        try {
            await downloadArtifactFile(configServerUrl, sessionId, artifact);
            addNotification(`Downloaded artifact: ${artifact.filename}.`);
        } catch {
            addNotification(`Failed to download artifact: ${artifact.filename}.`, "error");
        }
    };

    return {
        onDownload,
    };
};
