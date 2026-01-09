/**
 * @file sourceUrlHelpers.ts
 * @description Unified utilities for extracting and checking URLs from RAG sources and citations.
 */

import type { RAGSource, RAGSearchResult } from "@/lib/types/fe";
import type { Citation as CitationType } from "@/lib/utils/citations";

/**
 * Supported source types for RAG and citation sources.
 */
export type SourceType = "web" | "image" | "file" | "web_search" | "deep_research" | "kb_search" | "file_search";

/**
 * Result of URL extraction from a source.
 */
export interface SourceUrlInfo {
    /** The extracted URL, or null if none found */
    url: string | null;
    /** Whether a valid URL was found */
    hasUrl: boolean;
    /** The type of the source */
    sourceType: SourceType;
}

/**
 * A union type representing source objects that can be passed to getSourceUrl.
 * Supports both RAGSource and Citation source objects.
 */
type SourceLike = RAGSource | CitationType["source"] | null | undefined;

/**
 * Extracts URL from a source object regardless of where it's stored.
 * Handles: source.sourceUrl, source.url, source.metadata.link
 *
 * Priority order: sourceUrl > url > metadata.link
 *
 * @param source - The source object to extract URL from (RAGSource or Citation source)
 * @returns SourceUrlInfo with the extracted URL and metadata
 *
 * @example
 * ```ts
 * const info = getSourceUrl(ragSource);
 * if (info.hasUrl) {
 *   window.open(info.url, '_blank');
 * }
 * ```
 */
export function getSourceUrl(source: SourceLike): SourceUrlInfo {
    if (!source) {
        return { url: null, hasUrl: false, sourceType: "web" };
    }

    // Determine source type from various possible locations
    const sourceType = (source.sourceType || source.metadata?.type || "web") as SourceType;

    // Priority order: sourceUrl > url > metadata.link
    const url = source.sourceUrl || source.url || source.metadata?.link || null;

    return {
        url,
        hasUrl: !!url,
        sourceType,
    };
}

/**
 * Check if RAG data contains any sources with valid URLs.
 * This is useful for determining whether to show a "Sources" tab or panel.
 *
 * @param ragData - Array of RAG search results to check
 * @returns true if any source has a valid URL
 *
 * @example
 * ```ts
 * const hasSourcesInSession = useMemo(() =>
 *   hasSourcesWithUrls(ragData),
 *   [ragData]
 * );
 * ```
 */
export function hasSourcesWithUrls(ragData: RAGSearchResult[] | undefined): boolean {
    if (!ragData?.length) return false;

    return ragData.some(search => search.sources?.some(source => getSourceUrl(source).hasUrl) ?? false);
}

/**
 * Get all sources with valid URLs from RAG data.
 * Useful for rendering a list of clickable sources.
 *
 * @param ragData - Array of RAG search results to filter
 * @returns Array of RAGSource objects that have valid URLs
 *
 * @example
 * ```ts
 * const sourcesWithUrls = useMemo(() =>
 *   getSourcesWithUrls(ragData ?? []),
 *   [ragData]
 * );
 * ```
 */
export function getSourcesWithUrls(ragData: RAGSearchResult[]): RAGSource[] {
    return ragData.flatMap(search => (search.sources ?? []).filter(source => getSourceUrl(source).hasUrl));
}

/**
 * Check if a source type represents a web-based source (web search or deep research).
 * These sources typically have clickable external URLs.
 *
 * @param sourceType - The source type to check
 * @returns true if the source is web-based
 */
export function isWebBasedSource(sourceType: SourceType | string | undefined): boolean {
    return sourceType === "web_search" || sourceType === "deep_research" || sourceType === "web";
}

/**
 * Check if a citation or source should open an external URL when clicked.
 * Combines source type checking with URL availability.
 *
 * @param source - The source object to check
 * @returns true if clicking should open an external URL
 */
export function hasClickableExternalUrl(source: SourceLike): boolean {
    const { hasUrl, sourceType } = getSourceUrl(source);
    return hasUrl && isWebBasedSource(sourceType);
}
