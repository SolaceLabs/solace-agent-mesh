import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/lib/components/ui/dialog";

export interface ConfirmationDialogProps {
    open: boolean;
    title: string;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;

    // optional cancel handler if additional functionality is needed when a user clicks cancel
    onCancel?: () => void;

    // optional content and description - provide at least one
    content?: React.ReactNode;
    description?: string;

    // optional loading and enabled state for confirm action
    isLoading?: boolean;
    isEnabled?: boolean;

    // optional custom action labels
    actionLabels?: {
        cancel?: string;
        confirm?: string;
    };

    // optional trigger to open the dialog eg. button
    trigger?: React.ReactNode;
}

export const ConfirmationDialog: React.FC<ConfirmationDialogProps> = ({ open, title, content, description, actionLabels, trigger, isLoading, isEnabled = true, onOpenChange, onConfirm, onCancel }) => {
    const cancelTitle = actionLabels?.cancel ?? "Cancel";
    const confirmTitle = actionLabels?.confirm ?? "Confirm";

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                    <DialogDescription>{description}</DialogDescription>
                </DialogHeader>
                <div className="min-w-0 break-words">{content}</div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button
                            variant="ghost"
                            title={cancelTitle}
                            onClick={e => {
                                e.stopPropagation();
                                onCancel?.();
                            }}
                            disabled={isLoading}
                        >
                            {cancelTitle}
                        </Button>
                    </DialogClose>
                    <Button
                        data-testid="dialogConfirmButton"
                        variant="outline"
                        title={confirmTitle}
                        onClick={async e => {
                            e.stopPropagation();
                            await onConfirm();
                            onOpenChange(false);
                        }}
                        disabled={isLoading || !isEnabled}
                    >
                        {confirmTitle}
                    </Button>
                </DialogFooter>
                {isLoading && (
                    <>
                        <style>{`
                        @keyframes progressBarSlide {
                            0% { transform: translateX(-100%); }
                            100% { transform: translateX(400%); }
                        }
                        .progress-bar-animate {
                            animation: progressBarSlide 2s ease-in-out infinite;
                            width: 25%;
                            background: var(--color-brand-wMain);
                        }
                        `}</style>
                        <div className="bg-muted absolute right-1 bottom-0 left-1 h-1 overflow-hidden rounded-full">
                            <div className="progress-bar-animate h-full rounded-full"></div>
                        </div>
                    </>
                )}
            </DialogContent>
        </Dialog>
    );
};
