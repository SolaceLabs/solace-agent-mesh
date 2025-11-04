import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { CircleX } from "lucide-react";

interface ErrorDialogProps {
    title: string;
    error: string;
    errorDetails?: string;
    onClose: () => void;
}

export const ErrorDialog: React.FC<ErrorDialogProps> = ({ title, error, errorDetails, onClose }) => {
    return (
        <Dialog open={true} onOpenChange={onClose}>
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex max-w-[400px] flex-row gap-1">{title}</DialogTitle>
                </DialogHeader>

                <div className="flex flex-row items-center gap-2">
                    <CircleX className="h-6 w-6 flex-shrink-0 self-start text-[var(--color-error-wMain)]" />
                    <div>{error}</div>
                </div>
                {errorDetails && <div className="text-[var(--color-secondary-text-wMain)]">{errorDetails}</div>}

                <div className="flex justify-end">
                    <Button variant="outline" testid="closeButton" type="button" title="Close" onClick={onClose}>
                        Close
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
};
