import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/lib/components/ui/dialog";

export interface ConfirmationDialogProps {
    title: string;
    content: string | React.ReactNode;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void;

    // optional cancel for additional actions on cancel beyond closing the dialog
    onCancel?: () => void;
    // optional subtitle below the title (note: typically unused)
    subtitle?: string;
    // optional trigger to open the dialog eg. button
    trigger?: React.ReactNode;
}

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({ title, content, subtitle, trigger, onConfirm, onCancel, open, onOpenChange }) => {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                    <DialogDescription>{subtitle}</DialogDescription>
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
