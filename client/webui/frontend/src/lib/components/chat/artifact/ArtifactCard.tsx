import React from "react";

import type { ArtifactInfo } from "@/lib/types";
import { ArtifactMessage } from "../file/ArtifactMessage";
import { useChatContext } from "@/lib/hooks";

interface ArtifactCardProps {
    artifact: ArtifactInfo;
    isPreview?: boolean;
    readOnly?: boolean;
    onDownloadOverride?: () => Promise<void>;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ artifact, isPreview, readOnly = false, onDownloadOverride }) => {
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
        <div
            className={`${isPreview ? "" : "cursor-pointer transition-all duration-150 hover:bg-(--background-w20)"}`}
            onClick={handleClick}
            onKeyDown={
                !isPreview
                    ? e => {
                          if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setPreviewArtifact(artifact);
                          }
                      }
                    : undefined
            }
            role={!isPreview ? "button" : undefined}
            tabIndex={!isPreview ? 0 : undefined}
        >
            <ArtifactMessage status="completed" name={artifact.filename} fileAttachment={fileAttachment} context="list" readOnly={readOnly} onDownloadOverride={onDownloadOverride} />
        </div>
    );
};
