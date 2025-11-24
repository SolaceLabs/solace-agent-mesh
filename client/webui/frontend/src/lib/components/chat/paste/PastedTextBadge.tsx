import React from "react";

import { FileText, XIcon } from "lucide-react";

import { Badge, Button } from "@/lib/components/ui";

interface PastedTextBadgeProps {
    id: string;
    index: number;
    textPreview: string;
    onClick: () => void;
    onRemove?: () => void;
}

export const PastedTextBadge: React.FC<PastedTextBadgeProps> = ({ index, textPreview, onClick, onRemove }) => {
    return (
        <Badge
            className="bg-muted max-w-fit gap-1.5 rounded-full pr-1 cursor-pointer hover:bg-muted/80 transition-colors"
            onClick={onClick}
            title={`Click to view full content: ${textPreview}`}
        >
            <FileText className="size-3 shrink-0" />
            <span className="min-w-0 flex-1 whitespace-nowrap text-xs md:text-sm font-medium">
                Pasted Text #{index}
            </span>
            {onRemove && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                        e.stopPropagation(); // Prevent triggering onClick when removing
                        onRemove();
                    }}
                    className="h-2 min-h-0 w-2 min-w-0 p-2 shrink-0"
                    title="Remove pasted text"
                >
                    <XIcon />
                </Button>
            )}
        </Badge>
    );
};