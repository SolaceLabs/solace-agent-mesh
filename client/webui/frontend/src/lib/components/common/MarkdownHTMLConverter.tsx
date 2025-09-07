import DOMPurify from "dompurify";
import { marked } from "marked";
import parse, { type HTMLReactParserOptions, Element } from "html-react-parser";

import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";

interface MarkdownHTMLConverterProps {
    children?: string;
    className?: string;
}

const parserOptions: HTMLReactParserOptions = {
    replace: domNode => {
        if (domNode instanceof Element && domNode.attribs && domNode.name === "a") {
            domNode.attribs.target = "_blank";
            domNode.attribs.rel = "noopener noreferrer";
        }

        return undefined;
    },
};

export function MarkdownHTMLConverter({ children, className }: Readonly<MarkdownHTMLConverterProps>) {
    if (!children) {
        return null;
    }

    // Helper function to decode HTML entities
    const decodeHtmlEntities = (text: string): string => {
        const textarea = document.createElement('textarea');
        textarea.innerHTML = text;
        return textarea.value;
    };

    try {
        // 1. Decode HTML entities first
        const decodedChildren = decodeHtmlEntities(children);
        
        // 2. Convert markdown to HTML string using marked
        const rawHtml = marked.parse(decodedChildren, { gfm: true }) as string;

        // 3. Sanitize the HTML string using DOMPurify
        const cleanHtml = DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } });

        // 4. Parse the sanitized HTML string into React elements
        const reactElements = parse(cleanHtml, parserOptions);

        return <div className={getThemeHtmlStyles(className)}>{reactElements}</div>;
    } catch {
        return <div className={getThemeHtmlStyles(className)}>{children}</div>;
    }
}
