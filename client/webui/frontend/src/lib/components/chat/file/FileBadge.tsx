import React from "react";

import { XIcon } from "lucide-react";

import { Badge, Button } from "@/lib/components/ui";

interface FileBadgeProps {
    fileName: string;
    onRemove?: () => void;
}

export const FileBadge: React.FC<FileBadgeProps> = ({ fileName, onRemove }) => {
    return (
        <Badge className="bg-muted max-w-50 gap-1.5 rounded-full pr-1">
            <span className="min-w-0 flex-1 truncate text-xs md:text-sm" title={fileName}>
                {fileName}
            </span>
            {onRemove && (
                <Button variant="ghost" size="icon" onClick={onRemove} className={"h-2 min-h-0 w-2 min-w-0 p-2"} title="Remove file">
                    <XIcon />
                </Button>
            )}
        </Badge>
    );
};
