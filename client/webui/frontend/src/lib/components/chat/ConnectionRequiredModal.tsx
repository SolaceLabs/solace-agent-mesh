/**
 * Connection Required Modal Component
 *
 * Shows when user tries to select an enterprise source that requires authentication
 * Provides option to navigate to connections panel to authenticate
 */

import React from "react";
import { AlertCircle, ExternalLink } from "lucide-react";
import { Button } from "@/lib/components/ui/button";

interface ConnectionRequiredModalProps {
    isOpen: boolean;
    onClose: () => void;
    sourceName: string;
    onNavigateToConnections: () => void;
}

export const ConnectionRequiredModal: React.FC<ConnectionRequiredModalProps> = ({ isOpen, onClose, sourceName, onNavigateToConnections }) => {
    if (!isOpen) return null;

    return (
        <>
            {/* Backdrop */}
            <div className="fixed inset-0 z-[100] bg-black/50" onClick={onClose} />

            {/* Modal */}
            <div className="fixed top-1/2 left-1/2 z-[101] w-full max-w-md -translate-x-1/2 -translate-y-1/2">
                <div className="space-y-4 rounded-lg border border-gray-300 bg-white p-6 shadow-xl dark:border-gray-700 dark:bg-gray-900">
                    {/* Header */}
                    <div className="flex items-start gap-3">
                        <div className="mt-0.5 flex-shrink-0">
                            <AlertCircle className="h-6 w-6 text-amber-500" />
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-semibold">Connection Required</h3>
                            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">You need to connect your {sourceName} account before using it in deep research.</p>
                        </div>
                    </div>

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

                    {/* Actions */}
                    <div className="flex justify-end gap-3">
                        <Button variant="outline" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button onClick={onNavigateToConnections} className="bg-blue-600 text-white hover:bg-blue-700">
                            <ExternalLink className="mr-2 h-4 w-4" />
                            Go to Connections
                        </Button>
                    </div>
                </div>
            </div>
        </>
    );
};
