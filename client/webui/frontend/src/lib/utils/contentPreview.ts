import { getRenderType } from "@/lib/components/chat/preview/previewUtils";

/**
 * Generates content preview text specifically for file icon display
 */
export const generateIconContentPreview = (content: string, filename?: string, mimeType?: string, maxLength: number = 150): string => {
    if (!content || typeof content !== "string") {
        return "";
    }
    
    const renderType = getRenderType(filename, mimeType);
    
    switch (renderType) {
        case "json":
            return generateJsonIconPreview(content, maxLength);
        case "yaml":
            return generateYamlIconPreview(content, maxLength);
        case "csv":
            return generateCsvIconPreview(content, maxLength);
        case "html":
            return generateHtmlIconPreview(content, maxLength);
        case "markdown":
            return generateMarkdownIconPreview(content, maxLength);
        default:
            return generateTextIconPreview(content, maxLength);
    }
};

/**
 * Generates JSON preview for file icons
 */
export const generateJsonIconPreview = (content: string, maxLength: number = 150): string => {
    try {
        const parsed = JSON.parse(content);
        if (typeof parsed === "object" && parsed !== null) {
            const keys = Object.keys(parsed).slice(0, 6); // Show up to 6 keys for icons
            const preview = keys.map(key => {
                const value = parsed[key];
                if (typeof value === "string") {
                    const truncatedValue = value.length > 15 ? value.substring(0, 15) + '...' : value;
                    return `"${key}": "${truncatedValue}"`;
                } else if (typeof value === "number" || typeof value === "boolean") {
                    return `"${key}": ${value}`;
                } else if (Array.isArray(value)) {
                    return `"${key}": [${value.length}]`;
                } else if (typeof value === "object" && value !== null) {
                    return `"${key}": {...}`;
                }
                return `"${key}": ${typeof value}`;
            }).join('\n');
            
            const result = `{\n${preview}\n}`;
            return result.length > maxLength ? result.substring(0, maxLength) + '...' : result;
        }
        return content.substring(0, maxLength);
    } catch (error) {
        return content.substring(0, maxLength);
    }
};

/**
 * Generates YAML preview for file icons
 */
export const generateYamlIconPreview = (content: string, maxLength: number = 150): string => {
    const lines = content.split('\n').slice(0, 8);
    const meaningfulLines = lines.filter(line => {
        const trimmed = line.trim();
        return trimmed && 
               !trimmed.startsWith('#') && 
               (trimmed.includes(':') || trimmed.startsWith('-'));
    }).slice(0, 6);
    
    const result = meaningfulLines.join('\n');
    return result.length > maxLength ? result.substring(0, maxLength) + '...' : result;
};

/**
 * Generates CSV preview for file icons
 */
export const generateCsvIconPreview = (content: string, maxLength: number = 150): string => {
    const lines = content.split('\n').slice(0, 5);
    const preview = lines.map(line => {
        // Truncate very long lines for icon display
        return line.length > 40 ? line.substring(0, 40) + '...' : line;
    }).join('\n');
    
    return preview.length > maxLength ? preview.substring(0, maxLength) + '...' : preview;
};

/**
 * Generates HTML preview for file icons
 */
export const generateHtmlIconPreview = (content: string, maxLength: number = 150): string => {
    // Try to extract meaningful HTML structure for icon display
    const structuralTags = content.match(/<(html|head|body|div|section|article|header|footer|nav|main|aside|h[1-6]|p)[^>]*>/gi);
    
    if (structuralTags && structuralTags.length > 0) {
        const preview = structuralTags.slice(0, 6).join('\n');
        return preview.length > maxLength ? preview.substring(0, maxLength) + '...' : preview;
    }
    
    // Fallback to text extraction
    const textContent = content
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
        .replace(/<[^>]*>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    
    return textContent.length > maxLength ? textContent.substring(0, maxLength) + '...' : textContent;
};

/**
 * Generates Markdown preview for file icons
 */
export const generateMarkdownIconPreview = (content: string, maxLength: number = 150): string => {
    const lines = content.split('\n').slice(0, 8);
    const meaningfulLines = lines.filter(line => {
        const trimmed = line.trim();
        return trimmed && !trimmed.startsWith('<!--');
    }).slice(0, 5);
    
    const result = meaningfulLines.join('\n');
    return result.length > maxLength ? result.substring(0, maxLength) + '...' : result;
};

/**
 * Generates plain text preview for file icons
 */
export const generateTextIconPreview = (content: string, maxLength: number = 150): string => {
    // For plain text, preserve some line structure but keep it concise
    const lines = content.split('\n').slice(0, 6);
    const result = lines.join('\n');
    return result.length > maxLength ? result.substring(0, maxLength) + '...' : result;
};

/**
 * Cleans and normalizes content for icon preview display
 */
export const cleanContentForIconPreview = (content: string): string => {
    if (!content || typeof content !== "string") {
        return "";
    }
    
    return content
        .replace(/\r\n/g, '\n') // Normalize line endings
        .replace(/\n{3,}/g, '\n\n') // Limit consecutive newlines
        .replace(/[ \t]{3,}/g, '  ') // Limit consecutive spaces/tabs
        .trim();
};

/**
 * Generates a fallback preview for binary or unsupported files
 */
export const generateBinaryFilePreview = (filename: string, mimeType?: string, size?: number): string => {
    const extension = filename.split('.').pop()?.toUpperCase() || 'FILE';
    const sizeText = size ? `${Math.round(size / 1024)}KB` : '';
    const typeText = mimeType ? mimeType.split('/')[0].toUpperCase() : 'BINARY';
    
    return [
        `${extension} File`,
        typeText,
        sizeText
    ].filter(Boolean).join('\n');
};
