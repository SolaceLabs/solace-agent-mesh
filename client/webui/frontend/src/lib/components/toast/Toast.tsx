import { AlertCircle, CheckCircle } from "lucide-react";

import { Alert, AlertTitle } from "../ui/alert";

export interface ToastProps {
    id: string;
    message: string;
    type?: "info" | "success" | "warning" | "error";
    duration?: number;
}

export function Toast({ message, type }: ToastProps) {
    return (
        <div className="transform transition-all duration-200 ease-in-out">
            <Alert className="border-border max-w-80 rounded-sm bg-[var(--color-background-wMain)] text-[var(--color-primary-text-w10)] shadow-md">
                <AlertTitle className="flex items-center text-sm">
                    {type === "error" && <AlertCircle className="mr-2 text-[var(--color-error-wMain)]" />}
                    {type === "success" && <CheckCircle className="mr-2 text-[var(--color-success-wMain)]" />}
                    <div className="truncate">{message}</div>
                </AlertTitle>
            </Alert>
        </div>
    );
}
