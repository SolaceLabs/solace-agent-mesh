import React, { useState } from "react";

import { Button, Input, Textarea } from "@/lib/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";

interface CreateProjectDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onSubmit: (data: { name: string; description: string }) => Promise<void>;
    isSubmitting?: boolean;
}

export const CreateProjectDialog: React.FC<CreateProjectDialogProps> = ({
    isOpen,
    onClose,
    onSubmit,
    isSubmitting = false,
}) => {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!name.trim()) {
            setError("Project name is required");
            return;
        }

        try {
            await onSubmit({ name: name.trim(), description: description.trim() });
            // Reset form on success
            setName("");
            setDescription("");
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to create project");
        }
    };

    const handleClose = () => {
        if (!isSubmitting) {
            setName("");
            setDescription("");
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
                        <DialogDescription>
                            Create a new project to organize your chats and files. You can add more details after creation.
                        </DialogDescription>
                    </DialogHeader>
                    
                    <div className="space-y-4 py-4">
                        {error && (
                            <div className="text-sm text-red-500 bg-red-50 dark:bg-red-900/20 p-2 rounded">
                                {error}
                            </div>
                        )}
                        
                        <div className="space-y-2">
                            <label htmlFor="project-name" className="text-sm font-medium">
                                Project Name <span className="text-red-500">*</span>
                            </label>
                            <Input
                                id="project-name"
                                value={name}
                                onChange={e => setName(e.target.value)}
                                disabled={isSubmitting}
                                required
                            />
                        </div>
                        
                        <div className="space-y-2">
                            <label htmlFor="project-description" className="text-sm font-medium">
                                Description
                            </label>
                            <Textarea
                                id="project-description"
                                value={description}
                                onChange={e => setDescription(e.target.value)}
                                disabled={isSubmitting}
                                rows={3}
                            />
                        </div>
                    </div>
                    
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="ghost"
                            onClick={handleClose}
                            disabled={isSubmitting}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSubmitting}>
                            {isSubmitting ? "Creating..." : "Create Project"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};
