import React from "react";

import { FileText, XIcon } from "lucide-react";

import { Badge, Button, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";

interface PastedTextBadgeProps {
    id: string;
    index: number;
    textPreview: string;
    onClick: () => void;
    onRemove?: () => void;
}

/**
 * Badge for displaying already-saved pasted artifacts (used after artifact is created)
 */
export const PastedTextBadge: React.FC<PastedTextBadgeProps> = ({ index, textPreview, onClick, onRemove }) => {
    return (
        <Badge className="bg-muted hover:bg-muted/80 max-w-fit cursor-pointer gap-1.5 rounded-full pr-1 transition-colors" onClick={onClick} title={`Click to view full content: ${textPreview}`}>
            <FileText className="size-3 shrink-0" />
            <span className="min-w-0 flex-1 text-xs font-medium whitespace-nowrap md:text-sm">Pasted Text #{index}</span>
            {onRemove && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={e => {
                        e.stopPropagation(); // Prevent triggering onClick when removing
                        onRemove();
                    }}
                    className="h-2 min-h-0 w-2 min-w-0 shrink-0 p-2"
                    title="Remove pasted text"
                >
                    <XIcon />
                </Button>
            )}
        </Badge>
    );
};

export interface PendingPastedTextBadgeProps {
    id: string;
    content: string;
    onClick: () => void;
    onRemove: () => void;
    isConfigured?: boolean; // true if user has configured via dialog
    filename?: string; // configured filename to display
    defaultFilename?: string; // default filename that will be used if not configured
}

/**
 * Badge for displaying pending pasted text (not yet uploaded as artifact)
 * Shows a card-like preview with text preview and status label
 * When configured, shows the filename and a checkmark
 */
export const PendingPastedTextBadge: React.FC<PendingPastedTextBadgeProps> = ({ content, onClick, onRemove, isConfigured, filename, defaultFilename }) => {
    // Get first few lines for preview (max 2 lines, max 40 chars per line)
    const getPreviewLines = (text: string): string[] => {
        const lines = text.split("\n").slice(0, 2);
        return lines.map(line => {
            const trimmed = line.trim();
            return trimmed.length > 40 ? trimmed.substring(0, 37) + "..." : trimmed;
        });
    };

    const previewLines = getPreviewLines(content);

    const tooltipText = isConfigured ? `Click to edit: ${filename}` : "Click to customize file settings";

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <div
                    className={`bg-background relative inline-flex max-w-[200px] cursor-pointer flex-col rounded-lg border shadow-sm transition-colors ${
                        isConfigured ? "border-[var(--color-info-wMain)]/50 hover:border-[var(--color-info-wMain)]" : "border-border hover:border-primary/50"
                    }`}
                    onClick={onClick}
                >
                    {/* Close button */}
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={e => {
                            e.stopPropagation();
                            onRemove();
                        }}
                        className="bg-background border-border hover:bg-muted absolute -top-2 -left-2 h-5 w-5 rounded-full border p-0 shadow-sm"
                        tooltip="Remove pasted text"
                        tooltipSide="left"
                    >
                        <XIcon className="h-3 w-3" />
                    </Button>

                    {/* Text preview */}
                    <div className="text-muted-foreground overflow-hidden px-3 pt-3 pb-2 font-mono text-xs leading-relaxed">
                        {previewLines.map((line, index) => (
                            <div key={index} className="truncate">
                                {line || "\u00A0"}
                            </div>
                        ))}
                        {content.split("\n").length > 2 && <div className="text-muted-foreground/60">...</div>}
                    </div>

                    {/* Status label - show filename (configured or default) */}
                    <div className="flex items-center gap-1 px-2 pb-2">
                        {isConfigured ? (
                            <span className="inline-flex max-w-[170px] items-center gap-1.5 truncate rounded bg-[var(--color-info-w10)] px-2 py-0.5 text-[10px] font-semibold tracking-wider text-[var(--color-info-wMain)] dark:bg-[var(--color-info-wMain)] dark:text-[var(--color-primary-text-w10)]">
                                {filename || "CONFIGURED"}
                                <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[var(--color-info-wMain)] dark:bg-[var(--color-primary-text-w10)]" />
                            </span>
                        ) : (
                            <span className="bg-muted text-muted-foreground inline-block max-w-[170px] truncate rounded px-2 py-0.5 text-[10px] font-semibold tracking-wider">{defaultFilename || "snippet.txt"}</span>
                        )}
                    </div>
                </div>
            </TooltipTrigger>
            <TooltipContent side="top">
                <p>{tooltipText}</p>
            </TooltipContent>
        </Tooltip>
    );
};
