import { AlertCircle, AlertTriangle, CheckCircle } from "lucide-react";

import { Alert, AlertTitle } from "../ui/alert";

export interface ToastProps {
    id: string;
    message: string;
    type?: "info" | "success" | "warning" | "error"; // error is deprecated, use a dialog instead
    duration?: number;
}

export function Toast({ message, type }: ToastProps) {
    return (
        <div className="transform transition-all duration-200 ease-in-out">
            <Alert className="light:border-none dark:border-border max-w-80 rounded-sm bg-[var(--color-background-wMain)] px-4 py-0 text-white shadow-[0_4px_6px_-1px_rgba(0,0,0,0.15)] dark:shadow-[0_4px_6px_-1px_rgba(255,255,255,0.1)]">
                <AlertTitle className="flex h-10 items-center">
                    {type === "error" && <AlertCircle className="mr-2 text-[var(--color-error-wMain)]" />}
                    {type === "warning" && <AlertTriangle className="mr-2 text-[var(--color-warning-wMain)]" />}
                    {type === "success" && <CheckCircle className="mr-2 text-[var(--color-success-wMain)]" />}
                    <div className="truncate">{message}</div>
                </AlertTitle>
            </Alert>
        </div>
    );
}
