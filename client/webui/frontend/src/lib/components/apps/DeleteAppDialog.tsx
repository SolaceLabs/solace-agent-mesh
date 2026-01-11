import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { Input } from "@/lib/components/ui/input";
import { Label } from "@/lib/components/ui/label";
import type { App } from "@/lib/types/app";

interface DeleteAppDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => Promise<void>;
    app: App | null;
    isDeleting?: boolean;
}

export const DeleteAppDialog = ({ isOpen, onClose, onConfirm, app, isDeleting = false }: DeleteAppDialogProps) => {
    const [confirmText, setConfirmText] = useState("");

    if (!app) {
        return null;
    }

    const isConfirmEnabled = confirmText === app.name;

    const handleClose = () => {
        setConfirmText("");
        onClose();
    };

    const handleConfirm = async () => {
        if (!isConfirmEnabled) return;
        await onConfirm();
        setConfirmText("");
    };

    const hasDeployedVersions = app.devVersion || app.stagingVersion || app.prodVersion;

    return (
        <Dialog open={isOpen} onOpenChange={open => !open && handleClose()}>
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-destructive">
                        <AlertTriangle className="size-5" />
                        Delete Widget Permanently
                    </DialogTitle>
                    <DialogDescription>
                        This action cannot be undone.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm">
                        <p className="font-medium">The following will be permanently deleted:</p>
                        <ul className="mt-2 list-inside list-disc space-y-1 text-muted-foreground">
                            <li>All source code and workspace files</li>
                            <li>All stored application data</li>
                            {hasDeployedVersions && (
                                <li>All deployed versions ({[
                                    app.devVersion && "dev",
                                    app.stagingVersion && "staging",
                                    app.prodVersion && "prod"
                                ].filter(Boolean).join(", ")})</li>
                            )}
                        </ul>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="confirm-name">
                            Type <strong>{app.name}</strong> to confirm:
                        </Label>
                        <Input
                            id="confirm-name"
                            value={confirmText}
                            onChange={e => setConfirmText(e.target.value)}
                            placeholder={app.name}
                            disabled={isDeleting}
                            autoComplete="off"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        variant="ghost"
                        onClick={handleClose}
                        disabled={isDeleting}
                    >
                        Cancel
                    </Button>
                    <Button
                        variant="destructive"
                        onClick={handleConfirm}
                        disabled={!isConfirmEnabled || isDeleting}
                    >
                        {isDeleting ? "Deleting..." : "Delete Widget"}
                    </Button>
                </DialogFooter>

                {isDeleting && (
                    <>
                        <style>{`
                        @keyframes progressBarSlide {
                            0% { transform: translateX(-100%); }
                            100% { transform: translateX(400%); }
                        }
                        .progress-bar-animate {
                            animation: progressBarSlide 2s ease-in-out infinite;
                            width: 25%;
                            background: var(--color-destructive);
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
