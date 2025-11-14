import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/lib/components/ui/dialog";
import { DialogClose } from "@radix-ui/react-dialog";

interface BaseDialogProps {
    title: string;
    message: string | React.ReactNode;
    onConfirm: () => void;
    onClose: () => void;
}

type ConfirmationDialogProps =
    | (BaseDialogProps & {
          triggerText: string;
          trigger?: never;
          open?: never;
          onOpenChange?: never;
      })
    | (BaseDialogProps & {
          trigger: React.ReactNode;
          triggerText?: never;
          open?: never;
          onOpenChange?: never;
      })
    | (BaseDialogProps & {
          trigger?: never;
          triggerText?: never;
          open: boolean;
          onOpenChange: (open: boolean) => void;
      });

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({ title, message, triggerText, trigger, onClose, onConfirm, open, onOpenChange }) => {
    const hasTrigger = trigger || triggerText;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {hasTrigger && <DialogTrigger asChild>{trigger ?? <Button>{triggerText}</Button>}</DialogTrigger>}
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
