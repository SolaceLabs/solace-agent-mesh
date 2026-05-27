import React from "react";
import { XIcon } from "lucide-react";

import { Button, Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui";
import { useIsMobile } from "@/lib/hooks";
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
    const isMobile = useIsMobile();

    // On mobile, render a compact thumbnail (icon/preview only, filename via tooltip)
    // to fit multiple attachments alongside the input without dominating the viewport.
    if (isMobile) {
        const thumb = (
            <div
                className={cn("relative inline-flex size-16 overflow-hidden rounded-lg border bg-(--secondary-w10) shadow-sm transition-colors", clickable && "cursor-pointer hover:border-(--primary-w20)")}
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
                aria-label={filename}
                title={tooltipText ?? filename}
            >
                {onRemove && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={event => {
                            event.stopPropagation();
                            onRemove();
                        }}
                        className="absolute -top-1.5 -left-1.5 z-10 h-5 w-5 rounded-full border bg-(--background-w10) p-0 shadow-sm hover:bg-(--secondary-w10)"
                        tooltip={removeTooltip}
                        tooltipSide="left"
                    >
                        <XIcon className="h-3 w-3" />
                    </Button>
                )}
                {inlineText ?? preview}
            </div>
        );

        if (!clickable) return thumb;
        return (
            <Tooltip>
                <TooltipTrigger asChild>{thumb}</TooltipTrigger>
                <TooltipContent side="top">
                    <p>{tooltipText ?? filename}</p>
                </TooltipContent>
            </Tooltip>
        );
    }

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
 * Inline text snippet preview shared by attachment cards. Shows up to three
 * non-blank trimmed/truncated lines. When more content exists beyond the
 * third visible line, the third line itself ends in "…" rather than burning
 * a fourth row on a standalone ellipsis. Blank lines are skipped so the
 * snippet doesn't waste a row on a paragraph break.
 */
const SNIPPET_MAX_LINES = 3;
const SNIPPET_LINE_MAX_CHARS = 40;

export const AttachmentInlineText: React.FC<{ lines: string[] }> = ({ lines }) => {
    const nonBlank = lines.map(l => l.trim()).filter(l => l.length > 0);
    const visible = nonBlank.slice(0, SNIPPET_MAX_LINES);
    const hasMore = nonBlank.length > visible.length;

    // Use the single-character Unicode ellipsis (U+2026) so our explicit
    // truncation matches what CSS `text-overflow: ellipsis` renders when a
    // line is wider than the card. Mixing "…" and "..." in the same card
    // looked inconsistent.
    const ELLIPSIS = "…";

    return (
        <div className="overflow-hidden px-3 pt-3 pb-2 font-mono text-xs leading-relaxed text-(--secondary-text-wMain)">
            {visible.map((line, index) => {
                const isLast = index === visible.length - 1;
                // Append "…" on the last visible line if there's more content
                // beyond it; otherwise just truncate per-line at the char cap.
                let display: string;
                if (isLast && hasMore) {
                    const cap = SNIPPET_LINE_MAX_CHARS - 1;
                    display = line.length > cap ? line.substring(0, cap) + ELLIPSIS : line + ELLIPSIS;
                } else {
                    display = line.length > SNIPPET_LINE_MAX_CHARS ? line.substring(0, SNIPPET_LINE_MAX_CHARS - 1) + ELLIPSIS : line;
                }
                return (
                    <div key={`${index}-${line}`} className="truncate">
                        {display}
                    </div>
                );
            })}
        </div>
    );
};
