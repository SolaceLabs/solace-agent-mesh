/**
 * Citation utilities for parsing and handling RAG source citations
 * Uses [[cite:type0]] pattern that LLMs can reliably reproduce
 * Also supports [[cite:research0]] for deep research citations
 */

import type { RAGSource, RAGSearchResult } from "@/lib/types/fe";

// Re-export getCleanDomain for backward compatibility
export { getCleanDomain } from "./url";

// Citation marker pattern: [[cite:file0]], [[cite:ref0]], [[cite:search0]], [[cite:research0]], etc.
// Also matches [[cite:0]] (treats as search citation when no type prefix)
// Also matches single bracket [cite:xxx] in case LLM uses wrong format
export const CITATION_PATTERN = /\[?\[cite:(?:(file|ref|search|research))?(\d+)\]\]?/g;

// Pattern for comma-separated citations like [[cite:search3, search4]] or [[cite:search3, search4, search5]]
// Also handles LLM-generated format with repeated cite: prefix like [[cite:research0, cite:research1, cite:research2]]
// This matches the entire bracket group with comma-separated values
export const MULTI_CITATION_PATTERN = /\[?\[cite:((?:(?:file|ref|search|research)?\d+)(?:\s*,\s*(?:cite:)?(?:file|ref|search|research)?\d+)+)\]\]?/g;

// Pattern to extract individual citations from a comma-separated list
// Handles both formats: "research0, research1" and "research0, cite:research1, cite:research2"
export const INDIVIDUAL_CITATION_PATTERN = /(?:cite:)?(file|ref|search|research)?(\d+)/g;

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
 * Parse individual citations from a comma-separated list like "search3, search4, search5"
 */
function parseMultiCitationContent(content: string, position: number, fullMatch: string, ragMetadata?: RAGSearchResult): Citation[] {
    const citations: Citation[] = [];
    let individualMatch;

    // Reset regex state
    INDIVIDUAL_CITATION_PATTERN.lastIndex = 0;

    while ((individualMatch = INDIVIDUAL_CITATION_PATTERN.exec(content)) !== null) {
        const [, type, sourceId] = individualMatch;
        // If no type prefix, default to 'search' for web search citations
        const citationType = (type || "search") as "file" | "ref" | "search" | "research";
        const citation: Citation = {
            marker: fullMatch, // Use the full multi-citation marker
            type: citationType,
            sourceId: parseInt(sourceId, 10),
            position: position,
        };

        // Match to source metadata if available
        if (ragMetadata?.sources) {
            const citationId = `${citationType}${sourceId}`;
            citation.source = ragMetadata.sources.find((s: RAGSource) => s.citationId === citationId);
        }

        citations.push(citation);
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
        if (afterMatch.match(/^\s*,\s*(?:file|ref|search|research)?\d+/)) {
            continue;
        }

        // If there's a comma before and we're still inside brackets, skip
        if (beforeMatch.match(/\[?\[cite:[^\]]*,\s*$/)) {
            continue;
        }

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
