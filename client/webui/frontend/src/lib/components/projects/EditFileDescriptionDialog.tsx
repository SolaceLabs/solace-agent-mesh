import React, { useState, useEffect } from "react";

import { Textarea } from "@/lib/components/ui";
import { ConfirmationDialog } from "@/lib/components/common";
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

    const dialogContent = (
        <div className="my-5 flex flex-col gap-4">
            <FileLabel fileName={artifact.filename} fileSize={artifact.size} />
            <div>
                <Textarea className="mt-1" rows={2} disabled={isSaving} value={description} onChange={e => setDescription(e.target.value)} />
            </div>
        </div>
    );

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={open => !open && onClose()}
            title="Edit Project File Description"
            description="Update the description to help Solace Agent Mesh understand its purpose."
            content={dialogContent}
            actionLabels={{
                cancel: "Discard Changes",
                confirm: "Save",
            }}
            isLoading={isSaving}
            onConfirm={handleSave}
            onCancel={handleCancel}
        />
    );
};
