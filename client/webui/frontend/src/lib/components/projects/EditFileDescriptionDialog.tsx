import React, { useState, useEffect } from "react";

import { Button, Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, Textarea } from "@/lib/components/ui";
import type { ArtifactInfo } from "@/lib/types";

import { FileLabel } from "../chat/file/FileLabel";

interface EditFileDescriptionDialogProps {
    isOpen: boolean;
    artifact: ArtifactInfo | null;
    onClose: () => void;
    onSave: (description: string) => Promise<void>;
    isSaving?: boolean;
}

export const EditFileDescriptionDialog: React.FC<EditFileDescriptionDialogProps> = ({ isOpen, artifact, onClose, onSave, isSaving = false }) => {
    const [description, setDescription] = useState("");

    useEffect(() => {
        if (isOpen && artifact) {
            setDescription(artifact.description || "");
        }
    }, [isOpen, artifact]);

    const handleSave = async () => {
        await onSave(description);
    };

    const handleCancel = () => {
        setDescription(artifact?.description || "");
        onClose();
    };

    if (!artifact) return null;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle>Edit File Description</DialogTitle>
                    <DialogDescription>Update the description for this file to help Solace Agent Mesh understand its purpose.</DialogDescription>
                </DialogHeader>
                <div className="py-4">
                    <FileLabel fileName={artifact.filename} fileSize={artifact.size} />
                    <Textarea className="mt-2" rows={2} disabled={isSaving} value={description} onChange={e => setDescription(e.target.value)} />
                </div>
                <DialogFooter>
                    <Button variant="ghost" onClick={handleCancel} disabled={isSaving}>
                        Discard Changes
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                        {isSaving ? "Saving..." : "Save"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
