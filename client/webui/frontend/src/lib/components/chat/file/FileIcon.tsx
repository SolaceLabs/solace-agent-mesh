import React from "react";
import { cn } from "@/lib/utils";
import { FileImage, FileVideo, FileAudio, FileText, Archive, FileSpreadsheet, Presentation, Settings, Type, File, FileCode } from "lucide-react";

interface FileIconProps {
    filename: string;
    mimeType?: string;
    size?: number;
    className?: string;
}

const getFileExtension = (filename: string): string => {
    const parts = filename.split(".");
    return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
};

const getFileStyles = (type: string) => {
    switch (type) {
        case "html":
            return "bg-[#e34c26]";
        case "json":
            return "bg-[#fbc02d] text-[#333]";
        case "yaml":
            return "bg-[#cb171e]";
        case "markdown":
            return "bg-[#6c757d]";
        case "text":
            return "bg-[#5c6bc0]";
        default:
            return "bg-gray-500";
    }
};

const getFileTypeIcon = (mimeType?: string, filename?: string): React.ReactElement | null => {
    const iconProps = { className: "text-secondary-foreground/60" };

    if (mimeType) {
        // Image files
        if (mimeType.startsWith("image/")) {
            return <FileImage {...iconProps} />;
        }
        // Video files
        if (mimeType.startsWith("video/")) {
            return <FileVideo {...iconProps} />;
        }
        // Audio files
        if (mimeType.startsWith("audio/")) {
            return <FileAudio {...iconProps} />;
        }
        // PDF files
        if (mimeType === "application/pdf") {
            return <FileText {...iconProps} />;
        }
        // Archive files
        if (mimeType === "application/zip" || mimeType === "application/x-zip-compressed" || mimeType === "application/x-rar-compressed" || mimeType === "application/x-tar" || mimeType === "application/gzip") {
            return <Archive {...iconProps} />;
        }
        // Office documents
        if (mimeType.includes("word") || mimeType.includes("document")) {
            return <FileText {...iconProps} />;
        }
        if (mimeType.includes("excel") || mimeType.includes("spreadsheet")) {
            return <FileSpreadsheet {...iconProps} />;
        }
        if (mimeType.includes("powerpoint") || mimeType.includes("presentation")) {
            return <Presentation {...iconProps} />;
        }
        // Executable files
        if (mimeType === "application/x-executable" || mimeType === "application/x-msdownload") {
            return <Settings {...iconProps} />;
        }
    }

    // Fallback based on filename extension
    const ext = filename ? getFileExtension(filename).toLowerCase() : "";
    switch (ext) {
        // Images
        case "jpg":
        case "jpeg":
        case "png":
        case "gif":
        case "bmp":
        case "webp":
        case "svg":
        case "ico":
            return <FileImage {...iconProps} />;
        // Videos
        case "mp4":
        case "avi":
        case "mov":
        case "wmv":
        case "flv":
        case "webm":
        case "mkv":
            return <FileVideo {...iconProps} />;
        // Audio
        case "mp3":
        case "wav":
        case "flac":
        case "aac":
        case "ogg":
        case "m4a":
            return <FileAudio {...iconProps} />;
        // Documents
        case "pdf":
        case "doc":
        case "docx":
            return <FileText {...iconProps} />;
        case "xls":
        case "xlsx":
        case "csv":
            return <FileSpreadsheet {...iconProps} />;
        case "ppt":
        case "pptx":
            return <Presentation {...iconProps} />;
        // Archives
        case "zip":
        case "rar":
        case "7z":
        case "tar":
        case "gz":
            return <Archive {...iconProps} />;
        // Executables
        case "exe":
        case "msi":
        case "dmg":
        case "pkg":
        case "deb":
        case "rpm":
            return <Settings {...iconProps} />;
        // Fonts
        case "ttf":
        case "otf":
        case "woff":
        case "woff2":
            return <Type {...iconProps} />;
        case "htm":
        case "html":
            return <FileCode {...iconProps} />;
        default:
            return null;
    }
};

const getFileTypeColor = (mimeType?: string, filename?: string): string => {
    if (mimeType) {
        if (mimeType.startsWith("text/html") || mimeType === "application/xhtml+xml") {
            return getFileStyles("html");
        }
        if (mimeType === "application/json" || mimeType === "text/json") {
            return getFileStyles("json");
        }
        if (mimeType === "application/yaml" || mimeType === "text/yaml" || mimeType === "application/x-yaml" || mimeType === "text/x-yaml") {
            return getFileStyles("yaml");
        }
        if (mimeType.startsWith("text/")) {
            return getFileStyles("text");
        }
        if (mimeType.startsWith("text/markdown") || mimeType === "application/markdown") {
            return getFileStyles("markdown");
        }
    }

    // Fallback based on filename extension
    const ext = filename ? getFileExtension(filename).toLowerCase() : "";
    switch (ext) {
        case "html":
        case "htm":
            return getFileStyles("html");
        case "json":
            return getFileStyles("json");
        case "yaml":
        case "yml":
            return getFileStyles("yaml");
        case "md":
        case "markdown":
            return getFileStyles("markdown");
        case "txt":
            return getFileStyles("text");
        default:
            return getFileStyles("default");
    }
};

export const FileIcon: React.FC<FileIconProps> = ({ filename, mimeType, className }) => {
    // Validate required props
    if (!filename || typeof filename !== "string") {
        console.warn("FileIcon: filename is required and must be a string");
        return null;
    }

    const extension = getFileExtension(filename);
    const typeColor = getFileTypeColor(mimeType, filename);
    const fileIcon = getFileTypeIcon(mimeType, filename);

    return (
        <div className={cn("relative flex-shrink-0", className)}>
            {/* Main document icon with square corners */}
            <div className="bg-muted/50 relative h-[75px] w-[60px] border">
                {/* Icon */}
                <div className="absolute top-[4px] right-[4px] bottom-[24px] left-[4px] overflow-hidden font-mono text-[3.5px] leading-[1.4]">
                    {fileIcon ? (
                        <div className="flex h-full items-center justify-center">{fileIcon}</div>
                    ) : (
                        <div className="text-secondary-foreground flex h-full text-[8px] select-none">
                            <div className="flex h-full w-full items-center justify-center">{<File className="text-secondary-foreground/60" />}</div>
                        </div>
                    )}
                </div>

                {/* File type badge */}
                <div className={cn("absolute right-[4px] bottom-[4px] z-[4] px-[4px] py-[2px] text-[10px] font-bold text-[var(--color-primary-text-w10)] select-none", typeColor)}>{extension.length > 4 ? extension.substring(0, 4) : extension}</div>
            </div>
        </div>
    );
};
