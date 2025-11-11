import React, { useState, useEffect, useCallback, type JSX } from "react";
import { useBlocker } from "react-router-dom";
import { ConfirmationDialog } from "@/lib/components/ui";

// Confirmation dialog component used as blocker
interface NavigationConfirmationDialogProps {
    isOpen: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

const NavigationConfirmationDialog: React.FC<NavigationConfirmationDialogProps> = ({ isOpen, onConfirm, onCancel }) => {
    return isOpen ? (
        <ConfirmationDialog
            title="Unsaved Changes Will Be Discarded"
            message="Leaving the form will discard any unsaved changes. Are you sure you want to leave?"
            onClose={onCancel}
            onConfirm={onConfirm}
        />
    ) : null;
};

interface UseNavigationBlockerReturn {
    NavigationBlocker: () => JSX.Element | null;
    allowNavigation: (navigationFn: () => void) => void;
    setBlockingEnabled: (enabled: boolean) => void;
}

export function useNavigationBlocker(): UseNavigationBlockerReturn {
    const [showConfirmationDialog, setShowConfirmationDialog] = useState(false);
    const [isNavigationAllowed, setIsNavigationAllowed] = useState(false);
    const [blockingEnabled, setBlockingEnabled] = useState(false);

    const blocker = useBlocker(({ currentLocation, nextLocation }) =>
        blockingEnabled && !isNavigationAllowed && currentLocation.pathname !== nextLocation.pathname
    );

    useEffect(() => {
        if (blocker.state === "blocked") {
            setShowConfirmationDialog(true);
        }
    }, [blocker]);

    const confirmNavigation = useCallback(() => {
        setShowConfirmationDialog(false);
        if (blocker.state === "blocked") {
            blocker.proceed();
        }
    }, [blocker]);

    const cancelNavigation = useCallback(() => {
        setShowConfirmationDialog(false);
        if (blocker.state === "blocked") {
            blocker.reset();
        }
    }, [blocker]);

    const allowNavigation = useCallback((navigationFn: () => void) => {
        setIsNavigationAllowed(true);
        setTimeout(() => {
            navigationFn();
        }, 0);
    }, []);

    const NavigationBlocker = useCallback(() => {
        return <NavigationConfirmationDialog isOpen={showConfirmationDialog} onConfirm={confirmNavigation} onCancel={cancelNavigation} />;
    }, [showConfirmationDialog, confirmNavigation, cancelNavigation]);

    return {
        NavigationBlocker,
        allowNavigation,
        setBlockingEnabled,
    };
}