import React from "react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";

interface PromptRestoreDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    versionNumber: number;
}

export const PromptRestoreDialog = React.memo<PromptRestoreDialogProps>(({ isOpen, onClose, onConfirm, versionNumber }) => {
    if (!isOpen) {
        return null;
    }

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Restore Version {versionNumber}?</DialogTitle>
                    <DialogDescription>
                        This will set version <strong>{versionNumber}</strong> as the production version. The current production version will remain in history and can be restored later.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} title="Cancel">
                        Cancel
                    </Button>
                    <Button onClick={onConfirm} title="Restore">
                        Restore
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
});