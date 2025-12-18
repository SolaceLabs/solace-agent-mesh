import type { ArtifactInfo } from "../types";
import { api } from "@/lib/api";
import { getErrorMessage } from "../utils/api";
import { downloadBlob } from "../utils/download";
import { useChatContext } from "./useChatContext";
import { useProjectContext } from "../providers/ProjectProvider";

const downloadArtifactFile = async (sessionId: string | null, activeProjectId: string | null, artifact: ArtifactInfo) => {
    const hasSessionContext = sessionId && sessionId.trim() && sessionId !== "null" && sessionId !== "undefined";

    let endpoint: string;
    if (hasSessionContext) {
        endpoint = `/api/v1/artifacts/${sessionId.trim()}/${encodeURIComponent(artifact.filename)}`;
    } else if (activeProjectId) {
        endpoint = `/api/v1/artifacts/null/${encodeURIComponent(artifact.filename)}?project_id=${activeProjectId}`;
    } else {
        throw new Error("No valid session or project context for downloading artifact.");
    }

    const response = await api.webui.get(endpoint, { fullResponse: true });
    if (!response.ok) {
        throw new Error(`Failed to download artifact: ${response.statusText}`);
    }
    const blob = await response.blob();
    downloadBlob(blob, artifact.filename);
};

export const useDownload = (projectIdOverride?: string | null) => {
    const { addNotification, sessionId, displayError } = useChatContext();
    const { activeProject } = useProjectContext();

    const onDownload = async (artifact: ArtifactInfo) => {
        try {
            const effectiveProjectId = projectIdOverride || activeProject?.id || null;
            await downloadArtifactFile(sessionId, effectiveProjectId, artifact);
            addNotification(`Downloaded artifact: ${artifact.filename}.`, "success");
        } catch (error) {
            displayError({ title: "Failed to Download Artifact", error: getErrorMessage(error, "An unknown error occurred while downloading the artifact.") });
        }
    };

    return { onDownload };
};
