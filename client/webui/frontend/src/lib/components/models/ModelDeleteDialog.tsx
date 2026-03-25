import React, { useState } from "react";

import { Input } from "@/lib/components/ui";
import { ConfirmationDialog } from "@/lib/components/common";
import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { DEFAULT_MODEL_ALIASES } from "./common";

interface ModelDeleteDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
    modelAlias: string;
    isLoading?: boolean;
}

export const ModelDeleteDialog = React.memo<ModelDeleteDialogProps>(({ open, onOpenChange, onConfirm, modelAlias, isLoading }) => {
    const isDefaultModel = DEFAULT_MODEL_ALIASES.includes(modelAlias.toLowerCase());

    if (isDefaultModel) {
        return <DefaultModelDialog open={open} onOpenChange={onOpenChange} modelAlias={modelAlias} />;
    }

    return <ConfirmDeleteDialog open={open} onOpenChange={onOpenChange} onConfirm={onConfirm} isLoading={isLoading} />;
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

/** Confirm deletion with DELETE input - uses shared ConfirmationDialog */
const ConfirmDeleteDialog: React.FC<{
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
    isLoading?: boolean;
}> = ({ open, onOpenChange, onConfirm, isLoading }) => {
    const [confirmText, setConfirmText] = useState("");

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            setConfirmText("");
        }
        onOpenChange(nextOpen);
    };

    return (
        <ConfirmationDialog
            open={open}
            onOpenChange={handleOpenChange}
            title="Delete Model"
            actionLabels={{ confirm: "Delete" }}
            isEnabled={confirmText === "DELETE"}
            isLoading={isLoading}
            onConfirm={async () => {
                await onConfirm();
                setConfirmText("");
            }}
            content={
                <div className="flex flex-col gap-4">
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
