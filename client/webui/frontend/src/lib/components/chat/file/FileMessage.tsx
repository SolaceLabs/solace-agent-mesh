import React, { useMemo, useCallback, useContext } from "react";

import { Download, Eye } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { ChatContext, type ChatContextValue } from "@/lib/contexts/ChatContext";
import type { ArtifactInfo } from "@/lib/types";

import { getFileIcon } from "./fileUtils";

interface FileMessageProps {
    filename: string;
    mimeType?: string;
    className?: string;
    onDownload?: () => void;
    isEmbedded?: boolean;
    /**
     * When true, renders in read-only mode without requiring ChatContext.
     * Used for shared sessions where ChatProvider is not available.
     */
    readOnly?: boolean;
}

export const FileMessage: React.FC<Readonly<FileMessageProps>> = ({ filename, mimeType, className, onDownload, isEmbedded = false, readOnly = false }) => {
    // Try to get ChatContext, but don't fail if not available (for shared sessions)
    const chatContext = useContext(ChatContext) as ChatContextValue | undefined;
    const hasContext = chatContext !== undefined && !readOnly;

    const artifacts = hasContext ? chatContext.artifacts : [];
    const setPreviewArtifact = hasContext ? chatContext.setPreviewArtifact : undefined;
    const openSidePanelTab = hasContext ? chatContext.openSidePanelTab : undefined;

    const artifact: ArtifactInfo | undefined = useMemo(() => artifacts.find((a: ArtifactInfo) => a.filename === filename), [artifacts, filename]);
    const FileIcon = useMemo(() => getFileIcon(artifact || { filename, mime_type: mimeType || "", size: 0, last_modified: "" }), [artifact, filename, mimeType]);

    const handlePreviewClick = useCallback(
        (e: React.MouseEvent) => {
            e.stopPropagation();
            if (artifact && setPreviewArtifact && openSidePanelTab) {
                openSidePanelTab("files");
                setPreviewArtifact(artifact);
            }
        },
        [artifact, openSidePanelTab, setPreviewArtifact]
    );

    const handleDownloadClick = useCallback(() => {
        if (onDownload) {
            onDownload();
        }
    }, [onDownload]);

    return (
        <div className={`flex h-11 max-w-xs flex-shrink items-center gap-2 rounded-lg bg-[var(--message-background)] px-2 py-1 ${className || ""}`}>
            {FileIcon}
            <span className="min-w-0 flex-1 truncate text-sm leading-9" title={filename}>
                <strong>
                    <code>{filename}</code>
                </strong>
            </span>

            {artifact && !isEmbedded && !readOnly && setPreviewArtifact && (
                <Button variant="ghost" onClick={handlePreviewClick} tooltip="Preview">
                    <Eye className="h-4 w-4" />
                </Button>
            )}

            {onDownload && (
                <Button variant="ghost" onClick={handleDownloadClick} tooltip="Download file">
                    <Download className="h-4 w-4" />
                </Button>
            )}
        </div>
    );
};
