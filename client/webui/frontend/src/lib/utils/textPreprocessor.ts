/**
 * Processes text content to convert base64 image data URLs to markdown image syntax
 * @param text - The raw text content that may contain base64 image data URLs
 * @returns Processed text with base64 images converted to markdown image syntax
 */
export function processImagesInText(text: string): string {
    if (!text || typeof text !== "string") {
        return text || "";
    }

    // Regex pattern to match base64 image data URLs
    // Matches: data:image/[format];base64,[base64-data]
    // Supports common image formats: png, jpeg, jpg, gif, webp, svg+xml, bmp, ico
    const base64ImageRegex = /data:image\/(png|jpeg|jpg|gif|webp|svg\+xml|bmp|ico);base64,([A-Za-z0-9+/=]+)/g;

    let imageCounter = 1;

    // Replace each base64 image data URL with markdown image syntax
    const processedText = text.replace(base64ImageRegex, (match, _imageFormat, base64Data) => {
        // Validate that we have actual base64 data
        if (!base64Data || base64Data.length < 10) {
            return match; // Return original if data seems invalid
        }

        // Create markdown image syntax with the original data URL
        const altText = `Image ${imageCounter}`;
        const markdownImage = `![${altText}](${match})`;

        imageCounter++;
        return markdownImage;
    });

    return processedText;
}

/**
 * Checks if the given text contains any base64 image data URLs
 * @param text - The text to check
 * @returns True if the text contains base64 image data URLs, false otherwise
 */
export function containsBase64Images(text: string): boolean {
    if (!text || typeof text !== "string") {
        return false;
    }

    const base64ImageRegex = /data:image\/(png|jpeg|jpg|gif|webp|svg\+xml|bmp|ico);base64,([A-Za-z0-9+/=]+)/;
    return base64ImageRegex.test(text);
}

/**
 * Extracts all base64 image data URLs from the given text
 * @param text - The text to extract images from
 * @returns Array of objects containing image information
 */
export function extractBase64Images(text: string): Array<{
    dataUrl: string;
    format: string;
    base64Data: string;
    position: number;
}> {
    if (!text || typeof text !== "string") {
        return [];
    }

    const base64ImageRegex = /data:image\/(png|jpeg|jpg|gif|webp|svg\+xml|bmp|ico);base64,([A-Za-z0-9+/=]+)/g;
    const images: Array<{
        dataUrl: string;
        format: string;
        base64Data: string;
        position: number;
    }> = [];

    let match;
    while ((match = base64ImageRegex.exec(text)) !== null) {
        images.push({
            dataUrl: match[0],
            format: match[1],
            base64Data: match[2],
            position: match.index,
        });
    }

    return images;
}
