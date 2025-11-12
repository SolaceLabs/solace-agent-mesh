import React, { useMemo } from "react";
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import parse, { type HTMLReactParserOptions, type DOMNode, Text } from 'html-react-parser';

import type { BaseRendererProps } from ".";
import { useCopy } from "../../../../hooks/useCopy";
import { getThemeHtmlStyles } from '@/lib/utils/themeHtmlStyles';

export const MarkdownRenderer: React.FC<BaseRendererProps> = ({ content }) => {
    const { ref, handleKeyDown } = useCopy<HTMLDivElement>();
    const containerRef = React.useRef<HTMLDivElement>(null);

    // Custom parser options to convert citation markers to superscript links
    const parserOptions: HTMLReactParserOptions = useMemo(
        () => ({
            replace: (domNode: DOMNode) => {
                // Handle text nodes - check for citation markers
                if (domNode.type === 'text') {
                    const textNode = domNode as Text;
                    const textContent = textNode.data;

                    // Check for citation markers like [[cite:file1]] - ONLY double-bracket format
                    const citationRegex = /\[\[cite:(file|ref|search)(\d+)\]\]/g;
                    const hasCitations = citationRegex.test(textContent);
                    citationRegex.lastIndex = 0;

                    if (!hasCitations) {
                        return undefined; // No citations, keep as-is
                    }

                    // Split text by citation markers
                    const segments: (string | React.ReactElement)[] = [];
                    let lastIndex = 0;
                    let match;

                    while ((match = citationRegex.exec(textContent)) !== null) {
                        // Add text before citation
                        if (match.index > lastIndex) {
                            segments.push(textContent.substring(lastIndex, match.index));
                        }

                        // Extract citation number and convert to 1-based
                        const citationNum = match[2]; // From [[cite:fileX]]
                        const displayNum = parseInt(citationNum) + 1; // Convert 0-based to 1-based
                        
                        // Add citation as clickable superscript that scrolls to reference
                        segments.push(
                            <sup
                                key={`cite-${match.index}`}
                                className="text-blue-600 dark:text-blue-400 cursor-pointer hover:underline"
                                onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    
                                    // Scope search to the preview container only
                                    const container = containerRef.current;
                                    if (!container) return;
                                    
                                    // Try multiple strategies to find the citation in the References section
                                    
                                    // Strategy 1: Look for the exact citation number in bold (e.g., **[1]**)
                                    const allStrong = Array.from(container.querySelectorAll('strong, b'));
                                    const citationElement = allStrong.find(el => {
                                        const text = el.textContent?.trim();
                                        return text === `[${displayNum}]`;
                                    });
                                    
                                    if (citationElement) {
                                        citationElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                        return;
                                    }
                                    
                                    // Strategy 2: Look for References heading and scroll there within container
                                    const referencesHeading = Array.from(container.querySelectorAll('h2, h3, h4, h5, h6'))
                                        .find(el => el.textContent?.toLowerCase().includes('reference'));
                                    
                                    if (referencesHeading) {
                                        referencesHeading.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                    }
                                }}
                            >
                                [{displayNum}]
                            </sup>
                        );

                        lastIndex = match.index + match[0].length;
                    }

                    // Add remaining text
                    if (lastIndex < textContent.length) {
                        segments.push(textContent.substring(lastIndex));
                    }

                    // Return the segments as a fragment
                    return <>{segments}</>;
                }

                return undefined;
            },
        }),
        []
    );

    // Render markdown with citation handling
    const renderedContent = useMemo(() => {
        try {
            // 1. Convert markdown to HTML string using marked
            const rawHtml = marked.parse(content, { gfm: true }) as string;

            // 2. Sanitize the HTML string using DOMPurify
            const cleanHtml = DOMPurify.sanitize(rawHtml, {
                USE_PROFILES: { html: true },
            });

            // 3. Parse the sanitized HTML string into React elements with citation handling
            return parse(cleanHtml, parserOptions);
        } catch (error) {
            console.error('MarkdownRenderer: Error rendering markdown:', error);
            return content;
        }
    }, [content, parserOptions]);

    return (
        <div className="w-full p-4" ref={containerRef}>
            <div
                ref={ref}
                className="max-w-full overflow-hidden select-text focus-visible:outline-none"
                tabIndex={0}
                onKeyDown={handleKeyDown}
            >
                <div className={getThemeHtmlStyles("max-w-full break-words")}>
                    {renderedContent}
                </div>
            </div>
        </div>
    );
};
