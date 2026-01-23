/**
 * Citation component for displaying clickable source citations
 */
import React, { useState, useMemo, useRef, useCallback, type ReactNode } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import parse, { type HTMLReactParserOptions, type DOMNode, Element, Text as DomText } from "html-react-parser";
import type { Citation as CitationType } from "@/lib/utils/citations";
import { getCitationTooltip, INDIVIDUAL_CITATION_PATTERN } from "@/lib/utils/citations";
import { MarkdownHTMLConverter } from "@/lib/components";
import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";
import { getSourceUrl } from "@/lib/utils/sourceUrlHelpers";
import { Popover, PopoverContent, PopoverTrigger } from "@/lib/components/ui/popover";
import { ExternalLink } from "lucide-react";

interface CitationProps {
    citation: CitationType;
    onClick?: (citation: CitationType) => void;
    maxLength?: number;
}

/**
 * Truncate text to fit within maxLength, adding ellipsis if needed
 */
function truncateText(text: string, maxLength: number): string {
    if (text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength - 3) + "...";
}

/**
 * Extract clean filename from file_id by removing session prefix if present
 * Same logic as RAGInfoPanel, but only applies if the filename has the session pattern
 */
function extractFilename(filename: string): string {
    // Check if this looks like a session-prefixed filename
    const hasSessionPrefix = filename.includes("web-session-") || filename.startsWith("sam_dev_user_");

    // If it doesn't have a session prefix, return as-is
    if (!hasSessionPrefix) {
        return filename;
    }

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

    // Add back the .pdf extension
    return cleaned + ".pdf";
}

/**
 * Get display text for citation (filename or URL)
 */
function getCitationDisplayText(citation: CitationType, maxLength: number = 30): string {
    // For web search citations, try to extract domain name even without full source data
    const isWebSearch = citation.source?.metadata?.type === "web_search" || citation.type === "search";

    if (isWebSearch && citation.source?.sourceUrl) {
        try {
            const url = new URL(citation.source.sourceUrl);
            const domain = url.hostname.replace(/^www\./, "");
            return truncateText(domain, maxLength);
        } catch {
            // If URL parsing fails, fall through to other methods
        }
    }

    // Check if source has a URL in metadata
    if (citation.source?.metadata?.link) {
        try {
            const url = new URL(citation.source.metadata.link);
            const domain = url.hostname.replace(/^www\./, "");
            return truncateText(domain, maxLength);
        } catch {
            // If URL parsing fails, continue
        }
    }

    // If no source data but it's a search citation, try to infer from citation type
    if (!citation.source && citation.type === "search") {
        // For search citations without source data, show a more descriptive label
        return `Web Source ${citation.sourceId + 1}`;
    }

    if (!citation.source) {
        return `Source ${citation.sourceId + 1}`;
    }

    // The filename field contains the original filename (not the temp path)
    // The source_url field contains the temp path (not useful for display)
    if (citation.source.filename) {
        // For KB search, filename already contains the original name
        // For file search, it might have session prefix that needs extraction
        const hasSessionPrefix = citation.source.filename.includes("web-session-") || citation.source.filename.startsWith("sam_dev_user_");

        const displayName = hasSessionPrefix ? extractFilename(citation.source.filename) : citation.source.filename;

        return truncateText(displayName, maxLength);
    }

    // Fallback to source URL if no filename
    if (citation.source.sourceUrl) {
        // Try to extract domain name or filename from URL
        try {
            const url = new URL(citation.source.sourceUrl);
            const domain = url.hostname.replace(/^www\./, "");
            return truncateText(domain, maxLength);
        } catch {
            // If URL parsing fails, try to extract filename
            const filename = citation.source.sourceUrl.split("/").pop() || citation.source.sourceUrl;
            return truncateText(filename, maxLength);
        }
    }

    return `Source ${citation.sourceId + 1}`;
}

