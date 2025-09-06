import React from "react";
import { cn } from "@/lib/utils";

interface FileIconProps {
    filename: string;
    mimeType?: string;
    content?: string;
    size?: number;
    className?: string;
}

const getFileExtension = (filename: string): string => {
    const parts = filename.split('.');
    return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : 'FILE';
};

const getFileTypeColor = (mimeType?: string, filename?: string): string => {
    if (mimeType) {
        if (mimeType.startsWith('text/html') || mimeType === 'application/xhtml+xml') {
            return 'bg-[#e34c26]'; // HTML orange
        }
        if (mimeType === 'application/json' || mimeType === 'text/json') {
            return 'bg-[#fbc02d] text-[#333]'; // JSON yellow with dark text
        }
        if (mimeType === 'application/yaml' || mimeType === 'text/yaml' || mimeType === 'application/x-yaml' || mimeType === 'text/x-yaml') {
            return 'bg-[#cb171e]'; // YAML red
        }
        if (mimeType.startsWith('text/')) {
            return 'bg-[#5c6bc0]'; // Text blue
        }
        if (mimeType.startsWith('text/markdown') || mimeType === 'application/markdown') {
            return 'bg-[#6c757d]'; // Markdown gray
        }
    }
    
    // Fallback based on filename extension
    const ext = filename ? getFileExtension(filename).toLowerCase() : '';
    switch (ext) {
        case 'html':
        case 'htm':
            return 'bg-[#e34c26]';
        case 'json':
            return 'bg-[#fbc02d] text-[#333]';
        case 'yaml':
        case 'yml':
            return 'bg-[#cb171e]';
        case 'md':
        case 'markdown':
            return 'bg-[#6c757d]';
        case 'txt':
            return 'bg-[#5c6bc0]';
        default:
            return 'bg-[#6c757d]'; // Default gray
    }
};

const truncateContent = (content: string, maxLength: number = 200): string => {
    if (!content || typeof content !== 'string') {
        return '';
    }
    if (content.length <= maxLength) {
        return content;
    }
    // Truncate at word boundary if possible
    const truncated = content.substring(0, maxLength);
    const lastSpaceIndex = truncated.lastIndexOf(' ');
    const lastNewlineIndex = truncated.lastIndexOf('\n');
    
    // Use the latest boundary that's not too close to the start
    const boundaryIndex = Math.max(lastSpaceIndex, lastNewlineIndex);
    if (boundaryIndex > maxLength * 0.7) {
        return truncated.substring(0, boundaryIndex) + '...';
    }
    
    return truncated + '...';
};

export const FileIcon: React.FC<FileIconProps> = ({ 
    filename, 
    mimeType, 
    content, 
    size,
    className 
}) => {
    // Validate required props
    if (!filename || typeof filename !== 'string') {
        console.warn('FileIcon: filename is required and must be a string');
        return null;
    }

    const extension = getFileExtension(filename);
    const typeColor = getFileTypeColor(mimeType, filename);
    const previewContent = content ? truncateContent(content) : '';

    return (
        <div className={cn("relative flex-shrink-0 transition-transform duration-200 hover:scale-105", className)}>
            {/* Main document icon */}
            <div className="relative w-[60px] h-[66px] bg-gradient-to-b from-white via-[#fafafa] to-[#f5f5f5] dark:from-gray-100 dark:via-gray-200 dark:to-gray-300 border border-[#e0e0e0] dark:border-gray-400 overflow-visible rounded-sm transition-all duration-200">
                {/* Shadow effects */}
                <div className="absolute top-[10px] left-0 right-0 bottom-0 z-[-1] shadow-[0_2px_4px_rgba(0,0,0,0.15)] dark:shadow-[0_2px_4px_rgba(0,0,0,0.25)]" />
                <div className="absolute bottom-[7px] left-[2px] w-[45%] h-[20%] bg-[#777] dark:bg-[#555] shadow-[0_15px_10px_#777] dark:shadow-[0_15px_10px_#555] transform rotate-[-3deg] z-[-2] opacity-60" />
                <div className="absolute bottom-[7px] right-[2px] w-[45%] h-[20%] bg-[#777] dark:bg-[#555] shadow-[0_15px_10px_#777] dark:shadow-[0_15px_10px_#555] transform rotate-[3deg] z-[-2] opacity-60" />
                
                {/* Corner fold */}
                <div className="absolute top-0 right-0 w-0 h-0 border-l-[10px] border-l-transparent border-b-[10px] border-b-[#d0d0d0] dark:border-b-gray-500 z-[2] filter drop-shadow-sm" />
                <div className="absolute top-0 right-0 w-0 h-0 border-l-[9px] border-l-transparent border-b-[9px] border-b-[#f8f8f8] dark:border-b-gray-200 z-[3]" />
                
                {/* Content preview */}
                <div className="absolute top-[4px] left-[4px] right-[14px] bottom-[20px] font-mono text-[1.5px] leading-[1.4] text-[#444] dark:text-[#333] overflow-hidden">
                    {previewContent && (
                        <div className="whitespace-pre-wrap break-words text-[1.5px] select-none">
                            {previewContent}
                        </div>
                    )}
                    {!previewContent && (
                        <div className="flex items-center justify-center h-full text-[#999] dark:text-[#666] text-[2px] font-medium select-none">
                            {size ? `${Math.round(size / 1024)}KB` : 'File'}
                        </div>
                    )}
                </div>
                
                {/* File type badge */}
                <div className={cn(
                    "absolute bottom-[4px] right-[4px] text-white px-[3px] py-[1px] text-[5px] font-bold rounded-[1px] z-[4] shadow-sm select-none transition-all duration-200",
                    typeColor
                )}>
                    {extension.length > 4 ? extension.substring(0, 4) : extension}
                </div>
            </div>
        </div>
    );
};
