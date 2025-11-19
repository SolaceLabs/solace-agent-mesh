import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/lib/components/ui/dialog";
import { DialogClose } from "@radix-ui/react-dialog";

/* The following variable definitions are mutually exclusive and follow this precedence
 * open, openChange > trigger > triggerText
 *
 * Lower precedence config values will be ignored
 * */
export interface ConfirmationDialogProps {
    title: string;
    message: string | React.ReactNode;
    triggerText?: string;
    trigger?: React.ReactNode;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    onConfirm: () => void;
    onClose: () => void;
}

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({ title, message, triggerText, trigger, onClose, onConfirm, open, onOpenChange }) => {
    const hasTrigger = trigger || triggerText;
    const isExternallyControlled = open && onOpenChange;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {hasTrigger && !isExternallyControlled && <DialogTrigger asChild>{trigger ?? <Button>{triggerText}</Button>}</DialogTrigger>}
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                    <DialogDescription>{message}</DialogDescription>
                </DialogHeader>

                <DialogFooter>
                    <DialogClose asChild>
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
                    </DialogClose>

                    <DialogClose asChild>
                        <Button
                            title="Confirm"
                            onClick={event => {
                                event.stopPropagation();
                                onConfirm();
                            }}
                        >
                            Confirm
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
