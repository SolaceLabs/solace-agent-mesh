import { getRenderType } from "./previewUtils";

/**
 * Utility functions for detecting and processing embedded content in message text.
 * This includes data URIs, HTML content, and Mermaid diagrams.
 */

const mimeTypeToExtension: Record<string, string> = {
    "application/pdf": "pdf",
    "application/zip": "zip",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
    "text/csv": "csv",
    "text/html": "html",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "application/json": "json",
    "application/yaml": "yaml",
    "text/yaml": "yaml",
    "application/xml": "xml",
    "text/xml": "xml",
    // Images
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/svg+xml": "svg",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/tiff": "tiff",
    // Audio
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
    "audio/aac": "aac",
    "audio/flac": "flac",
    "audio/x-m4a": "m4a",
    // Video
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/ogg": "ogv",
    // Other common types
    "application/javascript": "js",
    "application/gzip": "gz",
    "application/x-tar": "tar",
    "application/rtf": "rtf",
};

function generateFilenameFromMimeType(mimeType: string, index: number): string {
    const extension = mimeTypeToExtension[mimeType] || "bin";
    return `embedded_file_${index + 1}.${extension}`;
}

/**
 * Represents an extracted content item from a message
 */
export interface ExtractedContent {
    type: string; // The content type (image, audio, html, file)
    content: string; // The actual content (base64 data or HTML)
    mimeType?: string; // Optional MIME type for the content
    originalMatch: string; // The original matched string in the text
    filename?: string; // Optional: for downloadable files
}

/**
 * Extracts all data URIs from text and categorizes them as renderable or file.
 * @param text The text to extract from
 * @returns Array of extracted content
 */
export function extractDataUris(text: string): ExtractedContent[] {
    if (!text || typeof text !== "string") {
        return [];
    }

    const results: ExtractedContent[] = [];
    // Generic regex to capture any data URI with base64 encoding
    const dataUriRegex = /data:([a-zA-Z0-9/.-]+);base64,([A-Za-z0-9+/=]+)/g;

    let match;
    let fileCounter = 0;
    while ((match = dataUriRegex.exec(text)) !== null) {
        const [fullMatch, mimeType, base64Data] = match;

        // Check if the data URI is enclosed in quotes
        const charBefore = text[match.index - 1];
        const charAfter = text[match.index + fullMatch.length];

        if ((charBefore === '"' && charAfter === '"') || (charBefore === "'" && charAfter === "'")) {
            // It's quoted, likely part of an HTML attribute. Skip it.
            continue;
        }

        if (base64Data && base64Data.length > 10) {
            const renderType = getRenderType(undefined, mimeType);

            if (renderType) {
                // It's a directly renderable type (image, audio, mermaid, etc.)
                results.push({
                    type: renderType,
                    content: base64Data,
                    mimeType: mimeType,
                    originalMatch: fullMatch,
                });
            } else {
                // It's not directly renderable, treat as a generic file
                results.push({
                    type: "file",
                    content: base64Data,
                    mimeType: mimeType,
                    originalMatch: fullMatch,
                    // Generate a filename for download
                    filename: generateFilenameFromMimeType(mimeType, fileCounter++),
                });
            }
        }
    }

    return results;
}

/**
 * Detects if text contains HTML content
 * @param text The text to check
 * @returns True if the text contains HTML tags
 */
export function containsHtmlContent(text: string): boolean {
    if (!text || typeof text !== "string") {
        return false;
    }

    // This checks for opening and closing tags, but excludes markdown-style code blocks
    const htmlRegex = /<\/?[a-z][\s\S]*?>/i;

    // Exclude markdown code blocks that might contain HTML examples
    const isInCodeBlock = /```[\s\S]*?```|`[\s\S]*?`/g.test(text);

    return htmlRegex.test(text) && !isInCodeBlock;
}

/**
 * Processes all embedded content in text
 * @param text The text to process
 * @returns Processed text with all embedded content properly formatted for rendering
 */
export function processEmbeddedContent(text: string): string {
    if (!text || typeof text !== "string") {
        return text || "";
    }

    const processedText = text;

    // This function is now a placeholder as extraction handles rendering decisions.
    // It could be used in the future for simple replacements like markdown images,
    // but for now, we extract and render as components.

    return processedText;
}

/**
 * Detects if text contains Mermaid diagram content
 * @param text The text to check
 * @returns True if the text contains Mermaid diagram content
 */
export function containsMermaidDiagram(text: string): boolean {
    if (!text || typeof text !== "string") {
        return false;
    }

    const mermaidRegex = /```mermaid\s*\n([\s\S]*?)```/i;
    return mermaidRegex.test(text);
}

/**
 * Detects if text contains any type of embedded content
 * @param text The text to check
 * @returns True if the text contains any embedded content
 */
export function containsEmbeddedContent(text: string): boolean {
    const dataUriRegex = /data:([a-zA-Z0-9/.-]+);base64,([A-Za-z0-9+/=]+)/;
    return dataUriRegex.test(text) || containsHtmlContent(text) || containsMermaidDiagram(text);
}

/**
 * Extracts HTML content from text
 * @param text The text to extract from
 * @returns Array of extracted HTML content
 */
export function extractHtmlContent(text: string): ExtractedContent[] {
    if (!text || typeof text !== "string") {
        return [];
    }

    const results: ExtractedContent[] = [];
    const htmlRegex = /<html[\s\S]*?<\/html>/gi;

    let match;
    while ((match = htmlRegex.exec(text)) !== null) {
        // Instead of extracting the HTML content, replace it with a message
        results.push({
            type: "html",
            content: match[0].trim(), // Use the full match as content
            originalMatch: match[0],
        });
    }

    return results;
}

/**
 * Extracts Mermaid diagram content from text
 * @param text The text to extract from
 * @returns Array of extracted Mermaid diagram content
 */
export function extractMermaidDiagrams(text: string): ExtractedContent[] {
    if (!text || typeof text !== "string") {
        return [];
    }

    const results: ExtractedContent[] = [];
    const mermaidRegex = /```mermaid\s*\n([\s\S]*?)```/gi;

    let match;
    while ((match = mermaidRegex.exec(text)) !== null) {
        const [fullMatch, diagramContent] = match;

        results.push({
            type: "mermaid",
            content: diagramContent.trim(),
            originalMatch: fullMatch,
        });
    }

    return results;
}

/**
 * Extracts all embedded content from text
 * @param text The text to process
 * @returns Array of all extracted content
 */
export function extractEmbeddedContent(text: string): ExtractedContent[] {
    if (!text || typeof text !== "string") {
        return [];
    }

    return [...extractDataUris(text), ...extractHtmlContent(text), ...extractMermaidDiagrams(text)];
}
