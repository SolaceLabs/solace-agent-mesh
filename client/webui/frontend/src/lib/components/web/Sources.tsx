/**
 * Sources Display Component
 */

import { useMemo } from "react";
import { StackedFavicons } from "./StackedFavicons";
import type { RAGSource } from "@/lib/types/fe";

interface SearchSource {
    link: string;
    title?: string;
    snippet?: string;
    attribution?: string;
    processed?: boolean;
    source_type?: string;
}

/**
 * Main Sources Component
 * Displays search results as stacked favicons button
 */
interface SourcesProps {
    messageId?: string;
    taskId?: string;
    isDeepResearch?: boolean;
    onDeepResearchClick?: () => void;
}

export function Sources({ ragMetadata, isDeepResearch = false, onDeepResearchClick }: SourcesProps & { ragMetadata?: { sources?: RAGSource[] } }) {
    // Process all sources including images (use source page link for images, not the image URL)
    const webSources = useMemo(() => {
        if (!ragMetadata?.sources) {
            return [];
        }

        const sources: SearchSource[] = [];
        const seenSources = new Set<string>();

        ragMetadata.sources.forEach((s: RAGSource) => {
            const sourceType = s.sourceType || "web";

            // For image sources, use the source page link (not the image URL)
            let link: string;
            let title: string;

            if (sourceType === "image") {
                link = s.sourceUrl || s.metadata?.link || "";
                title = s.metadata?.title || s.filename || "Image source";
            } else {
                // Handle regular web sources
                link = s.sourceUrl || s.metadata?.link || "";
                title = s.metadata?.title || s.filename || "";
            }

            const source: SearchSource = {
                link,
                title,
                snippet: s.contentPreview || "",
                attribution: s.filename || "",
                processed: false,
                source_type: sourceType,
            };

            // Create a unique key for deduplication
            const uniqueKey = `${sourceType}:${source.link}:${source.title}`;

            // Skip duplicates or sources without links
            if (!source.link || seenSources.has(uniqueKey)) {
                return;
            }
            seenSources.add(uniqueKey);

            sources.push(source);
        });

        return sources;
    }, [ragMetadata]);

    // Don't render if no web sources
    if (webSources.length === 0) {
        return null;
    }

    return (
        <div
            className={`flex items-center gap-2 rounded border border-gray-200 px-2 py-1 dark:border-gray-700 ${onDeepResearchClick ? "cursor-pointer transition-colors hover:bg-gray-100 dark:hover:bg-gray-800/50" : ""}`}
            role={onDeepResearchClick ? "button" : undefined}
            aria-label={isDeepResearch ? "View deep research sources" : "View web search sources"}
            onClick={onDeepResearchClick}
        >
            <StackedFavicons sources={webSources} end={3} size={16} />
            <span className="text-sm text-gray-600 dark:text-gray-400">
                {webSources.length} {webSources.length === 1 ? "source" : "sources"}
            </span>
        </div>
    );
}

export default Sources;
