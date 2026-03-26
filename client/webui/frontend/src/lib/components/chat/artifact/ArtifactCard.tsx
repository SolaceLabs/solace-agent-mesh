import type { MouseEvent } from "react";

import type { ArtifactInfo } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ArtifactMessage } from "../file/ArtifactMessage";
import { useChatContext } from "@/lib/hooks";

interface ArtifactCardProps {
    artifact: ArtifactInfo;
    isPreview?: boolean;
    readOnly?: boolean;
    onDownloadOverride?: () => Promise<void>;
}

export const ArtifactCard = ({ artifact, isPreview, readOnly = false, onDownloadOverride }: ArtifactCardProps) => {
    const { setPreviewArtifact } = useChatContext();

    // Create a FileAttachment from the ArtifactInfo
    const fileAttachment = {
        name: artifact.filename,
        mime_type: artifact.mime_type,
        size: artifact.size,
        uri: artifact.uri,
    };

    const handleClick = (e: MouseEvent) => {
        if (!isPreview) {
            e.stopPropagation();
            setPreviewArtifact(artifact);
        }
    };

    return (
        <div
            className={cn(!isPreview && "cursor-pointer transition-all duration-150 hover:bg-(--background-w20)")}
            onClick={handleClick}
            onKeyDown={e => e.key === "Enter" && handleClick(e as unknown as MouseEvent)}
            role={!isPreview ? "button" : undefined}
            tabIndex={!isPreview ? 0 : undefined}
        >
            <ArtifactMessage status="completed" name={artifact.filename} fileAttachment={fileAttachment} context="list" readOnly={readOnly} onDownloadOverride={onDownloadOverride} />
        </div>
    );
};
