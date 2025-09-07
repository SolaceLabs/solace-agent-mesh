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

const getFileTypeEmoji = (mimeType?: string, filename?: string): string | null => {
    if (mimeType) {
        // Image files
        if (mimeType.startsWith('image/')) {
            return '🖼️';
        }
        // Video files
        if (mimeType.startsWith('video/')) {
            return '🎬';
        }
        // Audio files
        if (mimeType.startsWith('audio/')) {
            return '🎵';
        }
        // PDF files
        if (mimeType === 'application/pdf') {
            return '📄';
        }
        // Archive files
        if (mimeType === 'application/zip' || mimeType === 'application/x-zip-compressed' ||
            mimeType === 'application/x-rar-compressed' || mimeType === 'application/x-tar' ||
            mimeType === 'application/gzip') {
            return '📦';
        }
        // Office documents
        if (mimeType.includes('word') || mimeType.includes('document')) {
            return '📝';
        }
        if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) {
            return '📊';
        }
        if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) {
            return '📈';
        }
        // Executable files
        if (mimeType === 'application/x-executable' || mimeType === 'application/x-msdownload') {
            return '⚙️';
        }
    }

    // Fallback based on filename extension
    const ext = filename ? getFileExtension(filename).toLowerCase() : '';
    switch (ext) {
        // Images
        case 'jpg':
        case 'jpeg':
        case 'png':
        case 'gif':
        case 'bmp':
        case 'webp':
        case 'svg':
        case 'ico':
            return '🖼️';
        // Videos
        case 'mp4':
        case 'avi':
        case 'mov':
        case 'wmv':
        case 'flv':
        case 'webm':
        case 'mkv':
            return '🎬';
        // Audio
        case 'mp3':
        case 'wav':
        case 'flac':
        case 'aac':
        case 'ogg':
        case 'm4a':
            return '🎵';
        // Documents
        case 'pdf':
            return '📄';
        case 'doc':
        case 'docx':
            return '📝';
        case 'xls':
        case 'xlsx':
            return '📊';
        case 'ppt':
        case 'pptx':
            return '📈';
        // Archives
        case 'zip':
        case 'rar':
        case '7z':
        case 'tar':
        case 'gz':
            return '📦';
        // Executables
        case 'exe':
        case 'msi':
        case 'dmg':
        case 'pkg':
        case 'deb':
        case 'rpm':
            return '⚙️';
        // Fonts
        case 'ttf':
        case 'otf':
        case 'woff':
        case 'woff2':
            return '🔤';
        default:
            return null;
    }
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
    const fileEmoji = getFileTypeEmoji(mimeType, filename);
    const previewContent = content ? truncateContent(content) : '';

    return (
        <div className={cn("relative flex-shrink-0", className)}>
            {/* Shadow container - positioned behind but shadows extend beyond */}
            <div className="absolute inset-0 overflow-visible">
                {/* Left corner shadow element */}
                <div className="absolute bottom-[5px] left-[5px] w-[49%] h-[50%] bg-[#666] dark:bg-[#444] shadow-[0_6px_12px_rgba(0,0,0,0.3)] dark:shadow-[0_8px_8px_rgba(0,0,0,1.0)] transform rotate-[4deg] skew-[-10deg] opacity-70"></div>
                {/* Right corner shadow element */}
                <div className="absolute bottom-[5px] right-[5px] w-[49%] h-[50%] bg-[#666] dark:bg-[#444] shadow-[0_6px_12px_rgba(0,0,0,0.3)] dark:shadow-[0_8px_8px_rgba(0,0,0,1)] transform rotate-[-4deg] skew-[10deg] opacity-70"></div>
            </div>

            {/* Main document icon with square corners */}
            <div className="relative w-[60px] h-[75px] bg-gradient-to-b from-white via-[#fafafa] to-[#f5f5f5] dark:from-gray-100 dark:via-gray-200 dark:to-gray-300 border border-[#e0e0e0] dark:border-gray-400 shadow-[0_4px_8px_rgba(0,0,0,0.15)] dark:shadow-[0_4px_8px_rgba(0,0,0,0.3)]">

                {/* Content preview or emoji */}
                <div className="absolute top-[4px] left-[4px] right-[4px] bottom-[20px] font-mono text-[3.5px] leading-[1.4] text-[#444] dark:text-[#333] overflow-hidden">
                    {fileEmoji ? (
                        <div className="flex items-center justify-center h-full">
                            <span className="text-[42px] select-none">{fileEmoji}</span>
                        </div>
                    ) : previewContent ? (
                        <div className="whitespace-pre-wrap break-words text-[8px] select-none">
                            {previewContent}
                        </div>
                    ) : (
                        <div className="flex h-full text-[#999] dark:text-[#666] text-[8px] font-medium select-none">
                            {size ? `${Math.round(size / 1024)}KB` : 'File'}
                        </div>
                    )}
                </div>

                {/* File type badge */}
                <div className={cn(
                    "absolute bottom-[4px] right-[4px] text-white px-[4px] py-[2px] text-[10px] font-bold z-[4] shadow-sm select-none",
                    typeColor
                )}>
                    {extension.length > 4 ? extension.substring(0, 4) : extension}
                </div>
            </div>
        </div>
    );
};
