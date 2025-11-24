import { useState, useCallback, type JSX } from "react";
import { ErrorDialog } from "../components/common/ErrorDialog";

interface ErrorInfo {
    message: string;
    validationDetails?: Record<string, string[]>;
}

type ErrorInput = string | ErrorInfo | Error | unknown;

export const getErrorMessage = (error: ErrorInput): string => {
    try {
        // Handle simple string errors
        if (typeof error === "string") {
            return error;
        }

        // Handle null/undefined
        if (!error) {
            return "An error occurred.";
        }

        // Handle JavaScript Error objects
        if (error instanceof Error) {
            return error.message || "An error occurred.";
        }

        // Handle ErrorInfo objects with optional validation details
        if (typeof error === "object" && "message" in error) {
            const errorObj = error as ErrorInfo;
            const message = errorObj.message ?? "An error occurred.";

            // Check if validationDetails exists and has properties
            if (errorObj.validationDetails && typeof errorObj.validationDetails === "object") {
                const validationErrors: string[] = [];

                for (const key in errorObj.validationDetails) {
                    const errors = errorObj.validationDetails[key];
                    if (Array.isArray(errors)) {
                        validationErrors.push(...errors);
                    }
                }

                // Append validation errors to the main message
                if (validationErrors.length > 0) {
                    return `${message}\n\n${validationErrors.join("\n")}`;
                }
            }

            return message;
        }

        // Fallback: try to stringify the error
        return String(error);
    } catch {
        return "An error occurred.";
    }
};

interface UseErrorDialogReturn {
    ErrorDialog: () => JSX.Element;
    setError: (errorInfo: { title: string; error: ErrorInput } | null) => void;
}

export function useErrorDialog(): UseErrorDialogReturn {
    const [error, setError] = useState<{ title: string; error: ErrorInput } | null>(null);
    const handleOpenChange = useCallback((open: boolean) => {
        if (!open) {
            setError(null);
        }
    }, []);

    const ErrorDialogComponent = useCallback(() => {
        return <ErrorDialog title={error?.title || "Error"} error={error ? getErrorMessage(error.error) : ""} open={error !== null} onOpenChange={handleOpenChange} />;
    }, [error, handleOpenChange]);

    return {
        ErrorDialog: ErrorDialogComponent,
        setError,
    };
}
