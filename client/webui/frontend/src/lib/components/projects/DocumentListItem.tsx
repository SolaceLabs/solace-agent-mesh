import React from "react";
import { Download, Trash } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { formatBytes, formatRelativeTime } from "@/lib/utils/format";
import type { ArtifactInfo } from "@/lib/types";
import { getFileIcon } from "../chat/file/fileUtils";

interface DocumentListItemProps {
    artifact: ArtifactInfo;
    onDownload: () => void;
    onDelete?: () => void;
}

export const DocumentListItem: React.FC<DocumentListItemProps> = ({
    artifact,
    onDownload,
    onDelete,
}) => {
    return (
        <div className="flex items-center justify-between p-2 hover:bg-accent/50 rounded-md group">
            <div className="flex items-center gap-2 min-w-0 flex-1">
                {getFileIcon(artifact, "h-4 w-4 flex-shrink-0 text-muted-foreground")}
                <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground truncate" title={artifact.filename}>
                        {artifact.filename}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {artifact.last_modified && (
                            <span className="truncate" title={formatRelativeTime(artifact.last_modified)}>
                                {formatRelativeTime(artifact.last_modified)}
                            </span>
                        )}
                        {artifact.size !== undefined && (
                            <>
                                {artifact.last_modified && <span>•</span>}
                                <span>{formatBytes(artifact.size)}</span>
                            </>
                        )}
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onDownload}
                    className="h-8 w-8 p-0"
                    tooltip="Download"
                >
                    <Download className="h-4 w-4" />
                </Button>
                {onDelete && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onDelete}
                        className="h-8 w-8 p-0"
                        tooltip="Delete"
                    >
                        <Trash className="h-4 w-4" />
                    </Button>
                )}
            </div>
        </div>
    );
};
