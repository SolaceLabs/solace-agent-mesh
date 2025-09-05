import React, { useMemo } from "react";

import { useChatContext, useDownload } from "@/lib/hooks";
import type { ArtifactInfo } from "@/lib/types";

import { FileMessage } from "../file";

interface ArtifactNotificationMessageProps {
    artifactName: string;
    mimeType?: string;
}

export const ArtifactNotificationMessage: React.FC<ArtifactNotificationMessageProps> = ({ artifactName, mimeType }) => {
    const { artifacts } = useChatContext();
    const { onDownload } = useDownload();

    // The full artifact info might not be in the list yet if the notification arrives before the list is refetched.
    // We can render a basic file capsule using the name and mime_type from the notification itself.
    const artifact: ArtifactInfo | undefined = useMemo(() => {
        return artifacts.find(art => art.filename === artifactName);
    }, [artifacts, artifactName]);

    const handleDownload = () => {
        if (artifact) {
            onDownload(artifact);
        } else {
            // This case should be rare, but as a fallback, we can't download without full info.
            // A better implementation might be to trigger a fetch for this specific artifact.
            console.warn("Download clicked but full artifact info not available yet.");
        }
    };

    // If we have the full artifact info, we can provide a richer experience (e.g., correct size for download).
    // If not, we render a slightly degraded but still functional capsule.
    const artifactForDisplay: ArtifactInfo = artifact || {
        filename: artifactName,
        mime_type: mimeType || "application/octet-stream",
        size: 0, // Size is unknown until refetched
        last_modified: new Date().toISOString(),
    };

    // The FileMessage component can handle previewing based on the artifact being present in the main list.
    // The download button is handled locally here.
    return <FileMessage filename={artifactForDisplay.filename} mimeType={artifactForDisplay.mime_type} onDownload={handleDownload} isEmbedded={false} className="ml-4" />;
};
