import React, { useMemo } from "react";

import { Download, Eye } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { useChatContext } from "@/lib/hooks";
import type { ArtifactInfo, FileAttachment } from "@/lib/types";
import { downloadFile } from "@/lib/utils/download";

import { getFileIcon } from "./fileUtils";

interface FileAttachmentMessageProps {
    fileAttachment: FileAttachment;
}

export const FileAttachmentMessage: React.FC<Readonly<FileAttachmentMessageProps>> = ({ fileAttachment }) => {
    return <FileMessage filename={fileAttachment.name} onDownload={() => downloadFile(fileAttachment)} className="ml-4" />;
};

interface FileMessageProps {
    filename: string;
    className?: string;
    onDownload?: () => void;
}

export const FileMessage: React.FC<Readonly<FileMessageProps>> = ({ filename, className, onDownload }) => {
    const { artifacts, setPreviewArtifact, openSidePanelTab } = useChatContext();

    const artifact: ArtifactInfo | undefined = useMemo(() => artifacts.find(artifact => artifact.filename === filename), [artifacts, filename]);
    const FileIcon = useMemo(() => getFileIcon(artifact), [artifact]);

    return (
        <div className={`flex flex-shrink items-center gap-2 rounded-lg bg-[var(--accent-background)] px-2 py-1 h-11 max-w-xs ${className || ""}`}>
            {FileIcon}
            <span className="min-w-0 flex-1 truncate text-sm leading-9" title={filename}>
                <strong>
                    <code>{filename}</code>
                </strong>
            </span>

            {artifact && (
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
