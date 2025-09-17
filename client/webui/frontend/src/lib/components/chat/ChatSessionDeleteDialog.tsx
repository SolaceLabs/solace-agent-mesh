import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Button } from "@/lib/components/ui/button";

interface ChatSessionDeleteDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    sessionName: string;
}

export const ChatSessionDeleteDialog = ({ isOpen, onClose, onConfirm, sessionName }: ChatSessionDeleteDialogProps) => {
    if (!isOpen) {
        return null;
    }

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Delete Chat Session?</DialogTitle>
                    <DialogDescription>
                        This action cannot be undone. This chat session and any associated artifacts will be permanently deleted: <strong>{sessionName}</strong>
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
};
