import React, { useState, useCallback } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import parse, { type HTMLReactParserOptions, Element } from "html-react-parser";
import { Copy, Check } from "lucide-react";

import { getThemeHtmlStyles } from "@/lib/utils/themeHtmlStyles";
import { Button } from "@/lib/components/ui";

interface MarkdownHTMLConverterProps {
    children?: string;
    className?: string;
}

interface CodeBlockProps {
    code: string;
    language?: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ code, language }) => {
    const [isCopied, setIsCopied] = useState(false);

    const handleCopy = useCallback(() => {
        navigator.clipboard
            .writeText(code)
            .then(() => {
                setIsCopied(true);
                setTimeout(() => setIsCopied(false), 2000);
            })
            .catch(err => {
                console.error("Failed to copy code:", err);
            });
    }, [code]);

    return (
        <div className="group relative">
            <pre className="border-border mb-4 max-w-full overflow-x-auto rounded-lg border bg-transparent p-4 whitespace-pre-wrap">
                <code className={`bg-transparent p-0 text-sm break-words ${language ? `language-${language}` : ""}`}>{code}</code>
            </pre>
            <Button variant="ghost" size="icon" className="bg-background/80 hover:bg-background absolute top-2 right-2 h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100" onClick={handleCopy} tooltip={isCopied ? "Copied!" : "Copy code"}>
                {isCopied ? <Check className="h-4 w-4 text-[var(--color-success-wMain)]" /> : <Copy className="h-4 w-4" />}
            </Button>
        </div>
    );
};

export function MarkdownHTMLConverter({ children, className }: Readonly<MarkdownHTMLConverterProps>) {
    if (!children) {
        return null;
    }

    const parserOptions: HTMLReactParserOptions = {
        replace: domNode => {
            if (domNode instanceof Element && domNode.attribs) {
                // Handle links
                if (domNode.name === "a") {
                    domNode.attribs.target = "_blank";
                    domNode.attribs.rel = "noopener noreferrer";
                }

                // Handle code blocks (pre > code)
                if (domNode.name === "pre") {
                    const codeElement = domNode.children.find(child => child instanceof Element && child.name === "code") as Element | undefined;

                    if (codeElement) {
                        // Extract code text content
                        const codeText = codeElement.children
                            .map(child => {
                                if ("data" in child) {
                                    return child.data;
                                }
                                return "";
                            })
                            .join("");

                        // Extract language from class (e.g., "language-javascript")
                        const languageClass = codeElement.attribs?.class || "";
                        const languageMatch = languageClass.match(/language-(\w+)/);
                        const language = languageMatch ? languageMatch[1] : undefined;

                        return <CodeBlock code={codeText} language={language} />;
                    }
                }
            }

            return undefined;
        },
    };

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
