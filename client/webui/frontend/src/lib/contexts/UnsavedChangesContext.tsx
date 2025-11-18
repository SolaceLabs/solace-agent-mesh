import React, { createContext, useContext, useState, useCallback } from 'react';
import { ConfirmationDialog } from '@/lib/components/ui';

interface UnsavedChangesContextType {
    hasUnsavedChanges: boolean;
    setHasUnsavedChanges: (value: boolean) => void;
    checkUnsavedChanges: (onConfirm: () => void) => void;
}

const UnsavedChangesContext = createContext<UnsavedChangesContextType | undefined>(undefined);

export const UnsavedChangesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
    const [showDialog, setShowDialog] = useState(false);
    const [pendingNavigation, setPendingNavigation] = useState<(() => void) | null>(null);

    const checkUnsavedChanges = useCallback((onConfirm: () => void) => {
        if (hasUnsavedChanges) {
            setPendingNavigation(() => onConfirm);
            setShowDialog(true);
        } else {
            onConfirm();
        }
    }, [hasUnsavedChanges]);

    const handleConfirm = useCallback(() => {
        setShowDialog(false);
        if (pendingNavigation) {
            pendingNavigation();
            setPendingNavigation(null);
        }
    }, [pendingNavigation]);

    const handleCancel = useCallback(() => {
        setShowDialog(false);
        setPendingNavigation(null);
    }, []);

    return (
        <UnsavedChangesContext.Provider value={{ hasUnsavedChanges, setHasUnsavedChanges, checkUnsavedChanges }}>
            {children}
            {showDialog && (
                <ConfirmationDialog
                    title="Unsaved Changes Will Be Discarded"
                    message="Leaving the form will discard any unsaved changes. Are you sure you want to leave?"
                    onClose={handleCancel}
                    onConfirm={handleConfirm}
                />
            )}
        </UnsavedChangesContext.Provider>
    );
};

export const useUnsavedChangesContext = () => {
    const context = useContext(UnsavedChangesContext);
    if (!context) {
        throw new Error('useUnsavedChangesContext must be used within UnsavedChangesProvider');
    }
    return context;
};