export interface PastedTextItem {
    id: string;
    content: string;
    timestamp: number;
    // Optional metadata - set when user configures via dialog
    filename?: string;
    mimeType?: string;
    description?: string;
    isConfigured?: boolean; // true if user has opened dialog and saved settings
}

export interface PastedArtifactItem {
    id: string;
    artifactId: string;
    filename: string;
    mimeType: string;
    timestamp: number;
}

/**
 * Determines if pasted text should be treated as "large" and rendered as a badge
 * @param text - The pasted text content
 * @returns true if text is >= 2000 characters OR >= 50 lines
 */
export const isLargeText = (text: string): boolean => {
    const charCount = text.length;
    const lineCount = text.split("\n").length;
    return charCount >= 2000 || lineCount >= 50;
};

/**
 * Generates a descriptive description from pasted content
 * @param content - The pasted text content
 * @returns A description summarizing the content
 */
export const generateArtifactDescription = (content: string): string => {
    const charCount = content.length;
    const lineCount = content.split("\n").length;

    // Get a shorter preview of the content (50 chars instead of 100)
    const preview = content.substring(0, 50).replace(/\n/g, " ").trim();
    const previewText = preview.length < content.length ? `${preview}...` : preview;

    return `Pasted text (${charCount} chars, ${lineCount} lines): ${previewText}`;
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
    const singleLine = text.replace(/\n/g, " ").trim();
    return singleLine.length > maxLength ? `${singleLine.substring(0, maxLength)}...` : singleLine;
};