export function Citation({ citation, onClick, maxLength = 30 }: CitationProps) {
    const displayText = getCitationDisplayText(citation, maxLength);
    const tooltip = getCitationTooltip(citation);

    // Check if this is a web search or deep research citation with a URL
    const { url: sourceUrl, sourceType } = getSourceUrl(citation.source);
    const isWebSearch = sourceType === "web_search" || citation.type === "search";
    const isDeepResearch = sourceType === "deep_research" || citation.type === "research";
    const hasClickableUrl = (isWebSearch || isDeepResearch) && sourceUrl;

    const handleClick = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();

        // For web search and deep research citations with URLs, open the URL directly
        if (hasClickableUrl) {
            window.open(sourceUrl, "_blank", "noopener,noreferrer");
            return;
        }

        // For RAG citations, use onClick handler (to open RAG panel)
        if (onClick) {
            onClick(citation);
        }
    };

    return (
        <button
            onClick={handleClick}
            className="citation-badge mx-0.5 inline-flex cursor-pointer items-center gap-0.5 rounded-sm bg-gray-200 px-1.5 py-0 align-baseline text-[11px] font-normal whitespace-nowrap text-gray-800 transition-colors duration-150 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
            title={tooltip}
            aria-label={`Citation: ${tooltip}`}
            type="button"
        >
            <span className="max-w-[200px] truncate">{displayText}</span>
            {hasClickableUrl && <ExternalLink className="h-2.5 w-2.5 flex-shrink-0" />}
        </button>
    );
}

/**
 * Bundled Citations Component
 * Displays multiple citations grouped together at the end of a paragraph
 * If only one citation, shows it as a regular citation badge
 * If multiple, shows first citation name with "+X" in the same bubble
 */
interface BundledCitationsProps {
    citations: CitationType[];
    onCitationClick?: (citation: CitationType) => void;
}

export function BundledCitations({ citations, onCitationClick }: BundledCitationsProps) {
    const [isDark, setIsDark] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const showTimeout = 150;
    const hideTimeout = 150;

    // Detect dark mode
    React.useEffect(() => {
        const checkDarkMode = () => {
            setIsDark(document.documentElement.classList.contains("dark"));
        };

        checkDarkMode();

        const observer = new MutationObserver(checkDarkMode);
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["class"],
        });

        return () => observer.disconnect();
    }, []);

    // Cleanup timeout on unmount
    React.useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    const handleMouseEnter = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            setIsOpen(true);
        }, showTimeout);
    }, []);

    const handleMouseLeave = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            setIsOpen(false);
        }, hideTimeout);
    }, []);

    const handleContentMouseEnter = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
    }, []);

    const handleContentMouseLeave = useCallback(() => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = setTimeout(() => {
            setIsOpen(false);
        }, hideTimeout);
    }, []);

    if (citations.length === 0) return null;

    // Get unique citations (deduplicate by sourceId)
    const uniqueCitations = citations.filter((citation, index, self) => index === self.findIndex(c => c.sourceId === citation.sourceId && c.type === citation.type));

    // If only one citation, render it as a regular citation badge
    if (uniqueCitations.length === 1) {
        return <Citation citation={uniqueCitations[0]} onClick={onCitationClick} />;
    }

    // Multiple citations - show first citation name + "+X" in same bubble
    const firstCitation = uniqueCitations[0];
    const remainingCount = uniqueCitations.length - 1;
    const firstDisplayText = getCitationDisplayText(firstCitation, 20);
    const tooltip = getCitationTooltip(firstCitation);

    // Check if this is a web search or deep research citation
    const { url: sourceUrl, sourceType } = getSourceUrl(firstCitation.source);
    const isWebSearch = sourceType === "web_search" || firstCitation.type === "search";
    const isDeepResearch = sourceType === "deep_research" || firstCitation.type === "research";
    const hasClickableUrl = (isWebSearch || isDeepResearch) && sourceUrl;

    const handleFirstCitationClick = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();

        // For web search and deep research citations, open the URL directly
        if (hasClickableUrl && sourceUrl) {
            window.open(sourceUrl, "_blank", "noopener,noreferrer");
            return;
        }

        // For RAG citations, use onClick handler (to open RAG panel)
        if (onCitationClick) {
            onCitationClick(firstCitation);
        }
    };

    return (
        <Popover open={isOpen} onOpenChange={setIsOpen}>
            <PopoverTrigger asChild>
                <button
                    onClick={handleFirstCitationClick}
                    onMouseEnter={handleMouseEnter}
                    onMouseLeave={handleMouseLeave}
                    className="citation-badge mx-0.5 inline-flex cursor-pointer items-center gap-1 rounded-sm bg-gray-200 px-1.5 py-0 align-baseline text-[11px] font-normal whitespace-nowrap text-gray-800 transition-colors duration-150 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
                    title={tooltip}
                    aria-label={`Citation: ${tooltip}`}
                    type="button"
                >
                    <span className="max-w-[200px] truncate">{firstDisplayText}</span>
                    {hasClickableUrl && <ExternalLink className="h-2.5 w-2.5 flex-shrink-0" />}
                    <span className="text-[10px] opacity-70">+{remainingCount}</span>
                </button>
            </PopoverTrigger>
            <PopoverContent
                sideOffset={8}
                onMouseEnter={handleContentMouseEnter}
                onMouseLeave={handleContentMouseLeave}
                className="z-[999] max-h-[400px] w-[320px] max-w-[calc(100vw-2rem)] cursor-default overflow-y-auto rounded-lg border p-3 shadow-xl"
                style={{
                    backgroundColor: isDark ? "#1f2937" : "#ffffff",
                    borderColor: isDark ? "#4b5563" : "#d1d5db",
                    color: isDark ? "#f3f4f6" : "#111827",
                }}
            >
                <div className="cursor-default space-y-2">
                    <div className="mb-3 border-b pb-2" style={{ borderColor: isDark ? "#4b5563" : "#e5e7eb" }}>
                        <h3 className="text-sm font-semibold">All Sources · {uniqueCitations.length}</h3>
                    </div>
                    {uniqueCitations.map((citation, index) => {
                        const displayText = getCitationDisplayText(citation, 50);
                        const { url: sourceUrl, sourceType } = getSourceUrl(citation.source);
                        const isWebSearch = sourceType === "web_search" || citation.type === "search";
                        const isDeepResearch = sourceType === "deep_research" || citation.type === "research";
                        const hasClickableUrl = (isWebSearch || isDeepResearch) && sourceUrl;

                        // Get favicon for web sources (both web search and deep research)
                        let favicon = null;
                        if ((isWebSearch || isDeepResearch) && sourceUrl) {
                            try {
                                const url = new URL(sourceUrl);
                                const domain = url.hostname;
                                favicon = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
                            } catch {
                                // Ignore favicon errors
                            }
                        }

                        const handleClick = (e: React.MouseEvent) => {
                            e.preventDefault();
                            e.stopPropagation();

                            if (hasClickableUrl && sourceUrl) {
                                window.open(sourceUrl, "_blank", "noopener,noreferrer");
                            } else if (onCitationClick) {
                                onCitationClick(citation);
                            }
                        };

                        return (
                            <button
                                key={`bundled-citation-${index}`}
                                onClick={handleClick}
                                className="group flex w-full cursor-pointer items-start gap-2 rounded-md p-2 text-left transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
                                type="button"
                            >
                                {favicon && (
                                    <div className="relative mt-0.5 h-4 w-4 flex-shrink-0 overflow-hidden rounded-full bg-white">
                                        <img src={favicon} alt="" className="h-full w-full" />
                                        <div className="absolute inset-0 rounded-full border border-gray-200/10 dark:border-transparent" />
                                    </div>
                                )}
                                <div className="flex-1 overflow-hidden">
                                    <div className="flex items-center gap-1">
                                        <span className="truncate text-sm font-medium text-[var(--color-primary-wMain)] group-hover:text-[var(--color-primary-w60)] dark:text-[var(--color-primary-w60)] dark:group-hover:text-[var(--color-white)]">
                                            {displayText}
                                        </span>
                                        {hasClickableUrl && (
                                            <ExternalLink className="h-3 w-3 flex-shrink-0 text-[var(--color-primary-wMain)] group-hover:text-[var(--color-primary-w60)] dark:text-[var(--color-primary-w60)] dark:group-hover:text-[var(--color-white)]" />
                                        )}
                                    </div>
                                    {citation.source?.metadata?.title && <div className="mt-0.5 truncate text-xs text-gray-600 dark:text-gray-400">{citation.source.metadata.title}</div>}
                                </div>
                            </button>
                        );
                    })}
                </div>
            </PopoverContent>
        </Popover>
    );
}

