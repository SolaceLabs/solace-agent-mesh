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

    try {
        // 1. Convert markdown to HTML string using marked
        const rawHtml = marked.parse(children, { gfm: true }) as string;

        // 2. Sanitize the HTML string using DOMPurify
        const cleanHtml = DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } });

        // 3. Parse the sanitized HTML string into React elements
        const reactElements = parse(cleanHtml, parserOptions);

        return <div className={getThemeHtmlStyles(className)}>{reactElements}</div>;
    } catch {
        return <div className={getThemeHtmlStyles(className)}>{children}</div>;
    }
}
