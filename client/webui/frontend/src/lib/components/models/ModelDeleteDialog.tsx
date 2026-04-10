import React, { useState } from "react";

import { Input } from "@/lib/components/ui";
import { ConfirmationDialog, MessageBanner } from "@/lib/components/common";
import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { pluginRegistry } from "@/lib/plugins";
import { DEFAULT_MODEL_ALIASES } from "./common";
import { getErrorMessage } from "@/lib/utils/api";

interface ModelDeleteDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
    modelId: string;
    modelAlias: string;
    isLoading?: boolean;
}

export const ModelDeleteDialog = React.memo<ModelDeleteDialogProps>(({ open, onOpenChange, onConfirm, modelId, modelAlias, isLoading }) => {
    const isDefaultModel = DEFAULT_MODEL_ALIASES.includes(modelAlias.toLowerCase());

    if (isDefaultModel) {
        return <DefaultModelDialog open={open} onOpenChange={onOpenChange} modelAlias={modelAlias} />;
    }

    return <ConfirmDeleteDialog open={open} onOpenChange={onOpenChange} onConfirm={onConfirm} isLoading={isLoading} modelId={modelId} modelAlias={modelAlias} />;
});

/** Default model cannot be deleted - informational dialog with Close button only */
const DefaultModelDialog: React.FC<{
    open: boolean;
    onOpenChange: (open: boolean) => void;
    modelAlias: string;
}> = ({ open, onOpenChange, modelAlias }) => {
    const displayName = modelAlias.charAt(0).toUpperCase() + modelAlias.slice(1);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-xl">
                <DialogHeader>
                    <DialogTitle>Unable to Delete</DialogTitle>
                    <DialogDescription />
                </DialogHeader>
                <div className="flex flex-col gap-3">
                    <p>The {displayName} model cannot be deleted as it is required for AI features in the platform.</p>
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="outline" title="Close">
                            Close
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

/** Confirm deletion with DELETE input - uses shared ConfirmationDialog or enterprise plugin */
const ConfirmDeleteDialog: React.FC<{
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
    isLoading?: boolean;
    modelId: string;
    modelAlias: string;
}> = ({ open, onOpenChange, onConfirm, isLoading, modelId, modelAlias }) => {
    const [confirmText, setConfirmText] = useState("");
    const [deleteError, setDeleteError] = useState<string | null>(null);

    const handleOpenChange = (isOpen: boolean) => {
        if (!isOpen) {
            setConfirmText("");
            setDeleteError(null);
        }
        onOpenChange(isOpen);
    };

    const handleConfirm = async () => {
        setDeleteError(null);
        try {
            await onConfirm();
            setConfirmText("");
        } catch (error) {
            setDeleteError(getErrorMessage(error, "An error occurred while deleting the model."));
            throw error; // Re-throw so ConfirmationDialog does not close
        }
    };

    // Check if enterprise provides a custom delete dialog
    const customDialog = pluginRegistry.getPluginById("model-delete-dialog");
    if (customDialog) {
        return <>{customDialog.render?.({ open, onOpenChange: handleOpenChange, onConfirm, isLoading, modelId, modelAlias })}</>;
    }

    return (
        <ConfirmationDialog
            open={open}
            onOpenChange={handleOpenChange}
            title="Delete Model"
            actionLabels={{ confirm: "Delete" }}
            isEnabled={confirmText === "DELETE"}
            isLoading={isLoading}
            onConfirm={handleConfirm}
            content={
                <div className="flex flex-col gap-4">
                    {deleteError && <MessageBanner variant="error" message={deleteError} dismissible onDismiss={() => setDeleteError(null)} />}
                    <p>If any code-based agents are referencing this model, they will no longer function correctly. This action cannot be undone.</p>
                    <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium">
                            Type <strong>DELETE</strong> to confirm
                        </label>
                        <Input value={confirmText} onChange={e => setConfirmText(e.target.value)} disabled={isLoading} autoComplete="off" />
                    </div>
                </div>
            }
        />
    );
};
