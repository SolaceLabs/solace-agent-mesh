import React from "react";

import { ConfirmationDialog } from "../common";

interface PromptDeleteDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    promptName: string;
}

export const PromptDeleteDialog = React.memo<PromptDeleteDialogProps>(({ isOpen, onClose, onConfirm, promptName }) => {
    return (
        <ConfirmationDialog
            title="Delete Prompt"
            content={
                <>
                    This action cannot be undone. This will permanently delete the prompt and all its versions: <strong>{promptName}</strong>.
                </>
            }
            actionLabels={{ confirm: "Delete" }}
            open={isOpen}
            onOpenChange={open => !open && onClose()}
            onConfirm={onConfirm}
            onCancel={onClose}
        />
    );
});
