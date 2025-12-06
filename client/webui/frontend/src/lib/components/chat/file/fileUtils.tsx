import { File, FileAudio, FileCode, FileImage, FileJson, FileSpreadsheet, FileText } from "lucide-react";

import type { ArtifactInfo } from "@/lib/types";

import { getRenderType } from "../preview/previewUtils";

export const getFileIcon = (artifact: ArtifactInfo | undefined, className = "h-4 w-4") => {
    if (!artifact) {
        return <File className={className} />;
    }

    const type = getRenderType(artifact.filename, artifact.mime_type);

    switch (type) {
        case "image":
        case "mermaid":
            return <FileImage className={className} />;
        case "audio":
            return <FileAudio className={className} />;
        case "html":
            return <FileCode className={className} />;
        case "text":
            return <FileText className={className} />;
        case "csv":
            return <FileSpreadsheet className={className} />;
        case "json":
            return <FileJson className={className} />;
        default:
            return <File className={className} />;
    }
};

/**
 * Determines if a file should auto-render (images, audio, text, and markdown)
 */
export const shouldAutoRender = (filename?: string, mimeType?: string): boolean => {
    const renderType = getRenderType(filename, mimeType);
    return renderType === "image" || renderType === "audio" || renderType === "text" || renderType === "markdown";
};

/**
 * Determines if a file is user-controllable for rendering (text-based files, images, and audio)
 * Images and audio auto-expand but users should be able to collapse them
 */
export const isUserControllableRendering = (filename?: string, mimeType?: string): boolean => {
    const renderType = getRenderType(filename, mimeType);
    const controllableTypes = ["text", "markdown", "json", "yaml", "csv", "html", "image", "audio"];
    return renderType ? controllableTypes.includes(renderType) : false;
};

/**
 * Generates content preview text for display in the file icon
 */
export const generateContentPreview = (content: string, maxLength: number = 200): string => {
    if (!content || typeof content !== "string") {
        return "";
    }

    // Remove excessive whitespace but preserve structure
    const cleanedContent = content
        .replace(/\r\n/g, "\n") // Normalize line endings
        .replace(/\n{3,}/g, "\n\n") // Limit consecutive newlines
        .replace(/[ \t]{2,}/g, " ") // Limit consecutive spaces/tabs
        .trim();

    if (cleanedContent.length <= maxLength) {
        return cleanedContent;
    }

    // Truncate at word boundary if possible
    const truncated = cleanedContent.substring(0, maxLength);
    const lastSpaceIndex = truncated.lastIndexOf(" ");
    const lastNewlineIndex = truncated.lastIndexOf("\n");

    // Use the latest boundary (space or newline) that's not too close to the start
    const boundaryIndex = Math.max(lastSpaceIndex, lastNewlineIndex);
    if (boundaryIndex > maxLength * 0.7) {
        return truncated.substring(0, boundaryIndex) + "...";
    }

    return truncated + "...";
};

/**
 * Generates preview content for structured data (JSON/YAML)
 */
export const generateStructuredDataPreview = (content: string, type: "json" | "yaml", maxLength: number = 200): string => {
    try {
        if (type === "json") {
            const parsed = JSON.parse(content);
            // Extract key structure for preview
            if (typeof parsed === "object" && parsed !== null) {
                const keys = Object.keys(parsed).slice(0, 5); // Show first 5 keys
                const preview = keys
                    .map(key => {
                        const value = parsed[key];
                        const valueType = Array.isArray(value) ? "array" : typeof value;
                        return `${key}: ${valueType}`;
                    })
                    .join("\n");
                return generateContentPreview(preview, maxLength);
            }
        } else if (type === "yaml") {
            // For YAML, show first few lines that contain key-value pairs
            const lines = content.split("\n").slice(0, 10);
            const keyValueLines = lines.filter(line => line.trim() && !line.trim().startsWith("#") && line.includes(":")).slice(0, 5);
            return generateContentPreview(keyValueLines.join("\n"), maxLength);
        }
    } catch (error) {
        // If parsing fails, fall back to regular content preview
        console.warn(`Failed to parse ${type} for preview:`, error);
    }

    return generateContentPreview(content, maxLength);
};

/**
 * Extracts preview text from different file types for icon display
 */
