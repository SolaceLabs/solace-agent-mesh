import React from "react";
import { XIcon } from "lucide-react";

import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { cn } from "@/lib/utils";

interface AttachmentCardShellProps {
    /** Full filename shown in the bottom pill and the tooltip. */
    filename: string;
    /** Preview rendered in the fixed 80px-high box (used when `inlineText` is absent). */
    preview: React.ReactNode;
    /** If provided, renders inline (variable-height) text instead of the fixed preview box. */
    inlineText?: React.ReactNode;
    /** Tooltip text shown on hover. Defaults to `filename`. */
    tooltipText?: string;
    /** Label for the remove button's tooltip. */
    removeTooltip?: string;
    onClick?: () => void;
    onRemove?: () => void;
}

/**
 * Shared 200px-wide card shell used by FileUploadCard and ArtifactAttachmentCard.
 * Handles the remove button, keyboard affordance, filename pill, and hover tooltip
 * so the two attachment-card variants share one layout.
 */
export const AttachmentCardShell: React.FC<AttachmentCardShellProps> = ({ filename, preview, inlineText, tooltipText, removeTooltip = "Remove", onClick, onRemove }) => {
    const clickable = Boolean(onClick);

    const body = (
        <div
            className={cn("relative inline-flex w-[200px] flex-col rounded-lg border bg-(--background-w10) shadow-sm transition-colors", clickable && "cursor-pointer hover:border-(--primary-w20)")}
            role={clickable ? "button" : undefined}
            tabIndex={clickable ? 0 : undefined}
            onClick={clickable ? onClick : undefined}
            onKeyDown={
                clickable
                    ? event => {
                          if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              onClick?.();
                          }
                      }
                    : undefined
            }
        >
            {onRemove && (
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={event => {
                        event.stopPropagation();
                        onRemove();
                    }}
                    className="absolute -top-2 -left-2 z-10 h-5 w-5 rounded-full border bg-(--background-w10) p-0 shadow-sm hover:bg-(--secondary-w10)"
                    tooltip={removeTooltip}
                    tooltipSide="left"
                >
                    <XIcon className="h-3 w-3" />
                </Button>
            )}

            {/* The inline-text branch can size to content, but we floor it at 80px
                (the fixed preview-box height) so text / image / doc cards all
                render at the same overall height regardless of which branch
                each one took. */}
            {inlineText ? <div className="min-h-20">{inlineText}</div> : <div className="relative h-20 w-full overflow-hidden rounded-t-lg bg-(--secondary-w10)">{preview}</div>}

            <div className="flex items-center gap-1 px-2 pb-2">
                <span className="inline-block max-w-[170px] truncate rounded bg-(--secondary-w10) px-2 py-0.5 text-[10px] font-semibold tracking-wider text-(--secondary-text-wMain)" title={filename}>
                    {filename}
                </span>
            </div>
        </div>
    );

    if (!clickable) return body;

    return (
        <Tooltip>
            <TooltipTrigger asChild>{body}</TooltipTrigger>
            <TooltipContent side="top">
                <p>{tooltipText ?? filename}</p>
            </TooltipContent>
        </Tooltip>
    );
};

/**
 * Inline text snippet preview shared by attachment cards. Shows up to two
 * trimmed/truncated lines plus an ellipsis when more content is available.
 */
export const AttachmentInlineText: React.FC<{ lines: string[] }> = ({ lines }) => (
    <div className="overflow-hidden px-3 pt-3 pb-2 font-mono text-xs leading-relaxed text-(--secondary-text-wMain)">
        {lines.slice(0, 2).map((line, index) => {
            const trimmed = line.trim();
            const display = trimmed.length > 40 ? trimmed.substring(0, 37) + "..." : trimmed;
            return (
                <div key={`${index}-${line}`} className="truncate">
                    {display || " "}
                </div>
            );
        })}
        {lines.length > 2 && <div className="text-(--secondary-text-w50)">...</div>}
    </div>
);
