/**
 * Stacked Favicons Component
 * Displays overlapping favicons from multiple sources
 * Enhanced to support enterprise sources (Gmail, Outlook, Drive, SharePoint, KB)
 */

import { getCleanDomain, getFaviconUrl } from "@/lib/utils";
import type { SearchSource } from "@/lib/types/fe";
import { getFileTypeIcon } from "@/lib/components/chat/file/FileIcon";

interface StackedFaviconsProps {
    sources: SearchSource[];
    start?: number;
    end?: number;
    size?: number;
}

/**
 * Source icon component - handles web favicons, enterprise sources, and document file type icons
 */
function SourceIcon({ source, className = "", size = 16 }: { source: SearchSource; className?: string; size?: number }) {
    // Check if this is a document source (has filename but no link, or sourceType is 'document')
    const isDocument = source.sourceType === "document" || (source.filename && !source.link);

    if (isDocument && source.filename) {
        // Show file type icon for documents - reuses getFileTypeIcon from FileIcon component
        const iconSize = Math.round(size * 0.6);
        const icon = getFileTypeIcon(undefined, source.filename, { size: iconSize, className: "text-muted-foreground" });
        return (
            <div className={`bg-muted relative box-content overflow-hidden rounded-full border border-[var(--color-secondary-w20)] ${className}`} style={{ width: size, height: size }} title={source.filename}>
                <div className="flex h-full w-full items-center justify-center">{icon}</div>
            </div>
        );
    }

    // For web sources, use favicon
    const domain = getCleanDomain(source.link || "");
    return (
        <div className={`relative box-content overflow-hidden rounded-full border border-[var(--color-secondary-w20)] bg-white ${className}`} style={{ width: size, height: size }}>
            <img
                src={getFaviconUrl(domain, size * 2)}
                alt={domain}
                className="relative h-full w-full"
                onError={e => {
                    // Fallback to first letter of domain
                    const target = e.target as HTMLImageElement;
                    target.style.display = "none";
                    const parent = target.parentElement;
                    if (parent) {
                        parent.innerHTML = `<div class="bg-muted text-muted-foreground flex h-full w-full items-center justify-center text-xs font-bold">${domain[0].toUpperCase()}</div>`;
                    }
                }}
            />
        </div>
    );
}

/**
 * Stacked Favicons Component
 * Displays multiple favicons in an overlapping stack
 */
export function StackedFavicons({ sources, start = 0, end = 3, size = 16 }: StackedFaviconsProps) {
    // Handle negative start index (slice from end)
    const slice = start < 0 ? [start] : [start, end];
    const visibleSources = sources.slice(...slice);

    if (visibleSources.length === 0) {
        return null;
    }

    return (
        <div className="relative flex items-center" style={{ height: size }}>
            {visibleSources.map((source, i) => (
                <div
                    key={`favicon-${i}`}
                    className="relative"
                    style={{
                        marginLeft: i > 0 ? -4 : 0,
                        zIndex: i + 1,
                    }}
                >
                    <SourceIcon source={source} size={size} />
                </div>
            ))}
        </div>
    );
}

export default StackedFavicons;
