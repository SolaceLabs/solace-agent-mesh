import { AlertTriangle, CheckCircle } from "lucide-react";

import { Alert, AlertTitle } from "../ui/alert";
import type { Notification } from "../../types";

export function Toast({ id, message, type }: Notification) {
    return (
        <div id={id} className="transform transition-all duration-200 ease-in-out">
            <Alert className="light:border-none max-w-80 min-w-58 rounded-sm bg-(--background-wMain) px-4 py-0 text-white shadow-[0_4px_6px_-1px_rgba(0,0,0,0.15)]">
                <AlertTitle className="flex h-10 items-center">
                    {type === "warning" && <AlertTriangle className="mr-2 text-(--warning-wMain)" />}
                    {type === "success" && <CheckCircle className="mr-2 text-(--success-wMain)" />}
                    <div className="truncate">{message}</div>
                </AlertTitle>
            </Alert>
        </div>
    );
}
