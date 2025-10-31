export interface PastedTextItem {
    id: string;
    content: string;
    timestamp: number;
}

/**
 * Determines if pasted text should be treated as "large" and rendered as a badge
 * @param text - The pasted text content
 * @returns true if text is >= 300 characters OR >= 10 lines
 */
export const isLargeText = (text: string): boolean => {
    const charCount = text.length;
    const lineCount = text.split('\n').length;
    return charCount >= 300 || lineCount >= 10;
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