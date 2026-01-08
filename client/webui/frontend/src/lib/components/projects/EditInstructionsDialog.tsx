import React, { useState, useEffect } from "react";
import { AlertCircle } from "lucide-react";

import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/lib/components/ui/dialog";
import { Button, Textarea } from "@/lib/components/ui";
import type { Project } from "@/lib/types/projects";
import { useConfigContext } from "@/lib/hooks";

interface EditInstructionsDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onSave: (systemPrompt: string) => Promise<void>;
    project: Project;
    isSaving: boolean;
    error?: string | null;
}

export const EditInstructionsDialog: React.FC<EditInstructionsDialogProps> = ({
    isOpen,
    onClose,
    onSave,
    project,
    isSaving,
    error,
}) => {
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
    const isNearLimit = characterCount > MAX_INSTRUCTIONS_LENGTH * 0.9;

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && handleCancel()}>
            <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Edit Project Instructions</DialogTitle>
                    <DialogDescription>
                        Provide instructions that will guide the AI when working with this project.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 min-h-0 space-y-3">
                    <div className="relative">
                        <Textarea
                            value={editedPrompt}
                            onChange={(e) => setEditedPrompt(e.target.value)}
                            placeholder="Add instructions for this project..."
                            rows={15}
                            disabled={isSaving}
                            className={`text-sm resize-none ${isOverLimit ? 'border-destructive focus-visible:ring-destructive' : ''}`}
                        />
                        <div className={`mt-1 text-xs ${isOverLimit ? 'text-destructive font-medium' : isNearLimit ? 'text-orange-500' : 'text-muted-foreground'}`}>
                            {isOverLimit
                                ? `Instructions must be less than ${MAX_INSTRUCTIONS_LENGTH} characters (currently ${characterCount})`
                                : `${characterCount} / ${MAX_INSTRUCTIONS_LENGTH} characters`
                            }
                        </div>
                    </div>
                    {localError && (
                        <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                            <AlertCircle className="h-4 w-4 flex-shrink-0" />
                            <span>{localError}</span>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={handleCancel}
                        disabled={isSaving}
                    >
                        Discard Changes
                    </Button>
                    <Button
                        onClick={handleSave}
                        disabled={isSaving || isOverLimit}
                    >
                        Save
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};