/**
 * Component to render text with embedded citations
 */
interface TextWithCitationsProps {
    text: string;
    citations: CitationType[];
    onCitationClick?: (citation: CitationType) => void;
}

/**
 * Parse a citation ID and return its components
 * Handles both formats:
 * - s{turn}r{index} (e.g., "s0r0", "s1r2") -> type: "search"
 * - research{N} (e.g., "research0") -> type: "research"
 */
function parseCitationIdLocal(citationId: string): { type: "search" | "research"; sourceId: number } | null {
    // Try sTrN format first
    const searchMatch = citationId.match(/^s(\d+)r(\d+)$/);
    if (searchMatch) {
        return {
            type: "search",
            sourceId: parseInt(searchMatch[2], 10), // Use result index as sourceId
        };
    }

    // Try research format
    const researchMatch = citationId.match(/^research(\d+)$/);
    if (researchMatch) {
        return {
            type: "research",
            sourceId: parseInt(researchMatch[1], 10),
        };
    }

    return null;
}

/**
 * Parse individual citations from a comma-separated content string
 * Supports: s0r0, s1r2, research0, research1
 */
function parseMultiCitationIds(content: string): Array<{ type: "search" | "research"; sourceId: number; citationId: string }> {
    const results: Array<{ type: "search" | "research"; sourceId: number; citationId: string }> = [];
    let individualMatch;

    INDIVIDUAL_CITATION_PATTERN.lastIndex = 0;
    while ((individualMatch = INDIVIDUAL_CITATION_PATTERN.exec(content)) !== null) {
        const citationId = individualMatch[1]; // The captured citation ID (s0r0 or research0)
        const parsed = parseCitationIdLocal(citationId);

        if (parsed) {
            results.push({
                type: parsed.type,
                sourceId: parsed.sourceId,
                citationId: citationId,
            });
        }
    }

    return results;
}

