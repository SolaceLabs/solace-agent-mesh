import React, { useMemo } from "react";

import { Download, Eye } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";
import { downloadFile } from "@/lib/utils/download";

import { getFileIcon } from "./fileUtils";

interface FileAttachmentMessageProps {
    fileAttachment: FileAttachment;
    isEmbedded?: boolean;
}

export const FileAttachmentMessage: React.FC<Readonly<FileAttachmentMessageProps>> = ({ fileAttachment, isEmbedded = false }) => {
    return <FileMessage filename={fileAttachment.name} mimeType={fileAttachment.mime_type} onDownload={() => downloadFile(fileAttachment)} className="ml-4" isEmbedded={isEmbedded} />;
};

interface FileMessageProps {
    filename: string;
    mimeType?: string;
    className?: string;
    onDownload?: () => void;
    isEmbedded?: boolean;
}

export const FileMessage: React.FC<Readonly<FileMessageProps>> = ({ filename, mimeType, className, onDownload, isEmbedded = false }) => {
    const { artifacts, setPreviewArtifact, openSidePanelTab } = useChatContext();

    const artifact: ArtifactInfo | undefined = useMemo(() => artifacts.find(artifact => artifact.filename === filename), [artifacts, filename]);
    const FileIcon = useMemo(() => getFileIcon(artifact || { filename, mime_type: mimeType || "", size: 0, last_modified: "" }), [artifact, filename, mimeType]);

    return (
        <div className={`flex h-11 max-w-xs flex-shrink items-center gap-2 rounded-lg bg-[var(--accent-background)] px-2 py-1 ${className || ""}`}>
            {FileIcon}
            <span className="min-w-0 flex-1 truncate text-sm leading-9" title={filename}>
                <strong>
                    <code>{filename}</code>
                </strong>
            </span>

            {artifact && !isEmbedded && (
                <Button
                    variant="ghost"
                    onClick={e => {
                        e.stopPropagation();
                        openSidePanelTab("files");
                        setPreviewArtifact(artifact);
                    }}
                    tooltip="Preview"
                >
                    <Eye className="h-4 w-4" />
                </Button>
            )}

            {onDownload && (
                <Button variant="ghost" onClick={() => onDownload()} tooltip="Download file">
                    <Download className="h-4 w-4" />
                </Button>
            )}
        </div>
    );
};
