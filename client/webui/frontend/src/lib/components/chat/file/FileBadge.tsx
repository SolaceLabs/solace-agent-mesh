import React from "react";

import { XIcon } from "lucide-react";

import { Badge, Button } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

interface FileBadgeProps {
    fileName: string;
    onRemove?: () => void;
    /** Optional click handler for the badge body. Rendered as a button when set. */
    onClick?: () => void;
    /** Optional leading icon rendered before the filename (e.g. Link2 for artifact references). */
    leadingIcon?: React.ReactNode;
    /** Optional tooltip override for the filename label. */
    title?: string;
}

export const FileBadge: React.FC<FileBadgeProps> = ({ fileName, onRemove, onClick, leadingIcon, title }) => {
    const labelContent = (
        <>
            {leadingIcon && <span className="flex flex-shrink-0 items-center [&_svg]:size-3.5">{leadingIcon}</span>}
            <span className="min-w-0 flex-1 truncate text-xs md:text-sm" title={title ?? fileName}>
                {fileName}
            </span>
        </>
    );

    return (
        <Badge className="max-w-50 gap-1.5 rounded-full bg-(--secondary-w10) pr-1">
            {onClick ? (
                <button
                    type="button"
                    onClick={onClick}
                    title={title ?? fileName}
                    className={cn("flex min-w-0 flex-1 items-center gap-1.5 rounded-full bg-transparent text-left hover:text-(--primary-wMain) focus-visible:ring-2 focus-visible:ring-(--primary-wMain) focus-visible:outline-none")}
                >
                    {labelContent}
                </button>
            ) : (
                labelContent
            )}
            {onRemove && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={event => {
                        event.stopPropagation();
                        onRemove();
                    }}
                    className={"h-2 min-h-0 w-2 min-w-0 p-2"}
                    title="Remove file"
                >
                    <XIcon />
                </Button>
            )}
        </Badge>
    );
};