/**
 * Combined pattern that matches both single and multi-citation formats
 * This ensures we process them in order of appearance
 * Supports: s0r0, s1r2, research0, research1
 */
const COMBINED_CITATION_PATTERN = /\[?\[cite:((?:s\d+r\d+|research\d+)(?:\s*,\s*(?:cite:)?(?:s\d+r\d+|research\d+))*)\]\]?/g;

/**
 * Process text node content to replace citation markers with React components
 */
function processTextWithCitations(textContent: string, citations: CitationType[], onCitationClick?: (citation: CitationType) => void): ReactNode[] {
    const result: ReactNode[] = [];
    let lastIndex = 0;
    let match;
    let pendingCitations: CitationType[] = [];

    // Reset regex
    COMBINED_CITATION_PATTERN.lastIndex = 0;

    while ((match = COMBINED_CITATION_PATTERN.exec(textContent)) !== null) {
        // Add text before citation
        if (match.index > lastIndex) {
            // Flush pending citations before text
            if (pendingCitations.length > 0) {
                result.push(<BundledCitations key={`cit-${lastIndex}`} citations={pendingCitations} onCitationClick={onCitationClick} />);
                pendingCitations = [];
            }
            result.push(textContent.substring(lastIndex, match.index));
        }

        // Parse the citation content (could be single or comma-separated)
        const [, content] = match;
        const citationIds = parseMultiCitationIds(content);

        for (const { citationId } of citationIds) {
            // Look up by citationId (e.g., "s0r0" or "research0")
            const citation = citations.find(c => c.citationId === citationId);

            if (citation) {
                pendingCitations.push(citation);
            }
        }

        lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < textContent.length) {
        // Flush pending citations before remaining text
        if (pendingCitations.length > 0) {
            result.push(<BundledCitations key={`cit-${lastIndex}`} citations={pendingCitations} onCitationClick={onCitationClick} />);
            pendingCitations = [];
        }
        result.push(textContent.substring(lastIndex));
    } else if (pendingCitations.length > 0) {
        // Flush any remaining citations at the end
        result.push(<BundledCitations key={`cit-end`} citations={pendingCitations} onCitationClick={onCitationClick} />);
    }

    return result;
}

export function TextWithCitations({ text, citations, onCitationClick }: TextWithCitationsProps) {
    // Create parser options to process text nodes and replace citation markers
    const parserOptions: HTMLReactParserOptions = useMemo(
        () => ({
            replace: (domNode: DOMNode) => {
                // Process text nodes to find and replace citation markers
                if (domNode.type === "text" && domNode instanceof DomText) {
                    const textContent = domNode.data;

                    // Check if this text contains citation markers (single or multi)
                    COMBINED_CITATION_PATTERN.lastIndex = 0;
                    if (COMBINED_CITATION_PATTERN.test(textContent)) {
                        COMBINED_CITATION_PATTERN.lastIndex = 0;
                        const processed = processTextWithCitations(textContent, citations, onCitationClick);
                        if (processed.length > 0) {
                            return <>{processed}</>;
                        }
                    }
                }

                // Handle links - add target blank
                if (domNode instanceof Element && domNode.name === "a") {
                    domNode.attribs.target = "_blank";
                    domNode.attribs.rel = "noopener noreferrer";
                }

                return undefined;
            },
        }),
        [citations, onCitationClick]
    );

    if (citations.length === 0) {
        return <MarkdownHTMLConverter>{text}</MarkdownHTMLConverter>;
    }

    try {
        // Convert markdown to HTML
        const rawHtml = marked.parse(text, { gfm: true }) as string;
        const cleanHtml = DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } });

        // Parse HTML and inject citations
        const reactElements = parse(cleanHtml, parserOptions);

        return <div className={getThemeHtmlStyles()}>{reactElements}</div>;
    } catch {
        return <MarkdownHTMLConverter>{text}</MarkdownHTMLConverter>;
    }
}
