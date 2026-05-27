import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { CircleX } from "lucide-react";

interface ErrorDialogProps {
    title: string;
    error: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;

    // optional subtitle below the title (typically unused)
    subtitle?: string;
    // optional detailed error message
    errorDetails?: string;
}

export const ErrorDialog: React.FC<ErrorDialogProps> = ({ title, subtitle, error, errorDetails, open, onOpenChange }) => {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="w-[95vw] max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex min-w-0 flex-row gap-1 break-words">{title}</DialogTitle>
                    <DialogDescription>{subtitle}</DialogDescription>
                </DialogHeader>
                <div className="flex flex-col gap-4">
                    <div className="flex flex-row items-center gap-2">
                        <CircleX className="h-6 w-6 shrink-0 self-start text-(--error-wMain)" />
                        <div className="min-w-0 break-words">{error}</div>
                    </div>
                    {errorDetails && <div className="min-w-0 break-words">{errorDetails}</div>}
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="outline" testid="closeButton" title="Close">
                            Close
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
