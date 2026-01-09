import React from "react";
import { Pencil } from "lucide-react";

import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, VisuallyHidden } from "@/lib/components/ui";
import type { ArtifactInfo } from "@/lib/types";
import { FileLabel } from "../chat/file/FileLabel";

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
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <div className="flex justify-between">
                        <h2 className="text-lg font-semibold">Project File Details</h2>
                        <Button variant="ghost" size="sm" onClick={onEdit} className="flex-shrink-0 gap-2 text-sm">
                            <Pencil className="h-4 w-4" />
                            Edit Description
                        </Button>
                    </div>
                    <VisuallyHidden>
                        <DialogTitle>Project File Details</DialogTitle>
                        <DialogDescription>Project File Information</DialogDescription>
                    </VisuallyHidden>
                </DialogHeader>

                <div className="my-5 flex flex-col gap-2 overflow-hidden">
                    <FileLabel fileName={artifact.filename} fileSize={artifact.size} />
                    <div>
                        <div className="text-secondary-foreground my-1">Description:</div>
                        <div className="max-h-[50vh] overflow-y-auto text-sm whitespace-pre-wrap">{artifact.description || "No description provided"}</div>
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
