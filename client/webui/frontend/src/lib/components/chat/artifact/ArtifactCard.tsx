import React from "react";

import type { ArtifactInfo } from "@/lib/types";
import { ArtifactMessage } from "../file/ArtifactMessage";

interface ArtifactCardProps {
    artifact: ArtifactInfo;
    isPreview?: boolean;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact, isPreview }) => {
    // Create a FileAttachment from the ArtifactInfo
    const fileAttachment = {
        name: artifact.filename,
        mime_type: artifact.mime_type,
        size: artifact.size,
        uri: artifact.uri,
    };

    return (
        <div
            className={`${isPreview ? "" : "cursor-pointer hover:bg-[var(--accent-background)] transition-all duration-150"}`}
            onClick={e => {
                if (!isPreview) {
                    e.stopPropagation();
                    // The preview functionality is handled by the ArtifactMessage component
                }
            }}
        >
            <ArtifactMessage
                status="completed"
                name={artifact.filename}
                fileAttachment={fileAttachment}
                context={isPreview ? "chat" : "list"}
            />
        </div>
    );
};
