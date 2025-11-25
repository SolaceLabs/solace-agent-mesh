import { useState, useEffect, useCallback, type JSX } from "react";
import { useBlocker } from "react-router-dom";
import { ConfirmationDialog } from "../components/common/ConfirmationDialog";

interface UseNavigationBlockerReturn {
    NavigationBlocker: () => JSX.Element | null;
    allowNavigation: (navigationFn: () => void) => void;
    setBlockingEnabled: (enabled: boolean) => void;
}

export function useNavigationBlocker(): UseNavigationBlockerReturn {
    const [showConfirmationDialog, setShowConfirmationDialog] = useState(false);
    const [isNavigationAllowed, setIsNavigationAllowed] = useState(false);
    const [blockingEnabled, setBlockingEnabled] = useState(false);

    const blocker = useBlocker(({ currentLocation, nextLocation }) => blockingEnabled && !isNavigationAllowed && currentLocation.pathname !== nextLocation.pathname);

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
        return (
            <ConfirmationDialog
                title="Unsaved Changes Will Be Discarded"
                description="Leaving the form will discard any unsaved changes. Are you sure you want to leave?"
                open={showConfirmationDialog}
                onConfirm={confirmNavigation}
                onCancel={cancelNavigation}
                onOpenChange={setShowConfirmationDialog}
            />
        );
    }, [showConfirmationDialog, confirmNavigation, cancelNavigation]);

    return {
        NavigationBlocker,
        allowNavigation,
        setBlockingEnabled,
    };
}
