import React, { useState, useEffect } from "react";
import { Download, ChevronDown, Trash, Info, ChevronUp, CircleAlert, Pencil } from "lucide-react";

import { Button, Spinner } from "@/lib/components/ui";
import { cn, formatBytes } from "@/lib/utils";

import { FileIcon, ProjectBadge } from "../file";

const ErrorState: React.FC<{ message: string }> = ({ message }) => (
    <div className="w-full rounded-lg border border-[var(--color-error-w100)] bg-[var(--color-error-wMain-50)] p-3">
        <div className="text-sm text-[var(--color-error-wMain)]">Error: {message}</div>
    </div>
);

export interface ArtifactBarProps {
    filename: string;
    description?: string;
    mimeType?: string;
    size?: number;
    status: "in-progress" | "completed" | "failed";
    expandable?: boolean;
    expanded?: boolean;
    onToggleExpand?: () => void;
    actions?: {
        onDownload?: () => void;
        onPreview?: () => void;
        onDelete?: () => void;
        onInfo?: () => void;
        onExpand?: () => void;
        onEdit?: () => void;
    };
    // For creation progress
    bytesTransferred?: number;
    error?: string;
    // For rendered content when expanded
    expandedContent?: React.ReactNode;
    context?: "chat" | "list";
    isDeleted?: boolean; // If true, show as deleted
    version?: number; // Version number to display (e.g., 1, 2, 3)
    source?: string; // Source of the artifact (e.g., "project")
}

