import { AlertCircle } from "lucide-react";

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
            <Alert className="border-border bg-accent max-w-80 rounded-sm shadow-md">
                <AlertTitle className="flex items-center text-sm">
                    {type === "error" && <AlertCircle className="mr-2 text-[var(--color-error-wMain)]" />}
                    <div className="truncate">{message}</div>
                </AlertTitle>
            </Alert>
        </div>
    );
}
