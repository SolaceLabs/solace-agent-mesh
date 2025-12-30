import React, { useState } from "react";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";

export interface BatchDeleteSessionDialogProps {
    sessionCount: number;
    onClose: () => void;
    onConfirm: () => Promise<void>;
    isOpen: boolean;
}

export const BatchDeleteSessionDialog = React.memo<BatchDeleteSessionDialogProps>(({ isOpen, onClose, onConfirm, sessionCount }) => {
    const [isDeleting, setIsDeleting] = useState(false);

    const handleConfirm = async () => {
        setIsDeleting(true);
        try {
            await onConfirm();
        } catch (error) {
            console.error("Failed to batch delete sessions:", error);
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <ConfirmationDialog
            open={isOpen}
            onOpenChange={open => !open && onClose()}
            title={`Delete ${sessionCount} Chat${sessionCount > 1 ? "s" : ""}`}
            content={
                <>
                    This action cannot be undone. {sessionCount > 1 ? "These" : "This"} chat session{sessionCount > 1 ? "s" : ""} and any associated artifacts will be permanently deleted.
                </>
            }
            actionLabels={{
                confirm: isDeleting ? "Deleting..." : "Delete",
            }}
            isLoading={isDeleting}
            onConfirm={handleConfirm}
        />
    );
});

BatchDeleteSessionDialog.displayName = "BatchDeleteSessionDialog";
