export interface PastedTextItem {
    id: string;
    content: string;
    timestamp: number;
}

export interface PastedArtifactItem {
    id: string;
    artifactId: string;
    filename: string;
    timestamp: number;
}

/**
 * Determines if pasted text should be treated as "large" and rendered as a badge
 * @param text - The pasted text content
 * @returns true if text is >= 1000 characters OR >= 30 lines
 */
export const isLargeText = (text: string): boolean => {
    const charCount = text.length;
    const lineCount = text.split('\n').length;
    return charCount >= 1000 || lineCount >= 30;
};


/**
 * Generates a descriptive title from pasted content
 * @param content - The pasted text content
 * @returns A descriptive filename with appropriate extension
 */
export const generateArtifactTitle = (content: string): string => {
    // Detect file type
    const mimeType = detectContentType(content);
    const extension = getExtensionFromMimeType(mimeType);
    
    // Try to extract a meaningful name from the first line
    const firstLine = content.split('\n')[0].trim();
    let baseName = 'pasted-content';
    
    if (firstLine.length > 0 && firstLine.length <= 50) {
        // Use first line as base name if it's reasonable
        baseName = firstLine
            .replace(/[^a-zA-Z0-9-_\s]/g, '') // Remove special chars
            .replace(/\s+/g, '-') // Replace spaces with hyphens
            .toLowerCase()
            .substring(0, 30); // Limit length
        
        if (baseName.length < 3) {
            baseName = 'pasted-content';
        }
    }
    
    return `${baseName}.${extension}`;
};

/**
 * Generates a descriptive description from pasted content
 * @param content - The pasted text content
 * @returns A description summarizing the content
 */
export const generateArtifactDescription = (content: string): string => {
    const charCount = content.length;
    const lineCount = content.split('\n').length;
    const contentType = detectContentType(content);
    
    // Get a shorter preview of the content (50 chars instead of 100)
    const preview = content.substring(0, 50).replace(/\n/g, ' ').trim();
    const previewText = preview.length < content.length ? `${preview}...` : preview;
    
    const typeLabel = getTypeLabel(contentType);
    
    return `Pasted ${typeLabel} (${charCount} chars, ${lineCount} lines): ${previewText}`;
};

/**
 * Detects the content type from text
 */
const detectContentType = (content: string): string => {
    if (content.includes('def ') || content.includes('import ') && content.includes('from ')) {
        return 'text/python';
    }
    if (content.includes('function ') || content.includes('const ') || content.includes('let ') || content.includes('=>')) {
        return 'text/javascript';
    }
    if (content.includes('interface ') || content.includes('type ') && content.includes(':')) {
        return 'text/typescript';
    }
    if (content.includes('<!DOCTYPE') || content.includes('<html')) {
        return 'text/html';
    }
    if (content.includes('{') && content.includes('}') && content.includes(':')) {
        try {
            JSON.parse(content);
            return 'application/json';
        } catch {
            // Not valid JSON
        }
    }
    if (content.includes('---') && (content.includes('apiVersion:') || content.includes('kind:'))) {
        return 'text/yaml';
    }
    if (content.includes('<?xml') || content.includes('<') && content.includes('/>')) {
        return 'text/xml';
    }
    if (content.includes('#') && (content.includes('##') || content.includes('```'))) {
        return 'text/markdown';
    }
    return 'text/plain';
};

/**
 * Gets file extension from MIME type
 */
const getExtensionFromMimeType = (mimeType: string): string => {
    const extensionMap: Record<string, string> = {
        'text/plain': 'txt',
        'text/markdown': 'md',
        'application/json': 'json',
        'text/html': 'html',
        'text/css': 'css',
        'text/javascript': 'js',
        'text/typescript': 'ts',
        'text/python': 'py',
        'text/yaml': 'yaml',
        'text/xml': 'xml',
    };
    return extensionMap[mimeType] || 'txt';
};

/**
 * Gets human-readable type label
 */
const getTypeLabel = (mimeType: string): string => {
    const labelMap: Record<string, string> = {
        'text/plain': 'text',
        'text/markdown': 'Markdown',
        'application/json': 'JSON',
        'text/html': 'HTML',
        'text/css': 'CSS',
        'text/javascript': 'JavaScript',
        'text/typescript': 'TypeScript',
        'text/python': 'Python code',
        'text/yaml': 'YAML',
        'text/xml': 'XML',
    };
    return labelMap[mimeType] || 'text';
};

/**
 * Creates a new PastedTextItem with unique ID and timestamp
 * @param content - The pasted text content
 * @returns A new PastedTextItem object
 */
export const createPastedTextItem = (content: string): PastedTextItem => ({
    id: `paste-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
    content,
    timestamp: Date.now(),
});

/**
 * Gets a preview of the pasted text for display in badge tooltip
 * @param text - The full text content
 * @param maxLength - Maximum length of preview (default: 50)
 * @returns Truncated text with ellipsis if needed
 */
export const getTextPreview = (text: string, maxLength: number = 50): string => {
    const singleLine = text.replace(/\n/g, ' ').trim();
    return singleLine.length > maxLength 
        ? `${singleLine.substring(0, maxLength)}...` 
        : singleLine;
};