export const ArtifactBar: React.FC<ArtifactBarProps> = ({
    filename,
    description,
    mimeType,
    size,
    status,
    expandable = false,
    expanded = false,
    onToggleExpand,
    actions,
    bytesTransferred,
    error,
    expandedContent,
    context = "chat",
    isDeleted = false,
    version,
    source,
}) => {
    const [contentForAnimation, setContentForAnimation] = useState(expandedContent);
    const [isDarkMode, setIsDarkMode] = useState(() => document.documentElement.classList.contains("dark"));

    useEffect(() => {
        if (expandedContent) {
            setContentForAnimation(expandedContent);
        } else {
            // When expandedContent is removed, wait for animation to finish before removing from DOM
            const timer = setTimeout(() => {
                setContentForAnimation(undefined);
            }, 300); // Corresponds to duration-300
            return () => clearTimeout(timer);
        }
    }, [expandedContent]);

    // Track dark mode changes
    useEffect(() => {
        const observer = new MutationObserver(() => {
            setIsDarkMode(document.documentElement.classList.contains("dark"));
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["class"],
        });

        return () => observer.disconnect();
    }, []);

    // Validate required props
    if (!filename || typeof filename !== "string") {
        console.error("ArtifactBar: filename is required and must be a string");
        return <ErrorState message="Invalid artifact filename" />;
    }

    if (!status || !["in-progress", "completed", "failed"].includes(status)) {
        console.error("ArtifactBar: status must be one of: in-progress, completed, failed");
        return <ErrorState message="Invalid artifact status" />;
    }

    const getStatusDisplay = () => {
        // If deleted, override the status display
        if (isDeleted) {
            return {
                text: "Deleted",
                className: "text-[var(--color-secondary-foreground)]",
            };
        }

        switch (status) {
            case "in-progress":
                return {
                    text: bytesTransferred ? `Creating... ${formatBytes(bytesTransferred)}` : "Creating...",
                    className: "text-[var(--color-info-wMain)]",
                };
            case "failed":
                return {
                    text: error || "Failed to create",
                    className: "text-[var(--color-error-wMain)]",
                };
            case "completed":
                return {
                    text: size ? formatBytes(size) : "",
                };
            default:
                return {
                    text: "Unknown",
                    className: "text-[var(--color-secondary-foreground)]",
                };
        }
    };

    const statusDisplay = getStatusDisplay();

    // Helper function to clean and truncate description
    const getDisplayDescription = (desc?: string, maxLength: number = 100): string => {
        if (!desc || typeof desc !== "string") {
            return "";
        }

        // Normalize whitespace and remove newlines
        const cleaned = desc.replace(/\s+/g, " ").trim();

        if (cleaned.length <= maxLength) {
            return cleaned;
        }

        // Truncate at word boundary if possible
        const truncated = cleaned.substring(0, maxLength);
        const lastSpaceIndex = truncated.lastIndexOf(" ");

        if (lastSpaceIndex > maxLength * 0.7) {
            return truncated.substring(0, lastSpaceIndex) + "...";
        }

        return truncated + "...";
    };

    const displayDescription = getDisplayDescription(description);
    const hasDescription = description && description.trim();

    const handleBarClick = () => {
        if (status === "completed" && actions?.onPreview) {
            try {
                actions.onPreview();
            } catch (error) {
                console.error("Preview failed:", error);
            }
        }
    };

    // Define shadow and background colors based on theme
    // Light mode: background-w10, shadow using secondary-w8040
    // Dark mode: background-wMain, shadow using primary-w90 (darker shadows)
    const backgroundColor = isDarkMode ? "var(--color-background-wMain)" : "var(--color-background-w10)";
    const restingShadow = isDarkMode ? "0px 1px 4px 0px var(--color-primary-w90)" : "0px 1px 4px 0px var(--color-secondary-w8040)";
    const hoverShadow = isDarkMode ? "0px 2px 8px 0px var(--color-primary-w90)" : "0px 2px 8px 0px var(--color-secondary-w8040)";

    // Determine if this artifact is clickable
    const isClickable = status === "completed" && actions?.onPreview && !isDeleted;
    // Show shadow for all artifacts in chat context (not deleted), but only enable hover for clickable ones
    const showShadow = context === "chat" && !isDeleted;

    return (
        <div
            className={`w-full ${isClickable ? "cursor-pointer" : ""} ${context === "list" ? "border-b" : ""} ${isDeleted ? "opacity-60" : ""} transition-shadow duration-200 ease-in-out`}
            style={{
                backgroundColor,
                boxShadow: showShadow ? restingShadow : undefined,
                borderRadius: context === "list" ? undefined : "4px",
            }}
            onMouseEnter={e => {
                if (isClickable) {
                    e.currentTarget.style.boxShadow = hoverShadow;
                }
            }}
            onMouseLeave={e => {
                if (isClickable) {
                    e.currentTarget.style.boxShadow = restingShadow;
                }
            }}
            onClick={isDeleted ? undefined : handleBarClick}
        >
            <div className="flex min-h-[60px] items-center gap-3 p-3">
                {/* File Icon */}
                <FileIcon filename={filename} mimeType={mimeType} size={size} className="flex-shrink-0" />

                {/* File Info Section */}
                <div className="min-w-0 flex-1 py-1">
                    {/*Primary line: Description (if available) or Filename */}
                    <div className="flex items-center gap-2">
                        <div className="truncate text-sm leading-tight font-semibold" title={hasDescription ? description : filename}>
                            {hasDescription ? displayDescription : filename.length > 50 ? `${filename.substring(0, 47)}...` : filename}
                        </div>
                        {/* Project badge */}
                        {source === "project" && <ProjectBadge />}
                    </div>

                    {/* Secondary line: Filename (if description shown) or status */}
                    <div className="text-secondary-foreground mt-1 flex items-center gap-2 text-xs leading-tight" title={hasDescription ? filename : statusDisplay.text}>
                        {hasDescription ? (
                            <div className="truncate">
                                {filename.length > 60 ? `${filename.substring(0, 57)}...` : filename}
                                {version !== undefined && context === "chat" && <span className="ml-1.5">(v{version})</span>}
                            </div>
                        ) : (
                            <>
                                {status === "in-progress" && <Spinner size="small" variant="primary" />}
                                <span className={statusDisplay.className}>{statusDisplay.text}</span>
                            </>
                        )}
                    </div>

                    {/* Tertiary line: Status when description is shown */}
                    {hasDescription && (
                        <div className={cn("mt-0.5 flex items-center gap-2 text-xs leading-tight", statusDisplay.className)}>
                            {status === "in-progress" && <Spinner size="small" variant="primary" />}
                            <span>{statusDisplay.text}</span>
                        </div>
                    )}
                </div>

                {/* Actions Section */}
                <div className="flex flex-shrink-0 items-center gap-1">
                    {status === "completed" && actions?.onInfo && !isDeleted && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onInfo?.();
                                } catch (error) {
                                    console.error("Info failed:", error);
                                }
                            }}
                            tooltip="Info"
                        >
                            <Info className="h-4 w-4" />
                        </Button>
                    )}

                    {status === "completed" && actions?.onDownload && !isDeleted && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onDownload?.();
                                } catch (error) {
                                    console.error("Download failed:", error);
                                }
                            }}
                            tooltip="Download"
                        >
                            <Download className="h-4 w-4" />
                        </Button>
                    )}

                    {status === "completed" && actions?.onExpand && !isDeleted && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onExpand?.();
                                } catch (error) {
                                    console.error("Expand failed:", error);
                                }
                            }}
                            tooltip={expanded ? "Collapse" : "Expand"}
                        >
                            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                    )}

                    {status === "completed" && actions?.onEdit && !isDeleted && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onEdit?.();
                                } catch (error) {
                                    console.error("Edit failed:", error);
                                }
                            }}
                            tooltip="Edit Description"
                        >
                            <Pencil className="h-4 w-4" />
                        </Button>
                    )}

                    {status === "completed" && actions?.onDelete && !isDeleted && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onDelete?.();
                                } catch (error) {
                                    console.error("Delete failed:", error);
                                }
                            }}
                            tooltip="Delete"
                        >
                            <Trash className="h-4 w-4" />
                        </Button>
                    )}

                    {/* Error indicator for failed status */}
                    {status === "failed" && (
                        <div className="pr-4" title="Artifact action failed">
                            <CircleAlert className="h-4 w-4 text-[var(--color-error-wMain)]" />
                        </div>
                    )}
                </div>

                {/* Expand/Collapse Toggle */}
                {expandable && onToggleExpand && !isDeleted && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={e => {
                            e.stopPropagation();
                            try {
                                onToggleExpand();
                            } catch (error) {
                                console.error("Toggle expand failed:", error);
                            }
                        }}
                        tooltip={expanded ? "Collapse" : "Expand"}
                    >
                        {expanded ? <ChevronUp className="h-4 w-4 transition-transform duration-200" /> : <ChevronDown className="h-4 w-4 transition-transform duration-200" />}
                    </Button>
                )}
            </div>

            {/* Expanded Content Section */}
            <div className={cn("grid grid-rows-[0fr] transition-[grid-template-rows] duration-300 ease-in-out", expanded && expandedContent && "grid-rows-[1fr]")}>
                <div className="overflow-hidden">
                    {contentForAnimation && (
                        <>
                            <hr className="border-t" />
                            <div className="p-3">{contentForAnimation}</div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
