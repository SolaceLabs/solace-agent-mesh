import React from "react";

import type { ArtifactInfo } from "@/lib/types";
import { ArtifactMessage } from "../file/ArtifactMessage";
import { useChatContext } from "@/lib/hooks";

interface ArtifactCardProps {
    artifact: ArtifactInfo;
    isPreview?: boolean;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact, isPreview }) => {
    const { setPreviewArtifact } = useChatContext();

    // Create a FileAttachment from the ArtifactInfo
    const fileAttachment = {
        name: artifact.filename,
        mime_type: artifact.mime_type,
        size: artifact.size,
        uri: artifact.uri,
    };

    const handleClick = (e: React.MouseEvent) => {
        if (!isPreview) {
            e.stopPropagation();
            setPreviewArtifact(artifact);
        }
    };

    return (
        <div className={`${isPreview ? "" : "cursor-pointer transition-all duration-150 hover:bg-[var(--accent-background)]"}`} onClick={handleClick}>
            <ArtifactMessage status="completed" name={artifact.filename} fileAttachment={fileAttachment} context="list" />
        </div>
    );
};
