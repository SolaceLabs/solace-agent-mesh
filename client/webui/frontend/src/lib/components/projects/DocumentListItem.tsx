import React from "react";
import { Download, Trash } from "lucide-react";

import { Button, Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/lib/components/ui";
import { formatBytes, formatRelativeTime } from "@/lib/utils/format";
import type { ArtifactInfo } from "@/lib/types";
import { getFileIcon } from "../chat/file/fileUtils";

interface DocumentListItemProps {
    artifact: ArtifactInfo;
    onDownload: () => void;
    onDelete?: () => void;
}

export const DocumentListItem: React.FC<DocumentListItemProps> = ({ artifact, onDownload, onDelete }) => {
    return (
        <div className="hover:bg-accent/50 group flex items-center justify-between rounded-md p-2">
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
                <Button variant="ghost" size="sm" onClick={onDownload} className="h-8 w-8 p-0" tooltip="Download">
                    <Download className="h-4 w-4" />
                </Button>
                {onDelete && (
                    <Dialog>
                        <DialogTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" tooltip="Delete">
                                <Trash className="h-4 w-4" />
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Delete {artifact.filename}?</DialogTitle>
                                <DialogDescription>This action cannot be undone. This file will be permanently removed from the project.</DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                                <DialogClose asChild>
                                    <Button variant="ghost" title="Cancel">
                                        Cancel
                                    </Button>
                                </DialogClose>
                                <Button variant="outline" onClick={onDelete} title="Delete">
                                    Delete
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                )}
            </div>
        </div>
    );
};
