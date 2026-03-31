import React from "react";

import { FileText, Loader2 } from "lucide-react";

import { formatBytes } from "@/lib/utils/format";

interface InProgressFileMessageProps {
    name: string;
    bytesTransferred: number;
}

export const InProgressFileMessage: React.FC<InProgressFileMessageProps> = ({ name, bytesTransferred }) => {
    return (
        <div className="ml-4 flex h-11 max-w-xs items-center gap-2 rounded-lg bg-(--background-w20) px-2 py-1">
            <FileText className="h-4 w-4 flex-shrink-0" />
            <div className="min-w-0 flex-1 truncate">
                <div className="text-sm font-semibold" title={name}>
                    <code>{name}</code>
                </div>
                <div className="text-xs text-(--secondary-text-wMain)">Authoring artifact... {formatBytes(bytesTransferred)}</div>
            </div>
            <Loader2 className="h-4 w-4 animate-spin" />
        </div>
    );
};
