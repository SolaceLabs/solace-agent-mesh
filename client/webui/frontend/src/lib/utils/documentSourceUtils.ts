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
    displayName: string; // Cleaned filename without path/session prefix
    totalCitations: number;
    pages: PageCitation[];
    fileExtension: string;
}

/**
 * Extract clean filename from file_id by removing session prefix
 * Example: "sam_dev_user_web-session-xxx_filename.pdf_v0.pdf" -> "filename.pdf"
 */
const extractDisplayName = (filename: string | undefined): string => {
    if (!filename) return "Unknown";

    // The pattern is: sam_dev_user_web-session-{uuid}_{actual_filename}_v{version}.pdf
    // We need to extract just the {actual_filename}.pdf part

    // First, remove the .pdf extension at the very end (added by backend)
    let cleaned = filename.replace(/\.pdf$/, "");

    // Remove the version suffix (_v0, _v1, etc.)
    cleaned = cleaned.replace(/_v\d+$/, "");

    // Now we have: sam_dev_user_web-session-{uuid}_{actual_filename}
    // Find the pattern "web-session-{uuid}_" and remove everything before and including it
    const sessionPattern = /^.*web-session-[a-f0-9-]+_/;
    cleaned = cleaned.replace(sessionPattern, "");

    // If no session pattern found, just use the filename as-is
    if (cleaned === filename.replace(/\.pdf$/, "").replace(/_v\d+$/, "")) {
        // No transformation happened, use original filename
        return filename;
    }

    // Add back the .pdf extension
    return cleaned + ".pdf";
};

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
            displayName: extractDisplayName(filename),
            totalCitations: sources.length,
            pages,
            fileExtension: getFileExtension(filename),
        });
    });

    // Sort by filename
    return groupedDocuments.sort((a, b) => a.displayName.localeCompare(b.displayName));
};

/**
 * Check if RAGSearchResult array contains any document_search results
 */
export const hasDocumentSources = (ragData: RAGSearchResult[] | null): boolean => {
    if (!ragData || ragData.length === 0) return false;
    return ragData.some(r => r.searchType === "document_search");
};
