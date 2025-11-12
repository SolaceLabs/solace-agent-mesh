import DOMPurify from "dompurify";
import { marked } from "marked";
import parse, { type HTMLReactParserOptions, Element, domToReact, type DOMNode } from "html-react-parser";

import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";

interface MarkdownHTMLConverterProps {
    children?: string;
    className?: string;
    sources?: Array<{ citation_id: string; title?: string; link?: string }>;
}

/**
 * Process citation markers in text and convert them to clickable superscript links
 * Handles patterns like [[cite:search0]], [[cite:search1]], etc.
 */
function processCitations(text: string, sources?: Array<{ citation_id: string; title?: string; link?: string }>): string {
    if (!sources || sources.length === 0) {
        return text;
    }

    // Create a map of citation IDs to source indices
    const citationMap = new Map<string, number>();
    sources.forEach((source, index) => {
        citationMap.set(source.citation_id, index + 1);
    });

    // Replace [[cite:xxx]] with superscript citation numbers
    return text.replace(/\[\[cite:([^\]]+)\]\]/g, (match, citationId) => {
        const sourceIndex = citationMap.get(citationId);
        if (sourceIndex !== undefined) {
            // Create a superscript link that will be styled by CSS
            return `<sup class="citation-link" data-citation-id="${citationId}">[${sourceIndex}]</sup>`;
        }
        return match; // Keep original if citation not found
    });
}

/**
 * Auto-linkify plain URLs in text that aren't already part of markdown links
 */
function autoLinkifyUrls(text: string): string {
    // Match URLs that are NOT already in markdown link syntax [text](url)
    // This regex looks for URLs that are standalone (not preceded by ]( )
    const urlRegex = /(?<!\]\()https?:\/\/[^\s<]+[^<.,:;"')\]\s]/g;
    
    return text.replace(urlRegex, (url) => {
        // Don't linkify if it's already part of a markdown link
        return `[${url}](${url})`;
    });
}

const createParserOptions = (sources?: Array<{ citation_id: string; title?: string; link?: string }>): HTMLReactParserOptions => ({
    replace: (domNode) => {
        if (domNode instanceof Element) {
            // Handle regular links
            if (domNode.name === "a") {
                domNode.attribs.target = "_blank";
                domNode.attribs.rel = "noopener noreferrer";
                return undefined;
            }

            // Handle citation links
            if (domNode.name === "sup" && domNode.attribs?.class === "citation-link") {
                const citationId = domNode.attribs["data-citation-id"];
                const source = sources?.find(s => s.citation_id === citationId);
                
                if (source && source.link) {
                    return (
                        <sup>
                            <a
                                href={source.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="citation-link text-blue-600 dark:text-blue-400 hover:underline no-underline"
                                title={source.title || source.link}
                            >
                                {domToReact(domNode.children as DOMNode[])}
                            </a>
                        </sup>
                    );
                }
                
                // If no link, just render as plain superscript
                return (
                    <sup className="text-gray-500 dark:text-gray-400">
                        {domToReact(domNode.children as DOMNode[])}
                    </sup>
                );
            }
        }

        return undefined;
    },
});

export function MarkdownHTMLConverter({ children, className, sources }: Readonly<MarkdownHTMLConverterProps>) {
    if (!children) {
        return null;
    }

    try {
        // 1. Auto-linkify plain URLs
        const textWithLinks = autoLinkifyUrls(children);
        
        // 2. Process citations in the markdown text
        const processedText = processCitations(textWithLinks, sources);

        // 3. Convert markdown to HTML string using marked
        const rawHtml = marked.parse(processedText, { gfm: true }) as string;

        // 4. Sanitize the HTML string using DOMPurify (allow sup tags and data attributes)
        const cleanHtml = DOMPurify.sanitize(rawHtml, {
            USE_PROFILES: { html: true },
            ADD_TAGS: ['sup'],
            ADD_ATTR: ['data-citation-id', 'class']
        });

        // 5. Parse the sanitized HTML string into React elements
        const parserOptions = createParserOptions(sources);
        const reactElements = parse(cleanHtml, parserOptions);

        return <div className={getThemeHtmlStyles(className)}>{reactElements}</div>;
    } catch {
        return <div className={getThemeHtmlStyles(className)}>{children}</div>;
    }
}
