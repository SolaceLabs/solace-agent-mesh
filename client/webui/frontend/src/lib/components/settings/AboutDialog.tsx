import React from "react";

import { Dialog, DialogContent, DialogDescription, DialogTitle, VisuallyHidden } from "@/lib/components/ui";
import { AboutProduct } from "@/lib/components/settings/AboutProduct";

interface AboutDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export const AboutDialog: React.FC<AboutDialogProps> = ({ open, onOpenChange }) => {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-h-[90vh] w-[90vw] !max-w-[600px] gap-0 p-0" showCloseButton={true}>
                <VisuallyHidden>
                    <DialogTitle>About</DialogTitle>
                    <DialogDescription>About Solace Agent Mesh</DialogDescription>
                </VisuallyHidden>
                <div className="flex flex-col overflow-hidden">
                    {/* Header */}
                    <div className="flex items-center border-b px-6 py-4">
                        <h3 className="text-xl font-semibold">About</h3>
                    </div>

                    {/* Content Area */}
                    <div className="max-h-[70vh] overflow-y-auto p-6">
                        <div className="mx-auto max-w-2xl">
                            <AboutProduct />
                        </div>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    );
};
