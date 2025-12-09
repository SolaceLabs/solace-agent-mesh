import { AlertTriangle, CheckCircle } from "lucide-react";

import { Alert, AlertTitle } from "../ui/alert";
import type { Notification } from "../../types";

export function Toast({ id, message, type }: Notification) {
    return (
        <div id={id} className="transform transition-all duration-200 ease-in-out">
            <Alert className="light:border-none dark:border-border max-w-80 min-w-58 rounded-sm bg-[var(--color-background-wMain)] px-4 py-0 text-white shadow-[0_4px_6px_-1px_rgba(0,0,0,0.15)] dark:shadow-[0_4px_6px_-1px_rgba(255,255,255,0.1)]">
                <AlertTitle className="flex h-10 items-center">
                    {type === "warning" && <AlertTriangle className="mr-2 text-[var(--color-warning-wMain)]" />}
                    {type === "success" && <CheckCircle className="mr-2 text-[var(--color-success-wMain)]" />}
                    <div className="truncate">{message}</div>
                </AlertTitle>
            </Alert>
        </div>
    );
}
