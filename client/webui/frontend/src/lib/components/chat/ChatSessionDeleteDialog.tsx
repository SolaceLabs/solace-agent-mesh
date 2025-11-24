import React from "react";
import { ConfirmationDialog, type ConfirmationDialogProps } from "@/lib/components/common/ConfirmationDialog";

export interface ChatSessionDeleteDialogProps extends Omit<ConfirmationDialogProps, "title" | "content" | "onOpenChange"> {
    sessionName: string;
    onCancel: () => void;
}

export const ChatSessionDeleteDialog = React.memo<ChatSessionDeleteDialogProps>(({ open, onCancel, onConfirm, sessionName }) => {
    return (
        <ConfirmationDialog
            open={open}
            onOpenChange={open => {
                if (!open) {
                    onCancel();
                }
            }}
            title="Delete Chat"
            content={
                <div>
                    This action cannot be undone. This chat session and any associated artifacts will be permanently deleted: <strong>{sessionName}</strong>
                </div>
            }
            onConfirm={onConfirm}
        />
    );
});
