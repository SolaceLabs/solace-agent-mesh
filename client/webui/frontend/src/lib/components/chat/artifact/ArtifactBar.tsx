import React, { useState, useEffect } from "react";
import { Download, Eye, ChevronDown, Trash, Info, ChevronUp } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { FileIcon } from "../file/FileIcon";
import { cn } from "@/lib/utils";

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
    };
    // For creation progress
    bytesTransferred?: number;
    error?: string;
    // For content preview in file icon
    content?: string;
    // For rendered content when expanded
    expandedContent?: React.ReactNode;
}

export const ArtifactBar: React.FC<ArtifactBarProps> = ({ filename, description, mimeType, size, status, expandable = false, expanded = false, onToggleExpand, actions, bytesTransferred, error, content, expandedContent }) => {
    const [contentForAnimation, setContentForAnimation] = useState(expandedContent);

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

    console.log(`[ArtifactBar] Rendering ${filename} with status: ${status}, bytesTransferred: ${bytesTransferred}`);

    // Validate required props
    if (!filename || typeof filename !== "string") {
        console.error("ArtifactBar: filename is required and must be a string");
        return (
            <div className="w-full rounded-lg border border-red-300 bg-red-50 p-3">
                <div className="text-sm text-red-600">Error: Invalid artifact data</div>
            </div>
        );
    }

    if (!status || !["in-progress", "completed", "failed"].includes(status)) {
        console.error("ArtifactBar: status must be one of: in-progress, completed, failed");
        return (
            <div className="w-full rounded-lg border border-red-300 bg-red-50 p-3">
                <div className="text-sm text-red-600">Error: Invalid artifact status</div>
            </div>
        );
    }
    const getStatusDisplay = () => {
        switch (status) {
            case "in-progress":
                return {
                    text: bytesTransferred ? `Creating... ${(bytesTransferred / 1024).toFixed(1)}KB` : "Creating...",
                    className: "text-blue-600 dark:text-blue-400",
                };
            case "failed":
                return {
                    text: error || "Failed to create",
                    className: "text-red-600 dark:text-red-400",
                };
            case "completed":
                return {
                    text: size ? `${(size / 1024).toFixed(1)}KB` : "",
                    className: "text-green-600 dark:text-green-400",
                };
            default:
                return {
                    text: "Unknown",
                    className: "text-gray-600 dark:text-gray-400",
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

    return (
        <div
            className={`w-full rounded-lg border border-[#e0e0e0] bg-white shadow-sm transition-all duration-200 ease-in-out hover:shadow-md dark:border-[#404040] dark:bg-gray-800 ${
                status === "completed" && actions?.onPreview ? "cursor-pointer" : ""
            }`}
            onClick={handleBarClick}
        >
            <div className="flex min-h-[60px] items-center gap-3 p-3">
                {/* File Icon with Preview */}
                <FileIcon filename={filename} mimeType={mimeType} content={content} size={size} className="flex-shrink-0" />

                {/* File Info Section */}
                <div className="min-w-0 flex-1 py-1">
                    {/*Primary line: Description (if available) or Filename */}
                    <div className="truncate text-sm leading-tight font-semibold text-gray-900 dark:text-gray-100" title={hasDescription ? description : filename}>
                        {hasDescription ? displayDescription : filename.length > 50 ? `${filename.substring(0, 47)}...` : filename}
                    </div>

                    {/* Secondary line: Filename (if description shown) or status */}
                    <div className="mt-1 truncate text-xs leading-tight text-gray-600 dark:text-gray-400" title={hasDescription ? filename : statusDisplay.text}>
                        {hasDescription ? (filename.length > 60 ? `${filename.substring(0, 57)}...` : filename) : statusDisplay.text}
                    </div>

                    {/* Tertiary line: Status when description is shown */}
                    {hasDescription && <div className={cn("mt-0.5 text-xs leading-tight", statusDisplay.className)}>{statusDisplay.text}</div>}
                </div>

                {/* Actions Section */}
                <div className="flex flex-shrink-0 items-center gap-1">
                    {status === "completed" && actions?.onInfo && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onInfo?.();
                                } catch (error) {
                                    console.error("Info failed:", error);
                                }
                            }}
                            tooltip="Info"
                            className="h-8 w-8 p-0 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                            <Info className="h-4 w-4" />
                        </Button>
                    )}

                    {status === "completed" && actions?.onDownload && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onDownload?.();
                                } catch (error) {
                                    console.error("Download failed:", error);
                                }
                            }}
                            tooltip="Download"
                            className="h-8 w-8 p-0 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                            <Download className="h-4 w-4" />
                        </Button>
                    )}

                    {status === "completed" && actions?.onPreview && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onPreview?.();
                                } catch (error) {
                                    console.error("Preview failed:", error);
                                }
                            }}
                            tooltip="Preview"
                            className="h-8 w-8 p-0 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                            <Eye className="h-4 w-4" />
                        </Button>
                    )}

                    {status === "completed" && actions?.onExpand && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onExpand?.();
                                } catch (error) {
                                    console.error("Expand failed:", error);
                                }
                            }}
                            tooltip={expanded ? "Collapse" : "Expand"}
                            className="h-8 w-8 p-0 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                        </Button>
                    )}

                    {status === "completed" && actions?.onDelete && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={e => {
                                e.stopPropagation();
                                try {
                                    actions.onDelete?.();
                                } catch (error) {
                                    console.error("Delete failed:", error);
                                }
                            }}
                            tooltip="Delete"
                            className="h-8 w-8 p-0 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                            <Trash className="h-4 w-4" />
                        </Button>
                    )}

                    {/* Progress indicator for in-progress status */}
                    {status === "in-progress" && <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />}

                    {/* Error indicator for failed status */}
                    {status === "failed" && (
                        <div className="flex h-6 w-6 items-center justify-center rounded-full border border-red-200 bg-red-100 dark:border-red-800 dark:bg-red-900">
                            <div className="h-3 w-3 rounded-full bg-red-500 dark:bg-red-400" />
                        </div>
                    )}
                </div>

                {/* Expand/Collapse Toggle */}
                {expandable && onToggleExpand && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={e => {
                            e.stopPropagation();
                            try {
                                onToggleExpand();
                            } catch (error) {
                                console.error("Toggle expand failed:", error);
                            }
                        }}
                        tooltip={expanded ? "Collapse" : "Expand"}
                        className="h-8 w-8 flex-shrink-0 p-0 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700"
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
                            <hr className="border-t border-[#e0e0e0] dark:border-[#404040]" />
                            <div className="p-3">{contentForAnimation}</div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};
