/**
 * Stacked Favicons Component
 * Displays overlapping favicons from multiple sources
 * Enhanced to support enterprise sources (Gmail, Outlook, Drive, SharePoint, KB)
 */

import { getCleanDomain, getFaviconUrl } from "@/lib/utils";

interface SearchSource {
    link: string;
    title?: string;
    snippet?: string;
    source_type?: string; // 'web', 'kb'
}

interface StackedFaviconsProps {
    sources: SearchSource[];
    start?: number;
    end?: number;
    size?: number;
}

/**
 * Source icon component - handles both web favicons and enterprise source icons
 */
function SourceIcon({ source, className = "", size = 16 }: { source: SearchSource; className?: string; size?: number }) {
    // For web sources, use favicon
    const domain = getCleanDomain(source.link);
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
                        parent.innerHTML = `<div class="flex items-center justify-center w-full h-full text-xs font-bold text-gray-600 bg-gray-200">${domain[0].toUpperCase()}</div>`;
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
