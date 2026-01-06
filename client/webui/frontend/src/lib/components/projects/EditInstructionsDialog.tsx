import React, { useState, useEffect } from "react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button, Textarea } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { useConfigContext } from "@/lib/hooks";
import { MessageBanner } from "../common";

interface EditInstructionsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (systemPrompt: string) => Promise<void>;
    project: Project;
    isSaving: boolean;
    error?: string | null;
}

export const EditInstructionsDialog: React.FC<EditInstructionsDialogProps> = ({ isOpen, onClose, onSave, project, isSaving, error }) => {
    const { validationLimits } = useConfigContext();
    const MAX_INSTRUCTIONS_LENGTH = validationLimits?.projectInstructionsMax ?? 4000;

    const [editedPrompt, setEditedPrompt] = useState(project.systemPrompt || "");
    const [localError, setLocalError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen) {
            setEditedPrompt(project.systemPrompt || "");
            setLocalError(null);
        }
    }, [isOpen, project.systemPrompt]);

    useEffect(() => {
        if (error) {
            setLocalError(error);
        }
    }, [error]);

    const handleSave = async () => {
        setLocalError(null);

        if (editedPrompt.trim() !== (project.systemPrompt || "")) {
            try {
                await onSave(editedPrompt.trim());
                onClose();
            } catch {
                // Error will be handled by parent component
            }
        } else {
            onClose();
        }
    };

    const handleCancel = () => {
        setEditedPrompt(project.systemPrompt || "");
        setLocalError(null);
        onClose();
    };

    const characterCount = editedPrompt.length;
    const isOverLimit = characterCount > MAX_INSTRUCTIONS_LENGTH;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleCancel()}>
            <DialogContent className="flex max-h-[80vh] max-w-3xl flex-col">
                <DialogHeader>
                    <DialogTitle>Edit Project Instructions</DialogTitle>
                    <DialogDescription>Provide instructions that will guide the AI when working with this project.</DialogDescription>
                </DialogHeader>

                <div className="min-h-0 flex-1 pt-4">
                    <div className="relative">
                        <Textarea
                            value={editedPrompt}
                            onChange={e => setEditedPrompt(e.target.value)}
                            placeholder="Add instructions for this project..."
                            rows={15}
                            disabled={isSaving}
                            maxLength={MAX_INSTRUCTIONS_LENGTH + 1}
                            className={`resize-none text-sm ${isOverLimit ? "border-destructive" : ""}`}
                        />
                        <div className={`text-xs ${isOverLimit ? "text-destructive" : "text-muted-foreground text-right"}`}>
                            {isOverLimit && `Instructions must be less than ${MAX_INSTRUCTIONS_LENGTH} characters`}
                            {!isOverLimit && `${characterCount} / ${MAX_INSTRUCTIONS_LENGTH}`}
                        </div>
                    </div>
                    {localError && <MessageBanner variant="error" message={localError} className="py-3" />}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
                        Discard Changes
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving || isOverLimit}>
                        Save
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
