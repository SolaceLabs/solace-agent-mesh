import React from "react";
import { Pencil } from "lucide-react";

import { Button, Dialog, DialogContent, DialogFooter } from "@/lib/components/ui";
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
                <div className="space-y-6 py-6">
                    {/* Header with file info and edit button */}
                    <div className="flex items-start justify-between gap-4">
                        <div className="flex min-w-0 flex-1 items-start gap-3">
                            {getFileIcon(artifact, "h-10 w-10 flex-shrink-0 text-muted-foreground")}
                            <div className="min-w-0 flex-1">
                                <h2 className="text-foreground mb-1 text-lg font-semibold break-all">{artifact.filename}</h2>
                                <p className="text-muted-foreground text-sm">
                                    {artifact.last_modified && formatRelativeTime(artifact.last_modified)}
                                    {artifact.last_modified && " - "}
                                    {formatBytes(artifact.size)}
                                </p>
                            </div>
                        </div>
                        <Button variant="ghost" size="sm" onClick={onEdit} className="text-primary hover:text-primary flex-shrink-0 gap-2">
                            <Pencil className="h-4 w-4" />
                            Edit Description
                        </Button>
                    </div>

                    {/* Description section */}
                    <div>
                        <h3 className="text-muted-foreground mb-3 text-sm font-medium">Description</h3>
                        {artifact.description ? (
                            <div className="bg-muted/30 rounded-md p-4">
                                <p className="text-foreground text-sm whitespace-pre-wrap">{artifact.description}</p>
                            </div>
                        ) : (
                            <div className="bg-muted/30 rounded-md p-4">
                                <p className="text-muted-foreground text-sm italic">No description provided</p>
                            </div>
                        )}
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
