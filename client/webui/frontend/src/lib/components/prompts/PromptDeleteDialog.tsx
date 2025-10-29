import React from "react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";

interface PromptDeleteDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    promptName: string;
}

export const PromptDeleteDialog = React.memo<PromptDeleteDialogProps>(({ isOpen, onClose, onConfirm, promptName }) => {
    if (!isOpen) {
        return null;
    }

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete Prompt?</DialogTitle>
                    <DialogDescription>
                        This action cannot be undone. This will permanently delete the prompt and all its versions: <strong>{promptName}</strong>
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} title="Cancel">
                        Cancel
                    </Button>
                    <Button onClick={onConfirm} title="Delete">
                        Delete
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
});