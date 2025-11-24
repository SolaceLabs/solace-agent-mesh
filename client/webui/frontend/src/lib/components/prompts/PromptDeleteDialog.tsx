import React, { useEffect } from "react";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";

interface PromptDeleteDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    promptName: string;
}

export const PromptDeleteDialog = React.memo<PromptDeleteDialogProps>(({ isOpen, onClose, onConfirm, promptName }) => {
    // Cleanup effect to restore pointer events when dialog closes
    useEffect(() => {
        let observer: MutationObserver | null = null;
        
        return () => {
            // Remove any Radix portal overlays that might be stuck
            const overlays = document.querySelectorAll('[data-radix-dialog-overlay]');
            overlays.forEach(overlay => overlay.remove());
            
            // Restore pointer events on body
            document.body.style.pointerEvents = '';
            
            // Watch for Radix trying to set pointer-events back to none
            observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'style') {
                        const bodyStyle = (mutation.target as HTMLElement).style;
                        if (bodyStyle.pointerEvents === 'none') {
                            bodyStyle.pointerEvents = '';
                        }
                    }
                });
            });
            
            observer.observe(document.body, {
                attributes: true,
                attributeFilter: ['style']
            });
            
            // Disconnect observer after a short delay
            setTimeout(() => {
                observer?.disconnect();
            }, 500);
        };
    }, []);

    const handleCancel = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        document.body.style.pointerEvents = '';
        onClose();
    };

    const handleConfirm = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        onConfirm();
    };

    const handleOpenChange = (open: boolean) => {
        if (!open) {
            document.body.style.pointerEvents = '';
            onClose();
        }
    };

    if (!isOpen) {
        return null;
    }

    return (
        <Dialog open={isOpen} onOpenChange={handleOpenChange} modal={true}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete Prompt?</DialogTitle>
                    <DialogDescription>
                        This action cannot be undone. This will permanently delete the prompt and all its versions: <strong>{promptName}</strong>
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="ghost" onClick={handleCancel} title="Cancel">
                        Cancel
                    </Button>
                    <Button variant="outline" onClick={handleConfirm} title="Delete">
                        Delete
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
});