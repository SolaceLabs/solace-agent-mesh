import type { ArtifactInfo, FileAttachment } from "@/lib/types";

import { formatBytes } from "@/lib/utils/format";

/**
 * Checks if a filename indicates a text file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file.
 * @returns True if the file is a text-based file (case-insensitive).
 */
function isTextFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime.startsWith("text/")) {
            return true;
        }
    }
    if (!fileName) return false;

    const lowerFileName = fileName.toLowerCase();

    // Basic text files
    if (lowerFileName.endsWith(".txt") || lowerFileName.endsWith(".text")) return true;

    // Database/Query
    if (lowerFileName.endsWith(".sql")) return true;

    // Markup/Data
    if (lowerFileName.endsWith(".xml")) return true;
    if (lowerFileName.endsWith(".toml")) return true;
    if (lowerFileName.endsWith(".ini")) return true;
    if (lowerFileName.endsWith(".conf") || lowerFileName.endsWith(".config")) return true;
    if (lowerFileName.endsWith(".properties")) return true;

    // Programming Languages
    if (lowerFileName.endsWith(".py")) return true;
    if (lowerFileName.endsWith(".js") || lowerFileName.endsWith(".ts") || lowerFileName.endsWith(".jsx") || lowerFileName.endsWith(".tsx")) return true;
    if (lowerFileName.endsWith(".java")) return true;
    if (lowerFileName.endsWith(".c") || lowerFileName.endsWith(".cpp") || lowerFileName.endsWith(".h") || lowerFileName.endsWith(".hpp")) return true;
    if (lowerFileName.endsWith(".cs")) return true;
    if (lowerFileName.endsWith(".go")) return true;
    if (lowerFileName.endsWith(".rs")) return true;
    if (lowerFileName.endsWith(".rb")) return true;
    if (lowerFileName.endsWith(".php")) return true;
    if (lowerFileName.endsWith(".swift")) return true;
    if (lowerFileName.endsWith(".kt")) return true;
    if (lowerFileName.endsWith(".scala")) return true;

    // Shell/Scripts
    if (lowerFileName.endsWith(".sh")) return true;
    if (lowerFileName.endsWith(".bash")) return true;
    if (lowerFileName.endsWith(".zsh")) return true;
    if (lowerFileName.endsWith(".bat") || lowerFileName.endsWith(".cmd")) return true;
    if (lowerFileName.endsWith(".ps1")) return true;

    // Web
    if (lowerFileName.endsWith(".css")) return true;
    if (lowerFileName.endsWith(".scss") || lowerFileName.endsWith(".sass") || lowerFileName.endsWith(".less")) return true;

    // Documentation/Text
    if (lowerFileName.endsWith(".log")) return true;
    if (lowerFileName.endsWith(".env")) return true;
    if (lowerFileName.endsWith(".gitignore") || lowerFileName.endsWith(".dockerignore")) return true;
    if (lowerFileName.endsWith(".editorconfig")) return true;

    return false;
}

/**
 * Checks if a filename indicates an HTML file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file.
 * @returns True if the file extension is .html or .htm (case-insensitive).
 */
function isHtmlFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime === "text/html" || lowerMime === "application/xhtml+xml") {
            return true;
        }
    }
    if (!fileName) return false;
    return fileName.toLowerCase().endsWith(".html") || fileName.toLowerCase().endsWith(".htm");
}

/**
 * Checks if a filename indicates a Mermaid diagram file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file.
 * @returns True if the file extension is .mermaid or .mmd (case-insensitive).
 */
function isMermaidFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime === "text/x-mermaid" || lowerMime === "application/x-mermaid") {
            return true;
        }
    }
    if (!fileName) return false;
    return fileName.toLowerCase().endsWith(".mermaid") || fileName.toLowerCase().endsWith(".mmd");
}

/**
 * Checks if a filename indicates a CSV file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file (not used here, but can be extended).
 * @returns True if the file extension is .csv (case-insensitive).
 */
function isCsvFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime === "text/csv" || lowerMime === "application/csv") {
            return true;
        }
    }
    if (!fileName) return false;
    return fileName.toLowerCase().endsWith(".csv");
}

/**
 * Checks if a filename indicates an image file.
 * @param fileName The name of the file.
 * @returns True if the file extension is a common image format (case-insensitive).
 */
function isImageFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime.startsWith("image/")) {
            return true;
        }
        if (lowerMime.startsWith("text/") || lowerMime.startsWith("application/")) {
            return false;
        }
    }
    if (!fileName) return false;
    const lowerCaseFileName = fileName.toLowerCase();
    return (
        lowerCaseFileName.endsWith(".png") ||
        lowerCaseFileName.endsWith(".jpg") ||
        lowerCaseFileName.endsWith(".jpeg") ||
        lowerCaseFileName.endsWith(".gif") ||
        lowerCaseFileName.endsWith(".bmp") ||
        lowerCaseFileName.endsWith(".webp") ||
        lowerCaseFileName.endsWith(".svg")
    );
}

/**
 * Checks if a filename or MIME type indicates a JSON file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file.
 * @returns True if it's likely a JSON file.
 */
function isJsonFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime === "application/json" || lowerMime === "text/json") {
            return true;
        }
    }
    if (!fileName) return false;
    return fileName.toLowerCase().endsWith(".json");
}

/**
 * Checks if a filename or MIME type indicates a YAML file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file.
 * @returns True if it's likely a YAML file.
 */
function isYamlFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime === "application/yaml" || lowerMime === "text/yaml" || lowerMime === "application/x-yaml" || lowerMime === "text/x-yaml") {
            return true;
        }
    }
    if (!fileName) return false;
    const lowerFileName = fileName.toLowerCase();
    return lowerFileName.endsWith(".yaml") || lowerFileName.endsWith(".yml");
}

