import React, { useMemo } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import parse, { type HTMLReactParserOptions, type DOMNode, Element } from "html-react-parser";

import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";
import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";
import type { RAGSearchResult } from "@/lib/types";

interface MarkdownRendererProps extends BaseRendererProps {
    ragData?: RAGSearchResult;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, ragData }) => {
    const { ref, handleKeyDown } = useCopy<HTMLDivElement>();
    const containerRef = React.useRef<HTMLDivElement>(null);

    // Render markdown with citation handling
    const renderedContent = useMemo(() => {
        try {
            // 1. Pre-process content to replace citation markers with HTML placeholders BEFORE markdown parsing
            let processedContent = content;
            const citationRegex = /\[\[cite:(file|ref|search)(\d+)\]\]/g;
            let match;

            // Collect all citations with their positions
            const allCitations: Array<{
                index: number;
                length: number;
                type: string;
                num: string;
                displayNum: number;
                displayText: string;
            }> = [];

            while ((match = citationRegex.exec(content)) !== null) {
                const citationType = match[1];
                const citationNum = match[2];
                const displayNum = parseInt(citationNum) + 1;

                // Get display text from ragData
                let displayText = `${displayNum}`; // No brackets, just number
                if (ragData && ragData.sources) {
                    const citationId = `${citationType}${citationNum}`;
                    const source = ragData.sources.find(s => s.citationId === citationId);
                    if (source) {
                        if (source.url || source.sourceUrl) {
                            try {
                                const url = new URL(source.url || source.sourceUrl || "");
                                const domain = url.hostname.replace(/^www\./, "");
                                displayText = domain.length > 20 ? domain.substring(0, 20) + "..." : domain;
                            } catch {
                                displayText = source.title && source.title.length > 20 ? source.title.substring(0, 20) + "..." : source.title || `${displayNum}`;
                            }
                        } else if (source.title) {
                            displayText = source.title.length > 20 ? source.title.substring(0, 20) + "..." : source.title;
                        }
                    }
                }

                allCitations.push({
                    index: match.index,
                    length: match[0].length,
                    type: citationType,
                    num: citationNum,
                    displayNum,
                    displayText,
                });
            }

            // Group consecutive citations and sort each group
            const citationGroups: Array<typeof allCitations> = [];
            let currentGroup: typeof allCitations = [];

            allCitations.forEach((cit, idx) => {
                if (currentGroup.length === 0) {
                    currentGroup.push(cit);
                } else {
                    const lastCit = currentGroup[currentGroup.length - 1];
                    const lastEnd = lastCit.index + lastCit.length;

                    // Check if this citation immediately follows the previous one
                    if (cit.index === lastEnd) {
                        currentGroup.push(cit);
                    } else {
                        // Start new group
                        citationGroups.push(currentGroup);
                        currentGroup = [cit];
                    }
                }

                // Push last group
                if (idx === allCitations.length - 1) {
                    citationGroups.push(currentGroup);
                }
            });

            // Sort each group by display number and replace in reverse order
            citationGroups.reverse().forEach(group => {
                // Sort group by display number (low to high)
                const sortedGroup = [...group].sort((a, b) => a.displayNum - b.displayNum);

                // Calculate group start and end
                const groupStart = group[0].index;
                const groupEnd = group[group.length - 1].index + group[group.length - 1].length;

                // Build replacement HTML for this group
                const groupHtml = sortedGroup.map(cit => `<span data-citation-placeholder="true" data-citation-num="${cit.displayNum}" data-citation-text="${cit.displayText.replace(/"/g, "&quot;")}"></span>`).join("");

                // Replace the entire group
                processedContent = processedContent.substring(0, groupStart) + groupHtml + processedContent.substring(groupEnd);
            });

            // 2. Convert markdown to HTML string using marked
            const rawHtml = marked.parse(processedContent, { gfm: true }) as string;

            // 3. Sanitize the HTML string using DOMPurify (allow data attributes)
            const cleanHtml = DOMPurify.sanitize(rawHtml, {
                USE_PROFILES: { html: true },
                ADD_ATTR: ["data-citation-placeholder", "data-citation-num", "data-citation-text"],
            });

            // 4. Parse HTML and replace citation placeholders with React buttons
            const parserOptions: HTMLReactParserOptions = {
                replace: (domNode: DOMNode) => {
                    // Replace citation placeholder spans with buttons
                    if (domNode instanceof Element && domNode.name === "span" && domNode.attribs?.["data-citation-placeholder"]) {
                        const displayNum = parseInt(domNode.attribs["data-citation-num"] || "0");
                        const displayText = domNode.attribs["data-citation-text"] || `${displayNum}`;

                        return (
                            <button
                                type="button"
                                className="citation-badge mx-0.5 inline-flex cursor-pointer items-center rounded-sm bg-gray-200 px-1.5 py-0 align-baseline text-[11px] font-normal whitespace-nowrap text-gray-800 transition-colors duration-150 hover:bg-gray-300 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
                                onClick={e => {
                                    e.preventDefault();
                                    e.stopPropagation();

                                    const container = containerRef.current;
                                    if (!container) return;

                                    const allStrong = Array.from(container.querySelectorAll("strong, b"));
                                    const citationElement = allStrong.find(el => {
                                        const text = el.textContent?.trim();
                                        return text === `[${displayNum}]`;
                                    });

                                    if (citationElement) {
                                        citationElement.scrollIntoView({ behavior: "smooth", block: "center" });
                                        return;
                                    }

                                    const referencesHeading = Array.from(container.querySelectorAll("h2, h3, h4, h5, h6")).find(el => el.textContent?.toLowerCase().includes("reference"));
                                    if (referencesHeading) {
                                        referencesHeading.scrollIntoView({ behavior: "smooth", block: "start" });
                                    }
                                }}
                                title={`Citation ${displayNum} - Click to view reference`}
                            >
                                {displayText}
                            </button>
                        );
                    }
                    return undefined;
                },
            };

            return parse(cleanHtml, parserOptions);
        } catch (error) {
            console.error("MarkdownRenderer: Error rendering markdown:", error);
            return content;
        }
    }, [content, ragData]);

    return (
        <div className="w-full p-4" ref={containerRef}>
            <div ref={ref} className="max-w-full overflow-hidden select-text focus-visible:outline-none" tabIndex={0} onKeyDown={handleKeyDown}>
                <div className={getThemeHtmlStyles("max-w-full break-words")}>{renderedContent}</div>
            </div>
        </div>
    );
};
