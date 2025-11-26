import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/lib/components/ui/dialog";

export interface ConfirmationDialogProps {
    open: boolean;
    title: string;
    content?: React.ReactNode;
    description?: string;
    actionLabels?: {
        cancel?: string;
        confirm?: string;
    };
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;
    onCancel?: () => void;

    // optional trigger to open the dialog eg. button
    trigger?: React.ReactNode;
}

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({ open, title, content, description, actionLabels, trigger, onOpenChange, onConfirm, onCancel }) => {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>
                {content}
                <DialogFooter>
                    <DialogClose asChild>
                        <Button
                            variant="ghost"
                            title="Cancel"
                            onClick={e => {
                                e.stopPropagation();
                                onCancel?.();
                            }}
                        >
                            {actionLabels?.cancel ?? "Cancel"}
                        </Button>
                    </DialogClose>
                    <DialogClose asChild>
                        <Button
                            title="Confirm"
                            onClick={e => {
                                e.stopPropagation();
                                onConfirm();
                            }}
                        >
                            {actionLabels?.confirm ?? "Confirm"}
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