/**
 * Checks if a filename indicates a Markdown file.
 * @param fileName The name of the file.
 * @returns True if the file extension is .md or .markdown (case-insensitive).
 */
function isMarkdownFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime === "text/markdown" || lowerMime === "application/markdown" || lowerMime === "text/x-markdown") {
            return true;
        }
    }
    if (!fileName) return false;
    const lowerCaseFileName = fileName.toLowerCase();
    return lowerCaseFileName.endsWith(".md") || lowerCaseFileName.endsWith(".markdown");
}

/**
 * Checks if a filename or MIME type indicates an audio file.
 * @param fileName The name of the file.
 * @param mimeType The MIME type of the file.
 * @returns True if it's likely an audio file.
 */
function isAudioFile(fileName?: string, mimeType?: string): boolean {
    if (mimeType) {
        const lowerMime = mimeType.toLowerCase();
        if (lowerMime.startsWith("audio/")) {
            return true;
        }

        if (lowerMime.startsWith("text/") || lowerMime.startsWith("application/") || lowerMime.startsWith("image/")) {
            return false;
        }
    }
    if (!fileName) return false;
    const lowerCaseFileName = fileName.toLowerCase();
    return lowerCaseFileName.endsWith(".mp3") || lowerCaseFileName.endsWith(".wav") || lowerCaseFileName.endsWith(".ogg") || lowerCaseFileName.endsWith(".aac") || lowerCaseFileName.endsWith(".flac") || lowerCaseFileName.endsWith(".m4a");
}

/**
 * Determines the appropriate renderer type based on filename and/or MIME type.
 * Checks all available file types and returns the corresponding renderer type.
 * @param fileName The name of the file (optional).
 * @param mimeType The MIME type of the file (optional).
 * @returns The renderer type string, or null if no suitable renderer is found.
 */
export function getRenderType(fileName?: string, mimeType?: string): string | null {
    if (isHtmlFile(fileName, mimeType)) {
        return "html";
    }

    if (isMermaidFile(fileName, mimeType)) {
        return "mermaid";
    }

    if (isImageFile(fileName, mimeType)) {
        return "image";
    }

    if (isMarkdownFile(fileName, mimeType)) {
        return "markdown";
    }

    if (isAudioFile(fileName, mimeType)) {
        return "audio";
    }

    if (isJsonFile(fileName, mimeType)) {
        return "json";
    }

    if (isYamlFile(fileName, mimeType)) {
        return "yaml";
    }

    if (isCsvFile(fileName, mimeType)) {
        return "csv";
    }

    if (isTextFile(fileName, mimeType)) {
        return "text";
    }

    // No renderer found
    return null;
}

/**
 * Decodes a base64 encoded string into a UTF-8 string.
 * Attempts to use TextDecoder for proper UTF-8 handling, falls back to simple atob
 * if TextDecoder fails (e.g., for non-UTF8 binary data represented as base64).
 *
 * @param content The base64 encoded string.
 * @returns The decoded string.
 * @throws Error if base64 decoding itself fails.
 */
export function decodeBase64Content(content: string): string {
    try {
        const bytes = Uint8Array.from(atob(content), c => c.charCodeAt(0));
        return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    } catch (error) {
        console.warn("TextDecoder failed (potentially non-UTF8 data), falling back to simple atob:", error);
        // Fallback for potential binary data or non-UTF8 text
        try {
            return atob(content);
        } catch (atobError) {
            console.error("Failed to decode base64 content with atob fallback:", atobError);
            return content;
        }
    }
}

const RENDER_TYPES = ["csv", "html", "json", "mermaid", "image", "markdown", "audio", "text", "yaml"];
const RENDER_TYPES_WITH_RAW_CONTENT = ["image", "audio"];

export const getFileContent = (file: FileAttachment | null) => {
    if (!file || !file.content) {
        return "";
    }

    // Determine the renderer type based on file name and MIME type
    const renderType = getRenderType(file.name, file.mime_type);

    if (!renderType || !RENDER_TYPES.includes(renderType)) {
        return ""; // Return empty string if unsupported render type
    }

    if (RENDER_TYPES_WITH_RAW_CONTENT.includes(renderType)) {
        return file.content;
    }

    // Check if content is already plain text (from streaming)
    // @ts-expect-error - Custom property added during streaming
    if (file.isPlainText) {
        console.log("Content is plain text from streaming, returning as-is");
        return file.content;
    }

    // Otherwise, decode as base64 (from backend API)
    try {
        return decodeBase64Content(file.content);
    } catch (e) {
        console.error("Failed to decode base64 content:", e);
        return "";
    }
};

// Configuration constants
const MAX_ARTIFACT_SIZE = 5 * 1024 * 1024; // configurable limit
const MAX_ARTIFACT_SIZE_HUMAN = formatBytes(MAX_ARTIFACT_SIZE);

export function canPreviewArtifact(artifact: ArtifactInfo | null): { canPreview: boolean; reason?: string } {
    if (!artifact || !artifact.size) {
        return { canPreview: false, reason: "No artifact or content available." };
    }

    // Determine the renderer type
    const renderType = getRenderType(artifact.filename, artifact.mime_type);
    if (!renderType || !RENDER_TYPES.includes(renderType)) {
        return { canPreview: false, reason: "Preview not yet supported for this file type." };
    }

    // Check if the file size is within limits
    if (artifact.size > MAX_ARTIFACT_SIZE) {
        return {
            canPreview: false,
            reason: `Preview not supported for files this large. Maximum size is: ${MAX_ARTIFACT_SIZE_HUMAN}.`,
        };
    }

    return { canPreview: true };
}
