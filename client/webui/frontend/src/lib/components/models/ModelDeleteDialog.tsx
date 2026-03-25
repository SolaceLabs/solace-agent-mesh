import React, { useState } from "react";

import { Button, Input } from "@/lib/components/ui";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";
import { DEFAULT_MODEL_ALIASES } from "./common";

interface ModelDeleteDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
    modelAlias: string;
    isLoading?: boolean;
}

export const ModelDeleteDialog = React.memo<ModelDeleteDialogProps>(({ open, onOpenChange, onConfirm, modelAlias, isLoading }) => {
    const isDefaultModel = DEFAULT_MODEL_ALIASES.includes(modelAlias.toLowerCase());

    if (isDefaultModel) {
        return <DefaultModelDialog open={open} onOpenChange={onOpenChange} modelAlias={modelAlias} />;
    }

    return <ConfirmDeleteDialog open={open} onOpenChange={onOpenChange} onConfirm={onConfirm} modelAlias={modelAlias} isLoading={isLoading} />;
});

/** Version 1: Default model cannot be deleted */
const DefaultModelDialog: React.FC<{
    open: boolean;
    onOpenChange: (open: boolean) => void;
    modelAlias: string;
}> = ({ open, onOpenChange, modelAlias }) => {
    const displayName = modelAlias.charAt(0).toUpperCase() + modelAlias.slice(1);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>Cannot Delete Model</DialogTitle>
                    <DialogDescription />
                </DialogHeader>
                <div className="flex flex-col gap-3">
                    <p>The {displayName} model cannot be deleted as it is required for AI features in the platform.</p>
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant="outline" title="Close">
                            Close
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

/** Version 2: Confirm deletion with DELETE input */
const ConfirmDeleteDialog: React.FC<{
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
    modelAlias?: string;
    isLoading?: boolean;
}> = ({ open, onOpenChange, onConfirm, isLoading }) => {
    const [confirmText, setConfirmText] = useState("");
    const isConfirmEnabled = confirmText === "DELETE";

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            setConfirmText("");
        }
        onOpenChange(nextOpen);
    };

    const handleConfirm = async () => {
        await onConfirm();
        setConfirmText("");
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="w-xl max-w-xl sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>Delete Model</DialogTitle>
                    <DialogDescription />
                </DialogHeader>
                <div className="flex flex-col gap-4">
                    <p>If any code-based agents are referencing this agent, they will no longer function correctly. This action cannot be undone.</p>
                    <div className="flex flex-col gap-2">
                        <label className="text-sm font-medium">
                            Type <strong>DELETE</strong> to confirm
                        </label>
                        <Input value={confirmText} onChange={e => setConfirmText(e.target.value)} disabled={isLoading} autoComplete="off" />
                    </div>
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button
                            variant="ghost"
                            title="Cancel"
                            onClick={e => {
                                e.stopPropagation();
                            }}
                            disabled={isLoading}
                        >
                            Cancel
                        </Button>
                    </DialogClose>
                    <Button
                        variant="ghost"
                        title="Delete"
                        onClick={async e => {
                            e.stopPropagation();
                            await handleConfirm();
                        }}
                        disabled={!isConfirmEnabled || isLoading}
                    >
                        Delete
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
                            background: var(--brand-wMain);
                        }
                        `}</style>
                        <div className="absolute right-1 bottom-0 left-1 h-1 overflow-hidden rounded-full bg-(--secondary-w10)">
                            <div className="progress-bar-animate h-full rounded-full"></div>
                        </div>
                    </>
                )}
            </DialogContent>
        </Dialog>
    );
};
