import React, { useEffect, useCallback, useState } from 'react';
import { ConfirmationDialog } from '@/lib/components/ui';

interface UseUnsavedChangesWarningProps {
    hasUnsavedChanges: boolean;
    onNavigate?: () => void;
}

interface UseUnsavedChangesWarningReturn {
    ConfirmNavigationDialog: () => React.JSX.Element | null;
    confirmNavigation: () => void;
}

export function useUnsavedChangesWarning({ 
    hasUnsavedChanges,
}: UseUnsavedChangesWarningProps): UseUnsavedChangesWarningReturn {
    const [showDialog, setShowDialog] = useState(false);
    const [pendingNavigation, setPendingNavigation] = useState<(() => void) | null>(null);

    // Handle browser beforeunload event
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = ''; // Chrome requires returnValue to be set
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [hasUnsavedChanges]);

    const confirmNavigation = useCallback(() => {
        if (pendingNavigation) {
            pendingNavigation();
            setPendingNavigation(null);
        }
        setShowDialog(false);
    }, [pendingNavigation]);

    const cancelNavigation = useCallback(() => {
        setPendingNavigation(null);
        setShowDialog(false);
    }, []);

    const ConfirmNavigationDialog = useCallback(() => {
        return showDialog ? (
            <ConfirmationDialog
                title="Unsaved Changes Will Be Discarded"
                message="Leaving the form will discard any unsaved changes. Are you sure you want to leave?"
                onClose={cancelNavigation}
                onConfirm={confirmNavigation}
                confirmVariant="outline"
            />
        ) : null;
    }, [showDialog, cancelNavigation, confirmNavigation]);

    return {
        ConfirmNavigationDialog,
        confirmNavigation,
    };
}