import React, { useState, useCallback } from "react";
import DOMPurify from "dompurify";
import { marked } from "marked";
import parse, { type HTMLReactParserOptions, Element, domToReact } from "html-react-parser";
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
            <pre className="mb-4 max-w-full overflow-x-auto rounded-lg border bg-transparent p-4 whitespace-pre-wrap">
                <code className={`bg-transparent p-0 text-sm break-words ${language ? `language-${language}` : ""}`}>{code}</code>
            </pre>
            <Button
                variant="ghost"
                size="icon"
                className="absolute top-2 right-2 h-8 w-8 bg-(--background-w10)/80 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-(--background-w10)"
                onClick={handleCopy}
                tooltip={isCopied ? "Copied!" : "Copy code"}
            >
                {isCopied ? <Check className="h-4 w-4 text-(--success-wMain)" /> : <Copy className="h-4 w-4" />}
            </Button>
        </div>
    );
};

export function MarkdownHTMLConverter({ children, className }: Readonly<MarkdownHTMLConverterProps>) {
    if (!children) {
        return null;
    }

    const liStartsWithCheckbox = (li: Element): boolean => {
        const first = li.children.find(c => (c as { type: string }).type !== "text" || ((c as unknown as { data: string }).data ?? "").trim() !== "");
        return first instanceof Element && first.name === "input" && first.attribs?.type === "checkbox";
    };

    const parserOptions: HTMLReactParserOptions = {
        replace: domNode => {
            if (domNode instanceof Element && domNode.attribs) {
                // GFM task-list checkbox — replace native disabled input with a styled span
                if (domNode.name === "input" && domNode.attribs.type === "checkbox") {
                    const isChecked = domNode.attribs.checked !== undefined;
                    return (
                        <span
                            aria-hidden
                            style={{
                                display: "inline-block",
                                width: "0.875rem",
                                height: "0.875rem",
                                flexShrink: 0,
                                border: `1px solid ${isChecked ? "var(--primary-wMain)" : "currentColor"}`,
                                opacity: isChecked ? 1 : 0.6,
                                borderRadius: "2px",
                                backgroundColor: isChecked ? "var(--primary-wMain)" : "transparent",
                                backgroundImage: isChecked
                                    ? "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16' fill='white'%3E%3Cpath d='M13.78 4.22a.75.75 0 0 1 0 1.06l-7 7a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 1 1 1.06-1.06L6.25 10.69l6.47-6.47a.75.75 0 0 1 1.06 0Z'/%3E%3C/svg%3E\")"
                                    : undefined,
                                backgroundRepeat: "no-repeat",
                                backgroundPosition: "center",
                                backgroundSize: "80%",
                                verticalAlign: "middle",
                            }}
                        />
                    );
                }

                // Drop the disc bullet on lists that contain task-list items.
                if (domNode.name === "ul" && domNode.children.some(c => c instanceof Element && c.name === "li" && liStartsWithCheckbox(c))) {
                    return <ul style={{ listStyle: "none", paddingLeft: "0.25rem", marginBottom: "1rem" }}>{domToReact(domNode.children as Parameters<typeof domToReact>[0], parserOptions)}</ul>;
                }

                if (domNode.name === "li" && liStartsWithCheckbox(domNode)) {
                    return <li style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>{domToReact(domNode.children as Parameters<typeof domToReact>[0], parserOptions)}</li>;
                }

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
