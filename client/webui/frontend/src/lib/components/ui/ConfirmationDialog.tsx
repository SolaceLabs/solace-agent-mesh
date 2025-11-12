import { Button, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/lib/components/ui";

interface ConfirmationDialogProps {
    title: string;
    message: string | React.ReactNode;
    onConfirm: () => void;
    onClose: () => void;
    confirmVariant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link";
}

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({ 
    title, 
    message, 
    onClose, 
    onConfirm, 
    confirmVariant = "default" 
}) => {
    return (
        <Dialog open={true} onOpenChange={() => onClose()}>
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                    <DialogDescription>{message}</DialogDescription>
                </DialogHeader>

                <div className="flex justify-end gap-2">
                    <Button
                        variant="ghost"
                        title="Cancel"
                        onClick={event => {
                            event.stopPropagation();
                            onClose();
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        title="Confirm"
                        variant={confirmVariant}
                        onClick={event => {
                            event.stopPropagation();
                            onConfirm();
                        }}
                    >
                        Confirm
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};