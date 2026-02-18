import type { RAGSource } from "@/lib/types";

/**
 * Escapes special regex characters in a string
 */
function escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Normalizes text for better matching by collapsing whitespace
 */
function normalizeText(text: string): string {
    return text.replace(/\s+/g, " ").trim();
}

/**
 * Highlights citation text within document content.
 * Returns content with matched text wrapped in <mark> tags with citation-highlight class.
 *
 * @param content - The document content to search in
 * @param citations - Array of RAGSource objects containing contentPreview to highlight
 * @returns Content with highlighted citations wrapped in <mark class="citation-highlight">
 */
export function highlightCitationsInText(content: string, citations: RAGSource[]): string {
    if (!content || citations.length === 0) {
        return content;
    }

    // Extract unique citation texts to highlight
    const citationTexts = citations
        .map(c => c.contentPreview)
        .filter((text): text is string => !!text && text.length > 20) // Filter out short/empty previews
        .map(text => normalizeText(text));

    // Remove duplicates
    const uniqueCitationTexts = [...new Set(citationTexts)];

    if (uniqueCitationTexts.length === 0) {
        return content;
    }

    // Build a combined regex pattern for all citation texts
    // Use word boundary matching for better accuracy
    let highlightedContent = content;

    for (const citationText of uniqueCitationTexts) {
        // Try to find a match using fuzzy matching (allowing whitespace differences)
        const pattern = escapeRegex(citationText).replace(/\s+/g, "\\s+");

        try {
            const regex = new RegExp(`(${pattern})`, "gi");
            highlightedContent = highlightedContent.replace(regex, '<mark class="citation-highlight">$1</mark>');
        } catch {
            // If regex fails (e.g., too long), try exact match
            const exactIndex = highlightedContent.toLowerCase().indexOf(citationText.toLowerCase());
            if (exactIndex !== -1) {
                const originalText = highlightedContent.substring(exactIndex, exactIndex + citationText.length);
                highlightedContent = highlightedContent.substring(0, exactIndex) + `<mark class="citation-highlight">${originalText}</mark>` + highlightedContent.substring(exactIndex + citationText.length);
            }
        }
    }

    return highlightedContent;
}

/**
 * Gets the first citation preview text for display in modal header.
 * Useful for PDF previews where text can't be highlighted in the document.
 *
 * @param citations - Array of RAGSource objects
 * @returns The first non-empty content preview, truncated if needed
 */
export function getFirstCitationPreview(citations: RAGSource[]): string | null {
    const firstCitation = citations.find(c => c.contentPreview && c.contentPreview.length > 0);
    if (!firstCitation?.contentPreview) {
        return null;
    }

    const preview = firstCitation.contentPreview;
    // Truncate if too long (for display in header)
    if (preview.length > 300) {
        return preview.substring(0, 300) + "...";
    }
    return preview;
}
