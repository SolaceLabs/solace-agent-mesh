import type { RAGSearchResult, RAGSource } from "@/lib/types";

/**
 * Represents a citation for a specific page within a document
 */
export interface PageCitation {
    pageNumber: number;
    pageLabel: string; // e.g., "Page 3"
    citationCount: number;
    citations: RAGSource[];
}

/**
 * Represents a document with grouped page citations
 */
export interface GroupedDocument {
    filename: string;
    totalCitations: number;
    pages: PageCitation[];
    fileExtension: string;
}

/**
 * Get file extension from filename
 */
export const getFileExtension = (filename: string): string => {
    const match = filename.match(/\.([^.]+)$/);
    return match ? match[1].toLowerCase() : "file";
};

/**
 * Parse page number from location string
 * Handles formats like: "Page 3", "Pages 3-5", "Page 10", etc.
 * Returns the first/primary page number, or 0 if parsing fails
 */
export const parsePageNumber = (locationString: string | undefined): number => {
    if (!locationString) return 0;

    // Match "Page N" or "Pages N" or "Pages N-M"
    const match = locationString.match(/Pages?\s*(\d+)/i);
    if (match) {
        return parseInt(match[1], 10);
    }

    // Try to match just a number
    const numberMatch = locationString.match(/(\d+)/);
    if (numberMatch) {
        return parseInt(numberMatch[1], 10);
    }

    return 0;
};

/**
 * Groups document sources by filename and page
 * @param ragData - Array of RAGSearchResult from document_search
 * @returns Array of GroupedDocument objects sorted by filename
 */
export const groupDocumentSources = (ragData: RAGSearchResult[]): GroupedDocument[] => {
    // Filter to only document_search results
    const documentSearchResults = ragData.filter(r => r.searchType === "document_search");

    // Map to track documents by filename
    const documentMap = new Map<string, { sources: RAGSource[]; filename: string }>();

    // Collect all sources grouped by filename
    documentSearchResults.forEach(result => {
        result.sources.forEach(source => {
            const filename = source.filename || source.fileId || "Unknown";

            if (!documentMap.has(filename)) {
                documentMap.set(filename, { sources: [], filename });
            }
            documentMap.get(filename)!.sources.push(source);
        });
    });

    // Transform into GroupedDocument array
    const groupedDocuments: GroupedDocument[] = [];

    documentMap.forEach(({ sources, filename }) => {
        // Group sources by page within this document
        const pageMap = new Map<number, RAGSource[]>();

        sources.forEach(source => {
            // Use primary_location first, fall back to location_range
            const locationString = source.metadata?.primary_location || source.metadata?.location_range;
            const pageNumber = parsePageNumber(locationString);

            if (!pageMap.has(pageNumber)) {
                pageMap.set(pageNumber, []);
            }
            pageMap.get(pageNumber)!.push(source);
        });

        // Convert page map to sorted array of PageCitation
        const pages: PageCitation[] = Array.from(pageMap.entries())
            .map(([pageNumber, citations]) => ({
                pageNumber,
                pageLabel: pageNumber > 0 ? `Page ${pageNumber}` : "Unknown page",
                citationCount: citations.length,
                citations,
            }))
            .sort((a, b) => a.pageNumber - b.pageNumber);

        groupedDocuments.push({
            filename,
            totalCitations: sources.length,
            pages,
            fileExtension: getFileExtension(filename),
        });
    });

    // Sort by filename
    return groupedDocuments.sort((a, b) => a.filename.localeCompare(b.filename));
};
