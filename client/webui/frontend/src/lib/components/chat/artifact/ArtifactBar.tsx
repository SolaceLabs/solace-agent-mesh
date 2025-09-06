import React from "react";
import { Download, Eye, ChevronDown, ChevronRight } from "lucide-react";

import { Button } from "@/lib/components/ui";
import { FileIcon } from "../file/FileIcon";
import { cn } from "@/lib/utils";

export interface ArtifactBarProps {
    filename: string;
    description?: string;
    mimeType?: string;
    size?: number;
    status: "creating" | "completed" | "failed";
    expandable?: boolean;
    expanded?: boolean;
    onToggleExpand?: () => void;
    actions?: {
        onDownload?: () => void;
        onPreview?: () => void;
        onDelete?: () => void;
    };
    // For creation progress
    bytesTransferred?: number;
    error?: string;
    // For content preview
    content?: string;
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
    content,
}) => {
    const getStatusDisplay = () => {
        switch (status) {
            case "creating":
                return {
                    text: bytesTransferred ? `Creating... ${Math.round(bytesTransferred / 1024)}KB` : "Creating...",
                    className: "text-blue-600 dark:text-blue-400",
                };
            case "failed":
                return {
                    text: error || "Failed to create",
                    className: "text-red-600 dark:text-red-400",
                };
            case "completed":
                return {
                    text: size ? `${Math.round(size / 1024)}KB` : "Ready",
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

    return (
        <div className="w-full border border-[#e0e0e0] dark:border-[#404040] rounded-lg bg-white dark:bg-gray-800 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-3 p-3">
                {/* File Icon with Preview */}
                <FileIcon
                    filename={filename}
                    mimeType={mimeType}
                    content={content}
                    size={size}
                    className="flex-shrink-0"
                />

                {/* File Info Section */}
                <div className="flex-1 min-w-0">
                    {/* Primary line: Filename */}
                    <div className="font-mono text-sm font-medium text-gray-900 dark:text-gray-100 truncate" title={filename}>
                        {filename}
                    </div>
                    
                    {/* Secondary line: Description or status */}
                    <div className="text-xs text-gray-600 dark:text-gray-400 truncate" title={description}>
                        {description || statusDisplay.text}
                    </div>
                    
                    {/* Tertiary line: Status for completed files */}
                    {status === "completed" && description && (
                        <div className={cn("text-xs", statusDisplay.className)}>
                            {statusDisplay.text}
                        </div>
                    )}
                </div>

                {/* Actions Section */}
                <div className="flex items-center gap-1">
                    {status === "completed" && actions?.onDownload && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={actions.onDownload}
                            tooltip="Download"
                            className="h-8 w-8 p-0"
                        >
                            <Download className="h-4 w-4" />
                        </Button>
                    )}
                    
                    {status === "completed" && actions?.onPreview && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={actions.onPreview}
                            tooltip="Preview"
                            className="h-8 w-8 p-0"
                        >
                            <Eye className="h-4 w-4" />
                        </Button>
                    )}
                    
                    {/* Progress indicator for creating status */}
                    {status === "creating" && (
                        <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    )}
                    
                    {/* Error indicator for failed status */}
                    {status === "failed" && (
                        <div className="w-6 h-6 rounded-full bg-red-100 dark:bg-red-900 flex items-center justify-center">
                            <div className="w-3 h-3 rounded-full bg-red-600" />
                        </div>
                    )}
                </div>

                {/* Expand/Collapse Toggle */}
                {expandable && onToggleExpand && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onToggleExpand}
                        tooltip={expanded ? "Collapse" : "Expand"}
                        className="h-8 w-8 p-0 flex-shrink-0"
                    >
                        {expanded ? (
                            <ChevronDown className="h-4 w-4" />
                        ) : (
                            <ChevronRight className="h-4 w-4" />
                        )}
                    </Button>
                )}
            </div>
        </div>
    );
};
