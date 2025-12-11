/**
 * Connection Required Modal Component
 *
 * Shows when user tries to select an enterprise source that requires authentication
 * Provides option to navigate to connections panel to authenticate
 */

import React from "react";
import { AlertCircle, ExternalLink } from "lucide-react";
import { Button } from "@/lib/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/lib/components/ui/dialog";

interface ConnectionRequiredModalProps {
    isOpen: boolean;
    onClose: () => void;
    sourceName: string;
    onNavigateToConnections: () => void;
}

export const ConnectionRequiredModal: React.FC<ConnectionRequiredModalProps> = ({ isOpen, onClose, sourceName, onNavigateToConnections }) => {
    return (
        <Dialog open={isOpen} onOpenChange={open => !open && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <AlertCircle className="h-5 w-5 text-amber-500" />
                        Connection Required
                    </DialogTitle>
                    <DialogDescription>You need to connect your {sourceName} account before using it in deep research.</DialogDescription>
                </DialogHeader>

                {/* Content */}
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-900/20">
                    <p className="text-sm text-blue-900 dark:text-blue-100">
                        <strong>How to connect:</strong>
                    </p>
                    <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-blue-800 dark:text-blue-200">
                        <li>Go to the Connections panel</li>
                        <li>Click "Connect" next to {sourceName}</li>
                        <li>Authenticate with your account</li>
                        <li>Return here to enable the source</li>
                    </ol>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button onClick={onNavigateToConnections}>
                        <ExternalLink className="mr-2 h-4 w-4" />
                        Go to Connections
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
