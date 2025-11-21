import React from "react";
import { ConfirmationDialog } from "@/lib/components/common/ConfirmationDialog";

interface ChatSessionDeleteDialogProps {
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
    sessionName: string;
}

export const ChatSessionDeleteDialog = React.memo<ChatSessionDeleteDialogProps>(({ open, onClose, onConfirm, sessionName }) => {
    return (
        <ConfirmationDialog
            open={open}
            onOpenChange={open => !open && onClose()}
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
