import React, { useState } from "react";

import { Button, Input, Textarea } from "@/lib/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { MessageBanner } from "@/lib/components/common";
import { getErrorMessage } from "@/lib/utils";

interface CreateProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: { name: string; description: string }) => Promise<void>;
    isSubmitting?: boolean;
}

export const CreateProjectDialog: React.FC<CreateProjectDialogProps> = ({ isOpen, onClose, onSubmit, isSubmitting = false }) => {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [nameError, setNameError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        const trimmedName = name.trim();
        if (trimmedName.length === 0) {
            setNameError("Project name is required");
            return;
        } else if (trimmedName.length > 255) {
            setNameError("Project name must be less than 255 characters");
            return;
        } else {
            setNameError(null);
        }

        try {
            await onSubmit({ name: trimmedName, description: description.trim() });
            // Reset form on success
            setName("");
            setDescription("");
            setError(null);
        } catch (err) {
            setError(getErrorMessage(err, "Failed to create project"));
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            setName("");
            setDescription("");
            setNameError(null);
            setError(null);
            onClose();
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleClose()}>
            <DialogContent className="sm:max-w-[500px]">
                <form onSubmit={handleSubmit}>
                    <DialogHeader>
                        <DialogTitle>Create New Project</DialogTitle>
                        <DialogDescription>Create a new project to organize your chats and files. You can add more details after creation.</DialogDescription>
                    </DialogHeader>

                    <div className="flex flex-col gap-4 pt-4">
                        {error && <MessageBanner variant="error" message={error} />}

                        <div>
                            <label htmlFor="project-name" className="font-medium">
                                Project Name <span className="text-[var(--color-brand-wMain)]">*</span>
                            </label>
                            <Input
                                id="project-name"
                                value={name}
                                onChange={e => {
                                    setName(e.target.value);
                                    setNameError(null);
                                }}
                                disabled={isSubmitting}
                                maxLength={256}
                                className={nameError ? "border-destructive" : ""}
                            />
                            {nameError && <div className="text-destructive text-xs">{nameError}</div>}
                        </div>

                        <div>
                            <label htmlFor="project-description" className="font-medium">
                                Description
                            </label>
                            <Textarea id="project-description" value={description} onChange={e => setDescription(e.target.value)} disabled={isSubmitting} rows={3} maxLength={1000} />
                            <div className="text-secondary-foreground text-right text-xs">{description.length}/1000</div>
                        </div>
                    </div>

                    <DialogFooter>
                        <Button type="button" variant="ghost" onClick={handleClose} disabled={isSubmitting}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSubmitting}>
                            Create Project
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};
