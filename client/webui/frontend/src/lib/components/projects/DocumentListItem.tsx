import React, { useState } from "react";
import { Download, Trash, Pencil } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { formatBytes, formatRelativeTime } from "@/lib/utils/format";
import type { ArtifactInfo } from "@/lib/types";
import { getFileIcon } from "../chat/file/fileUtils";
import { ConfirmationDialog } from "../common";

interface DocumentListItemProps {
    artifact: ArtifactInfo;
    onDownload: () => void;
    onDelete?: () => void;
    onClick?: () => void;
    onEditDescription?: () => void;
}

export const DocumentListItem: React.FC<DocumentListItemProps> = ({ artifact, onDownload, onDelete, onClick, onEditDescription }) => {
    const [showDeleteDialog, setShowDeleteDialog] = useState(false);

    return (
        <>
            <div className={`hover:bg-accent/50 group flex items-center justify-between rounded-md p-2 ${onClick ? "cursor-pointer" : ""}`} onClick={onClick}>
                <div className="flex min-w-0 flex-1 items-center gap-2">
                    {getFileIcon(artifact, "h-4 w-4 flex-shrink-0 text-muted-foreground")}
                    <div className="min-w-0 flex-1">
                        <p className="text-foreground truncate text-sm font-medium" title={artifact.filename}>
                            {artifact.filename}
                        </p>
                        <div className="text-muted-foreground flex items-center gap-2 text-xs">
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
                <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    {onEditDescription && (
                        <Button
                            variant="ghost"
                            onClick={e => {
                                e.stopPropagation();
                                onEditDescription();
                            }}
                            tooltip="Edit Description"
                        >
                            <Pencil />
                        </Button>
                    )}
                    <Button
                        variant="ghost"
                        onClick={e => {
                            e.stopPropagation();
                            onDownload();
                        }}
                        tooltip="Download"
                    >
                        <Download />
                    </Button>
                    {onDelete && (
                        <Button
                            variant="ghost"
                            tooltip="Delete"
                            onClick={e => {
                                e.stopPropagation();
                                setShowDeleteDialog(true);
                            }}
                        >
                            <Trash />
                        </Button>
                    )}
                </div>
            </div>
            {onDelete && (
                <ConfirmationDialog
                    title="Delete Project File"
                    content={
                        <>
                            This action cannot be undone. This file will be permanently removed from the project: <strong>{artifact.filename}</strong>
                        </>
                    }
                    actionLabels={{ confirm: "Delete" }}
                    open={showDeleteDialog}
                    onConfirm={onDelete}
                    onOpenChange={setShowDeleteDialog}
                />
            )}
        </>
    );
};
