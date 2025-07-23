/**
 * Utility functions for detecting and processing embedded content in message text.
 * This includes base64 encoded images, HTML content, audio data, Mermaid diagrams, and CSV content.
 */

// Constants for content type detection
const SUPPORTED_IMAGE_FORMATS = ["png", "jpeg", "jpg", "gif", "webp", "svg+xml", "bmp", "ico"];
const SUPPORTED_AUDIO_FORMATS = ["mp3", "wav", "ogg", "aac", "flac", "m4a"];

/**
 * Represents an extracted content item from a message
 */
export interface ExtractedContent {
    type: string; // The content type (image, audio, html)
    content: string; // The actual content (base64 data or HTML)
    mimeType?: string; // Optional MIME type for the content
    originalMatch: string; // The original matched string in the text
}

/**
 * Detects if text contains base64 encoded image data
 * @param text The text to check
 * @returns True if the text contains base64 image data
 */
export function containsBase64Images(text: string): boolean {
    if (!text || typeof text !== "string") {
        return false;
    }

    const base64ImageRegex = new RegExp(`data:image/(${SUPPORTED_IMAGE_FORMATS.join("|")});base64,[A-Za-z0-9+/=]+`, "i");
    return base64ImageRegex.test(text);
}

/**
 * Detects if text contains base64 encoded audio data
 * @param text The text to check
 * @returns True if the text contains base64 audio data
 */
export function containsBase64Audio(text: string): boolean {
    if (!text || typeof text !== "string") {
        return false;
    }

    const base64AudioRegex = new RegExp(`data:audio/(${SUPPORTED_AUDIO_FORMATS.join("|")});base64,[A-Za-z0-9+/=]+`, "i");
    return base64AudioRegex.test(text);
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
 * Processes base64 image data in text to markdown image syntax
 * @param text The text containing base64 image data
 * @returns Processed text with base64 images converted to markdown image syntax
 */
export function processBase64Images(text: string): string {
    if (!text || typeof text !== "string") {
        return text || "";
    }

    const base64ImageRegex = new RegExp(`data:image/(${SUPPORTED_IMAGE_FORMATS.join("|")});base64,([A-Za-z0-9+/=]+)`, "g");

    let imageCounter = 1;

    return text.replace(base64ImageRegex, (match, _format, base64Data) => {
        // Validate that we have actual base64 data
        if (!base64Data || base64Data.length < 10) {
            return match;
        }

        // Create markdown image syntax with the original data URL
        const altText = `Image ${imageCounter}`;
        const markdownImage = `![${altText}](${match})`;

        imageCounter++;
        return markdownImage;
    });
}

/**
 * Processes base64 audio data in text to audio element syntax
 * @param text The text containing base64 audio data
 * @returns Processed text with base64 audio converted to audio elements
 */
export function processBase64Audio(text: string): string {
    if (!text || typeof text !== "string") {
        return text || "";
    }

    const base64AudioRegex = new RegExp(`data:audio/(${SUPPORTED_AUDIO_FORMATS.join("|")});base64,([A-Za-z0-9+/=]+)`, "g");

    let audioCounter = 1;

    return text.replace(base64AudioRegex, (match, _format, base64Data) => {
        // Validate that we have actual base64 data
        if (!base64Data || base64Data.length < 10) {
            return match;
        }

        const audioElement = `<audio controls src="${match}">Audio ${audioCounter}</audio>`;

        audioCounter++;
        return audioElement;
    });
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

    let processedText = text;

    if (containsBase64Images(processedText)) {
        processedText = processBase64Images(processedText);
    }

    if (containsBase64Audio(processedText)) {
        processedText = processBase64Audio(processedText);
    }

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
    return containsBase64Images(text) || containsBase64Audio(text) || containsHtmlContent(text) || containsMermaidDiagram(text);
}

/**
 * Extracts base64 image data from text
 * @param text The text to extract from
 * @returns Array of extracted image content
 */
export function extractBase64Images(text: string): ExtractedContent[] {
    if (!text || typeof text !== "string") {
        return [];
    }

    const results: ExtractedContent[] = [];
    const base64ImageRegex = new RegExp(`data:image/(${SUPPORTED_IMAGE_FORMATS.join("|")});base64,([A-Za-z0-9+/=]+)`, "g");

    let match;
    while ((match = base64ImageRegex.exec(text)) !== null) {
        const [fullMatch, format, base64Data] = match;

        // Validate that we have actual base64 data
        if (base64Data && base64Data.length > 10) {
            results.push({
                type: "image",
                content: base64Data,
                mimeType: `image/${format}`,
                originalMatch: fullMatch,
            });
        }
    }

    return results;
}

/**
 * Extracts base64 audio data from text
 * @param text The text to extract from
 * @returns Array of extracted audio content
 */
export function extractBase64Audio(text: string): ExtractedContent[] {
    if (!text || typeof text !== "string") {
        return [];
    }

    const results: ExtractedContent[] = [];
    const base64AudioRegex = new RegExp(`data:audio/(${SUPPORTED_AUDIO_FORMATS.join("|")});base64,([A-Za-z0-9+/=]+)`, "g");

    let match;
    while ((match = base64AudioRegex.exec(text)) !== null) {
        const [fullMatch, format, base64Data] = match;

        // Validate that we have actual base64 data
        if (base64Data && base64Data.length > 10) {
            results.push({
                type: "audio",
                content: base64Data,
                mimeType: `audio/${format}`,
                originalMatch: fullMatch,
            });
        }
    }

    return results;
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

    return [...extractBase64Images(text), ...extractBase64Audio(text), ...extractHtmlContent(text), ...extractMermaidDiagrams(text)];
}