export const extractPreviewTextForIcon = (content: string, filename?: string, mimeType?: string): string => {
    const renderType = getRenderType(filename, mimeType);

    switch (renderType) {
        case "json":
            return extractJsonPreview(content);
        case "yaml":
            return extractYamlPreview(content);
        case "csv":
            return extractCsvPreview(content);
        case "html":
            return extractHtmlPreview(content);
        case "markdown":
            return extractMarkdownPreview(content);
        default:
            return extractTextPreview(content);
    }
};

/**
 * Extracts preview text from JSON content
 */
export const extractJsonPreview = (content: string): string => {
    try {
        const parsed = JSON.parse(content);
        if (typeof parsed === "object" && parsed !== null) {
            const keys = Object.keys(parsed).slice(0, 8); // Show more keys for icon
            const preview = keys
                .map(key => {
                    const value = parsed[key];
                    if (typeof value === "string") {
                        return `"${key}": "${value.length > 20 ? value.substring(0, 20) + "..." : value}"`;
                    } else if (typeof value === "number" || typeof value === "boolean") {
                        return `"${key}": ${value}`;
                    } else if (Array.isArray(value)) {
                        return `"${key}": [${value.length} items]`;
                    } else if (typeof value === "object" && value !== null) {
                        return `"${key}": {...}`;
                    }
                    return `"${key}": ${typeof value}`;
                })
                .join("\n");
            return `{\n${preview}\n}`;
        }
        return JSON.stringify(parsed, null, 2).substring(0, 150);
    } catch {
        return content.substring(0, 150);
    }
};

/**
 * Extracts preview text from YAML content
 */
export const extractYamlPreview = (content: string): string => {
    const lines = content.split("\n").slice(0, 12);
    const keyValueLines = lines
        .filter(line => {
            const trimmed = line.trim();
            return trimmed && !trimmed.startsWith("#") && (trimmed.includes(":") || trimmed.startsWith("-"));
        })
        .slice(0, 8);
    return keyValueLines.join("\n");
};

/**
 * Extracts preview text from CSV content
 */
export const extractCsvPreview = (content: string): string => {
    const lines = content.split("\n").slice(0, 6);
    return lines
        .map(line => {
            // Truncate very long lines
            return line.length > 50 ? line.substring(0, 50) + "..." : line;
        })
        .join("\n");
};

/**
 * Extracts preview text from HTML content
 */
export const extractHtmlPreview = (content: string): string => {
    // Try to extract meaningful structure
    const structuralTags = content.match(/<(html|head|body|div|section|article|header|footer|nav|main|aside)[^>]*>/gi);
    if (structuralTags && structuralTags.length > 0) {
        return structuralTags.slice(0, 8).join("\n");
    }

    // Fallback to text extraction
    const textContent = content
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "")
        .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, "")
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim();

    return textContent.substring(0, 150);
};

/**
 * Extracts preview text from Markdown content
 */
export const extractMarkdownPreview = (content: string): string => {
    const lines = content.split("\n").slice(0, 10);
    const meaningfulLines = lines
        .filter(line => {
            const trimmed = line.trim();
            return trimmed && !trimmed.startsWith("<!--");
        })
        .slice(0, 6);
    return meaningfulLines.join("\n");
};

/**
 * Extracts preview text from plain text content
 */
export const extractTextPreview = (content: string): string => {
    // For plain text, just return the first portion with some line preservation
    const lines = content.split("\n").slice(0, 8);
    return lines.join("\n").substring(0, 150);
};

/**
 * Generates appropriate preview text based on file type
 */
export const generateFileTypePreview = (content: string, filename?: string, mimeType?: string, maxLength: number = 200): string => {
    const renderType = getRenderType(filename, mimeType);

    switch (renderType) {
        case "json":
            return generateStructuredDataPreview(content, "json", maxLength);
        case "yaml":
            return generateStructuredDataPreview(content, "yaml", maxLength);
        case "csv": {
            // For CSV, show first few rows
            const csvLines = content.split("\n").slice(0, 5);
            return generateContentPreview(csvLines.join("\n"), maxLength);
        }
        case "html": {
            // For HTML, try to extract text content or show structure
            const htmlPreview = content
                .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "") // Remove scripts
                .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, "") // Remove styles
                .replace(/<[^>]*>/g, " ") // Remove HTML tags
                .replace(/\s+/g, " ") // Normalize whitespace
                .trim();
            return generateContentPreview(htmlPreview || content, maxLength);
        }
        default:
            return generateContentPreview(content, maxLength);
    }
};
