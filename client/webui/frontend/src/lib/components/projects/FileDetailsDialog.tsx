import React from "react";
import { Pencil } from "lucide-react";

import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, VisuallyHidden } from "@/lib/components/ui";
import { formatBytes, formatRelativeTime } from "@/lib/utils/format";
import type { ArtifactInfo } from "@/lib/types";
import { getFileIcon } from "../chat/file/fileUtils";

interface FileDetailsDialogProps {
    isOpen: boolean;
    artifact: ArtifactInfo | null;
    onClose: () => void;
    onEdit: () => void;
}

export const FileDetailsDialog: React.FC<FileDetailsDialogProps> = ({ isOpen, artifact, onClose, onEdit }) => {
    if (!artifact) return null;

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[700px]">
                <DialogHeader>
                    <div className="flex justify-between gap-4">
                        <div className="flex min-w-0 flex-1 gap-2">
                            {getFileIcon(artifact, "flex-shrink-0 text-muted-foreground")}
                            <div className="min-w-0 flex-1">
                                <DialogTitle className="max-w-[400px] truncate" title={artifact.filename}>
                                    {artifact.filename}
                                </DialogTitle>
                                <div className="text-muted-foreground mt-1 flex flex-row gap-2 text-sm font-medium">
                                    <div>{artifact.last_modified ? formatRelativeTime(artifact.last_modified) : null}</div>
                                    <div>{formatBytes(artifact.size)}</div>
                                </div>
                            </div>
                        </div>
                        <Button variant="ghost" size="sm" onClick={onEdit} className="flex-shrink-0 gap-2 text-sm">
                            <Pencil className="h-4 w-4" />
                            Edit Description
                        </Button>
                    </div>
                    <VisuallyHidden>
                        <DialogDescription>Project File Information</DialogDescription>
                    </VisuallyHidden>
                </DialogHeader>
                <div className="my-6">
                    <div className="text-secondary-foreground">Description</div>
                    <div className="py-2">
                        <div className="text-sm whitespace-pre-wrap">{artifact.description || "No description provided"}</div>
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
