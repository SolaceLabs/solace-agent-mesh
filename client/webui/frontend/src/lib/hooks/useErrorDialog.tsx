import { useState, useCallback, type JSX } from "react";
import { ErrorDialog } from "../components/common/ErrorDialog";

interface UseErrorDialogReturn {
    ErrorDialog: () => JSX.Element;
    setError: (errorInfo: { title: string; error: string } | null) => void;
}

export function useErrorDialog(): UseErrorDialogReturn {
    const [error, setError] = useState<{ title: string; error: string } | null>(null);

    const handleOpenChange = useCallback((open: boolean) => {
        if (!open) {
            setError(null);
        }
    }, []);

    const ErrorDialogComponent = useCallback(() => {
        return <ErrorDialog title={error?.title || "Error"} error={error?.error || "An error occurred."} open={error !== null} onOpenChange={handleOpenChange} />;
    }, [error, handleOpenChange]);

    return {
        ErrorDialog: ErrorDialogComponent,
        setError,
    };
}
