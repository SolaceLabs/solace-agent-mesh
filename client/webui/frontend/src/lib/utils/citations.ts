/**
 * Citation utilities for parsing and handling RAG source citations
 * Uses [[cite:type0]] pattern that LLMs can reliably reproduce
 * Also supports [[cite:research0]] for deep research citations
 */

import type { RAGSource, RAGSearchResult } from "@/lib/types/fe";

// Citation marker pattern: [[cite:file0]], [[cite:ref0]], [[cite:search0]], [[cite:research0]], etc.
// Also matches [[cite:0]] (treats as search citation when no type prefix)
// Also matches single bracket [cite:xxx] in case LLM uses wrong format
export const CITATION_PATTERN = /\[?\[cite:(?:(file|ref|search|research))?(\d+)\]\]?/g;
export const CLEANUP_REGEX = /\[?\[cite:[^\]]+\]\]?/g;

export interface Citation {
    marker: string;
    type: "file" | "ref" | "search" | "research";
    sourceId: number;
    position: number;
    source?: RAGSource;
}

// Re-export for convenience
export type { RAGSource, RAGSearchResult as RAGMetadata };

/**
 * Parse citation markers from text and match them to RAG metadata
 */
export function parseCitations(text: string, ragMetadata?: RAGSearchResult): Citation[] {
    const citations: Citation[] = [];
    let match;

    // Reset regex state
    CITATION_PATTERN.lastIndex = 0;

    while ((match = CITATION_PATTERN.exec(text)) !== null) {
        const [fullMatch, type, sourceId] = match;
        // If no type prefix, default to 'search' for web search citations
        const citationType = (type || "search") as "file" | "ref" | "search" | "research";
        const citation: Citation = {
            marker: fullMatch,
            type: citationType,
            sourceId: parseInt(sourceId, 10),
            position: match.index,
        };

        // Match to source metadata if available
        if (ragMetadata?.sources) {
            const citationId = `${citationType}${sourceId}`;
            citation.source = ragMetadata.sources.find((s: RAGSource) => s.citationId === citationId);

            // Debug logging to help troubleshoot citation matching
            if (!citation.source && ragMetadata.sources.length > 0) {
                console.log(
                    `Citation ${citationId} not found in sources:`,
                    ragMetadata.sources.map(s => s.citationId)
                );
            }
        }

        citations.push(citation);
    }

    return citations;
}

/**
 * Remove citation markers from text (for display without citations)
 */
export function removeCitationMarkers(text: string): string {
    return text.replace(CITATION_PATTERN, "");
}

/**
 * Split text into segments with citations
 * Returns array of {text, citation} objects
 */
export function splitTextWithCitations(text: string, citations: Citation[]): Array<{ text: string; citation?: Citation }> {
    if (citations.length === 0) {
        return [{ text }];
    }

    const segments: Array<{ text: string; citation?: Citation }> = [];
    let lastIndex = 0;

    // Sort citations by position
    const sortedCitations = [...citations].sort((a, b) => a.position - b.position);

    for (const citation of sortedCitations) {
        // Add text before citation
        if (citation.position > lastIndex) {
            segments.push({
                text: text.substring(lastIndex, citation.position),
            });
        }

        // Add citation marker (will be replaced with component)
        segments.push({
            text: citation.marker,
            citation,
        });

        lastIndex = citation.position + citation.marker.length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
        segments.push({
            text: text.substring(lastIndex),
        });
    }

    return segments;
}

/**
 * Group citations by paragraph
 * Returns array of paragraphs with their associated citations
 */
export function groupCitationsByParagraph(text: string, citations: Citation[]): Array<{ text: string; citations: Citation[] }> {
    if (citations.length === 0) {
        return [{ text, citations: [] }];
    }

    // Split text into paragraphs (by double newlines or single newlines)
    const paragraphs = text.split(/\n\n|\n/);
    const result: Array<{ text: string; citations: Citation[] }> = [];

    let currentPosition = 0;

    for (const paragraph of paragraphs) {
        const paragraphStart = currentPosition;
        const paragraphEnd = paragraphStart + paragraph.length;

        // Find citations that fall within this paragraph
        const paragraphCitations = citations.filter(citation => citation.position >= paragraphStart && citation.position < paragraphEnd);

        // Remove citation markers from paragraph text
        let cleanText = paragraph;
        for (const citation of paragraphCitations.sort((a, b) => b.position - a.position)) {
            const relativePos = citation.position - paragraphStart;
            cleanText = cleanText.substring(0, relativePos) + cleanText.substring(relativePos + citation.marker.length);
        }

        result.push({
            text: cleanText,
            citations: paragraphCitations,
        });

        // Account for the newline character(s)
        currentPosition = paragraphEnd + (text[paragraphEnd] === "\n" && text[paragraphEnd + 1] === "\n" ? 2 : 1);
    }

    return result;
}

/**
 * Get citation display number (1-indexed)
 */
export function getCitationNumber(citation: Citation): number {
    return citation.sourceId + 1;
}

/**
 * Get citation tooltip text
 */
export function getCitationTooltip(citation: Citation): string {
    // For web search citations, show the URL and title
    const isWebSearch = citation.source?.metadata?.type === "web_search" || citation.type === "search";

    if (isWebSearch && citation.source?.sourceUrl) {
        const title = citation.source.metadata?.title || citation.source.filename;
        if (title && title !== citation.source.sourceUrl) {
            return `${title}\n${citation.source.sourceUrl}`;
        }
        return citation.source.sourceUrl;
    }

    if (!citation.source) {
        return `Source ${getCitationNumber(citation)}`;
    }

    const score = (citation.source.relevanceScore * 100).toFixed(1);
    return `${citation.source.filename} (${score}% relevance)`;
}

/**
 * Get citation link URL (for kb_search with source URLs)
 */
export function getCitationLink(citation: Citation): string | undefined {
    return citation.source?.sourceUrl;
}
