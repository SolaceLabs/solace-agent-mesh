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
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                    <DialogDescription>{subtitle}</DialogDescription>
                </DialogHeader>
                <div className="flex flex-col gap-4">
                    <div className="flex flex-row items-center gap-2">
                        <CircleX className="h-6 w-6 shrink-0 self-start text-(--color-error-wMain)" />
                        <div>{error}</div>
                    </div>
                    {errorDetails && <div>{errorDetails}</div>}
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
