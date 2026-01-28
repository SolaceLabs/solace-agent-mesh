/**
 * Citation utilities for parsing and handling RAG source citations
 *
 * Citation format: [[cite:s{turn}r{index}]] where:
 * - turn = search turn number (0, 1, 2, ...)
 * - index = result index within that search (0, 1, 2, ...)
 *
 * Examples: [[cite:s0r0]], [[cite:s0r1]], [[cite:s1r0]], [[cite:s1r2]]
 *
 * Also supports [[cite:research0]] for deep research tool citations
 */

import type { RAGSource, RAGSearchResult } from "@/lib/types/fe";

// Re-export getCleanDomain for backward compatibility
export { getCleanDomain } from "./url";

// Citation marker pattern for the sTrN format: [[cite:s0r0]], [[cite:s1r2]], etc.
// Also supports single bracket [cite:xxx] in case LLM uses wrong format
// Also supports [[cite:research0]] for deep research
export const CITATION_PATTERN = /\[?\[cite:(s\d+r\d+|research\d+)\]\]?/g;

// Pattern for comma-separated citations like [[cite:s0r0, s0r1, s0r2]]
// Also handles LLM-generated format with repeated cite: prefix
export const MULTI_CITATION_PATTERN = /\[?\[cite:((?:s\d+r\d+|research\d+)(?:\s*,\s*(?:cite:)?(?:s\d+r\d+|research\d+))+)\]\]?/g;

// Pattern to extract individual citations from a comma-separated list
export const INDIVIDUAL_CITATION_PATTERN = /(?:cite:)?(s\d+r\d+|research\d+)/g;

export const CLEANUP_REGEX = /\[?\[cite:[^\]]+\]\]?/g;

export interface Citation {
    marker: string;
    type: "search" | "research";
    sourceId: number;
    position: number;
    source?: RAGSource;
    citationId: string; // The full citation ID like "s0r0" or "research0"
}

// Re-export for convenience
export type { RAGSource, RAGSearchResult as RAGMetadata };

/**
 * Parse a citation ID and return its components
 * Handles both formats:
 * - s{turn}r{index} (e.g., "s0r0", "s1r2") -> type: "search"
 * - research{N} (e.g., "research0") -> type: "research"
 */
// Regex patterns for parsing citation IDs
const SEARCH_CITATION_ID_PATTERN = /^s(\d+)r(\d+)$/;
const RESEARCH_CITATION_ID_PATTERN = /^research(\d+)$/;

function parseCitationId(citationId: string): { type: "search" | "research"; sourceId: number } | null {
    // Try sTrN format first
    const searchMatch = citationId.match(SEARCH_CITATION_ID_PATTERN);
    if (searchMatch) {
        return {
            type: "search",
            sourceId: parseInt(searchMatch[2], 10), // Use result index as sourceId
        };
    }

    // Try research format
    const researchMatch = citationId.match(RESEARCH_CITATION_ID_PATTERN);
    if (researchMatch) {
        return {
            type: "research",
            sourceId: parseInt(researchMatch[1], 10),
        };
    }

    return null;
}

/**
 * Parse individual citations from a comma-separated list like "s0r0, s0r1, s0r2"
 */
function parseMultiCitationContent(content: string, position: number, fullMatch: string, ragMetadata?: RAGSearchResult): Citation[] {
    const citations: Citation[] = [];
    let individualMatch;

    // Reset regex state
    INDIVIDUAL_CITATION_PATTERN.lastIndex = 0;

    while ((individualMatch = INDIVIDUAL_CITATION_PATTERN.exec(content)) !== null) {
        const citationId = individualMatch[1]; // The captured citation ID (s0r0 or research0)
        const parsed = parseCitationId(citationId);

        if (parsed) {
            const citation: Citation = {
                marker: fullMatch,
                type: parsed.type,
                sourceId: parsed.sourceId,
                position: position,
                citationId: citationId,
            };

            // Match to source metadata using the full citation ID
            if (ragMetadata?.sources) {
                citation.source = ragMetadata.sources.find((s: RAGSource) => s.citationId === citationId);
            }

            citations.push(citation);
        }
    }

    return citations;
}

/**
 * Parse citation markers from text and match them to RAG metadata
 */
export function parseCitations(text: string, ragMetadata?: RAGSearchResult): Citation[] {
    const citations: Citation[] = [];
    const processedPositions = new Set<number>();
    let match;

    // First, handle multi-citation patterns like [[cite:search3, search4]]
    MULTI_CITATION_PATTERN.lastIndex = 0;
    while ((match = MULTI_CITATION_PATTERN.exec(text)) !== null) {
        const [fullMatch, content] = match;
        const multiCitations = parseMultiCitationContent(content, match.index, fullMatch, ragMetadata);
        citations.push(...multiCitations);
        processedPositions.add(match.index);
    }

    // Then handle single citation patterns
    CITATION_PATTERN.lastIndex = 0;

    while ((match = CITATION_PATTERN.exec(text)) !== null) {
        // Skip if this position was already processed as part of a multi-citation
        if (processedPositions.has(match.index)) {
            continue;
        }

        // Check if this single citation is part of a multi-citation pattern
        // by looking for comma after it within brackets
        const afterMatch = text.substring(match.index + match[0].length);
        const beforeMatch = text.substring(0, match.index);

        // If there's a comma immediately after (within the same bracket), skip it
        // as it will be handled by the multi-citation pattern
        if (afterMatch.match(/^\s*,\s*(?:s\d+r\d+|research\d+)/)) {
            continue;
        }

        // If there's a comma before and we're still inside brackets, skip
        if (beforeMatch.match(/\[?\[cite:[^\]]*,\s*$/)) {
            continue;
        }

        const [fullMatch, citationId] = match;
        const parsed = parseCitationId(citationId);

        if (parsed) {
            const citation: Citation = {
                marker: fullMatch,
                type: parsed.type,
                sourceId: parsed.sourceId,
                position: match.index,
                citationId: citationId,
            };

            // Match to source metadata using the full citation ID
            if (ragMetadata?.sources) {
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
    }

    // Sort by position to maintain order
    citations.sort((a, b) => a.position - b.position);

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
    // For web search and deep research citations, show the URL and title
    const isWebSearch = citation.source?.metadata?.type === "web_search" || citation.type === "search";
    const isDeepResearch = citation.source?.metadata?.type === "deep_research" || citation.type === "research";
    const sourceUrl = citation.source?.sourceUrl || citation.source?.url || citation.source?.metadata?.link;

    if ((isWebSearch || isDeepResearch) && sourceUrl) {
        const title = citation.source?.metadata?.title || citation.source?.filename;
        if (title && title !== sourceUrl) {
            return `${title}\n${sourceUrl}`;
        }
        return sourceUrl;
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
