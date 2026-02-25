import type { RAGSearchResult, RAGSource } from "@/lib/types";

export interface LocationCitation {
    sortKey: number; // Numeric key for sorting (page number for pages, 0 for others)
    locationLabel: string; // e.g., "Page 3", "Lines 1-50", "Paragraph 5", "Slide 3"
    citationCount: number;
    citations: RAGSource[];
}

export interface GroupedDocument {
    filename: string;
    totalCitations: number;
    locations: LocationCitation[];
    fileExtension: string;
}

export const getFileExtension = (filename: string): string => {
    const match = filename.match(/\.([^.]+)$/);
    return match ? match[1].toLowerCase() : "file";
};

/**
 * Format location label for display
 * Central function for formatting all location types (lines, pages, paragraphs, slides)
 *
 * Transformations:
 * - Line ranges: "Lines 1_50" → "Lines 1-50" (underscore to dash)
 * - Pages: preserved as-is (e.g., "Page 3", "Pages 3-5")
 * - Paragraphs: preserved as-is (e.g., "Paragraph 5")
 * - Slides: preserved as-is (e.g., "Slide 3")
 * - Unknown: preserved as-is
 *
 * @param locationString - Raw location string from backend
 * @returns Formatted location string for UI display
 */
export const formatLocationLabel = (locationString: string): string => {
    if (!locationString) return locationString;

    // Line ranges: Replace underscores with dashes (Lines 1_50 -> Lines 1-50)
    if (locationString.startsWith("Lines ")) {
        return locationString.replace(/Lines (\d+)_(\d+)/g, "Lines $1-$2");
    }

    // Pages: No transformation needed (already formatted: "Page 3", "Pages 3-5")
    if (locationString.startsWith("Page")) {
        return locationString;
    }

    // Paragraphs: No transformation needed (already formatted: "Paragraph 5")
    if (locationString.startsWith("Paragraph")) {
        return locationString;
    }

    // Slides: No transformation needed (already formatted: "Slide 3")
    if (locationString.startsWith("Slide")) {
        return locationString;
    }

    // Unknown format: return as-is
    return locationString;
};

/**
 * Extract numeric sorting key from location string
 * Used for sorting locations within a document (pages are sorted numerically)
 *
 * Returns the first page number for page-based locations, or 0 for other types
 * (line ranges, paragraphs, slides are kept in their natural order with sortKey=0)
 *
 * @param locationString - Location string (e.g., "Page 3", "Lines 1-50")
 * @returns Numeric sorting key (page number for pages, 0 for non-page locations)
 */
export const parseSortKey = (locationString: string | undefined): number => {
    if (!locationString) return 0;

    const match = locationString.match(/^Pages?\s*(\d+)/i);
    if (match) {
        return parseInt(match[1], 10);
    }

    return 0;
};

/**
 * Groups document sources by filename and location
 * Preserves backend location formats (pages, lines, paragraphs, slides)
 * @param ragData - Array of RAGSearchResult from document_search
 * @returns Array of GroupedDocument objects sorted by filename
 */
export const groupDocumentSources = (ragData: RAGSearchResult[]): GroupedDocument[] => {
    const documentSearchResults = ragData.filter(r => r.searchType === "document_search");

    const documentMap = new Map<string, { sources: RAGSource[]; filename: string }>();

    documentSearchResults.forEach(result => {
        result.sources.forEach(source => {
            const filename = source.filename || source.fileId || "Unknown";

            if (!documentMap.has(filename)) {
                documentMap.set(filename, { sources: [], filename });
            }
            documentMap.get(filename)!.sources.push(source);
        });
    });

    const groupedDocuments: GroupedDocument[] = [];

    documentMap.forEach(({ sources, filename }) => {
        const locationMap = new Map<string, RAGSource[]>();

        sources.forEach(source => {
            const locationString = source.metadata?.primary_location || source.metadata?.location_range || "Unknown";

            if (!locationMap.has(locationString)) {
                locationMap.set(locationString, []);
            }
            locationMap.get(locationString)!.push(source);
        });

        const locations: LocationCitation[] = Array.from(locationMap.entries())
            .map(([locationString, citations]) => {
                const sortKey = parseSortKey(locationString);
                return {
                    sortKey,
                    locationLabel: formatLocationLabel(locationString),
                    citationCount: citations.length,
                    citations,
                };
            })
            .sort((a, b) => a.sortKey - b.sortKey);

        groupedDocuments.push({
            filename,
            totalCitations: sources.length,
            locations,
            fileExtension: getFileExtension(filename),
        });
    });

    return groupedDocuments.sort((a, b) => a.filename.localeCompare(b.filename));
};
