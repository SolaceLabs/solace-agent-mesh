/**
 * Markdown to Speech Preprocessor
 *
 * Converts markdown-formatted text to natural, speakable text suitable for
 * Text-to-Speech (TTS) engines. Uses the `marked` library for markdown
 * parsing.
 *
 * This is the frontend version that mirrors the backend Python implementation
 * for use with browser-based TTS.
 */

import { marked, Renderer } from "marked";
import type { Tokens } from "marked";

export interface MarkdownToSpeechOptions {
    /** Whether to announce code blocks (e.g., "Code block: print hello") */
    readCodeBlocks?: boolean;
    /** Whether to announce images (e.g., "Image: description") */
    readImages?: boolean;
    /** Whether to read citation references like [1], [2] */
    readCitations?: boolean;
    /** Format for citations. Use {n} as placeholder for the number */
    citationFormat?: string;
    /** Whether to add pauses (periods) after headers */
    addHeaderPauses?: boolean;
    /** Prefix for code blocks when readCodeBlocks is true */
    codeBlockPrefix?: string;
    /** Prefix for images when readImages is true */
    imagePrefix?: string;
}

const DEFAULT_OPTIONS: Required<MarkdownToSpeechOptions> = {
    readCodeBlocks: false,
    readImages: true,
    readCitations: true,
    citationFormat: "reference {n}",
    addHeaderPauses: true,
    codeBlockPrefix: "Code block.",
    imagePrefix: "Image:",
};

/**
 * Create a custom marked renderer that extracts plain text for TTS.
 */
function createSpeechRenderer(opts: Required<MarkdownToSpeechOptions>): Renderer {
    const renderer = new Renderer();

    // Code blocks - we intentionally ignore the code text for TTS
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    renderer.code = (_token: Tokens.Code): string => {
        if (opts.readCodeBlocks) {
            return ` ${opts.codeBlockPrefix} `;
        }
        return " ";
    };

    // Inline code - just return the text
    renderer.codespan = ({ text }: Tokens.Codespan): string => {
        return text;
    };

    // Blockquotes - just return the content
    renderer.blockquote = ({ text }: Tokens.Blockquote): string => {
        return text;
    };

    // HTML - strip it
    renderer.html = (): string => {
        return "";
    };

    // Headings - add pause after if configured
    renderer.heading = ({ text }: Tokens.Heading): string => {
        if (opts.addHeaderPauses) {
            return `${text}. `;
        }
        return `${text} `;
    };

    // Horizontal rules
    renderer.hr = (): string => {
        return " ";
    };

    // Lists
    renderer.list = ({ items }: Tokens.List): string => {
        return items.map(item => item.text).join(" ");
    };

    // List items
    renderer.listitem = ({ text }: Tokens.ListItem): string => {
        return `${text} `;
    };

    // Paragraphs
    renderer.paragraph = ({ text }: Tokens.Paragraph): string => {
        return `${text} `;
    };

    // Tables - extract text from cells
    renderer.table = ({ header, rows }: Tokens.Table): string => {
        const headerText = header.map(cell => cell.text).join(" ");
        const rowsText = rows.map(row => row.map(cell => cell.text).join(" ")).join(" ");
        return `${headerText} ${rowsText} `;
    };

    // Table row
    renderer.tablerow = ({ text }: Tokens.TableRow): string => {
        return `${text} `;
    };

    // Table cell
    renderer.tablecell = ({ text }: Tokens.TableCell): string => {
        return `${text} `;
    };

    // Strong/bold - just return text
    renderer.strong = ({ text }: Tokens.Strong): string => {
        return text;
    };

    // Emphasis/italic - just return text
    renderer.em = ({ text }: Tokens.Em): string => {
        return text;
    };

    // Strikethrough - just return text
    renderer.del = ({ text }: Tokens.Del): string => {
        return text;
    };

    // Links - keep the text, drop the URL
    renderer.link = ({ text }: Tokens.Link): string => {
        return text;
    };

    // Images
    renderer.image = ({ title, text }: Tokens.Image): string => {
        if (opts.readImages) {
            const altText = text || title || "";
            if (altText.trim()) {
                return ` ${opts.imagePrefix} ${altText}. `;
            }
        }
        return " ";
    };

    // Line breaks
    renderer.br = (): string => {
        return " ";
    };

    // Plain text - return as-is
    renderer.text = ({ text }: Tokens.Text): string => {
        return text;
    };

    return renderer;
}

/**
 * Handle SAM-specific citation formats that marked doesn't recognize.
 * These are custom formats like [[cite:search0]], [[cite:s1r1]], etc.
 */
function handleSamCitations(text: string, opts: Required<MarkdownToSpeechOptions>): string {
    if (!opts.readCitations) {
        // Remove all SAM citation formats entirely
        let result = text.replace(/\[?\[cite:[^\]]+\]\]?/g, "");
        // Simple citations
        result = result.replace(/\[(\d+)\]/g, "");
        return result;
    }

    let result = text;

    // Handle web search format: [[cite:s1r1]], [[cite:s2r3]] (s=search turn, r=result index)
    const webSearchPattern = /\[?\[cite:s(\d+)r(\d+)\]\]?/g;
    result = result.replace(webSearchPattern, (_, searchTurn: string, resultIndex: string) => {
        return `, search ${searchTurn} result ${resultIndex},`;
    });

    // Handle SAM-style multi-citations: [[cite:search0, search1]] or [[cite:research0, cite:research1]]
    const multiCitePattern = /\[?\[cite:((?:(?:file|ref|search|research)?\d+)(?:\s*,\s*(?:cite:)?(?:file|ref|search|research)?\d+)+)\]\]?/g;
    result = result.replace(multiCitePattern, (_, content: string) => {
        const individualPattern = /(?:cite:)?(file|ref|search|research)?(\d+)/g;
        const citations: Array<[string, string]> = [];
        let match;
        while ((match = individualPattern.exec(content)) !== null) {
            citations.push([match[1] || "search", match[2]]);
        }

        if (citations.length === 0) {
            return "";
        }

        const spokenParts = citations.map(([citeType, num]) => {
            const displayNum = String(parseInt(num, 10) + 1);
            switch (citeType) {
                case "research":
                    return `research source ${displayNum}`;
                case "search":
                    return `source ${displayNum}`;
                case "file":
                    return `file ${displayNum}`;
                case "ref":
                    return `reference ${displayNum}`;
                default:
                    return `source ${displayNum}`;
            }
        });

        if (spokenParts.length === 1) {
            return `, ${spokenParts[0]},`;
        } else if (spokenParts.length === 2) {
            return `, ${spokenParts[0]} and ${spokenParts[1]},`;
        } else {
            return `, ${spokenParts.slice(0, -1).join(", ")}, and ${spokenParts[spokenParts.length - 1]},`;
        }
    });

    // Handle SAM-style single citations: [[cite:search0]], [[cite:research0]], etc.
    const samCitePattern = /\[?\[cite:(?:(file|ref|search|research))?(\d+)\]\]?/g;
    result = result.replace(samCitePattern, (_, citeType: string | undefined, num: string) => {
        const type = citeType || "search";
        const displayNum = String(parseInt(num, 10) + 1);

        let spoken: string;
        switch (type) {
            case "research":
                spoken = `research source ${displayNum}`;
                break;
            case "search":
                spoken = `source ${displayNum}`;
                break;
            case "file":
                spoken = `file ${displayNum}`;
                break;
            case "ref":
                spoken = `reference ${displayNum}`;
                break;
            default:
                spoken = `source ${displayNum}`;
        }

        return `, ${spoken},`;
    });

    // Handle simple citations [1], [2], etc. (traditional format)
    if (opts.citationFormat) {
        result = result.replace(/\[(\d+)\]/g, (_, num: string) => {
            const spoken = opts.citationFormat.replace("{n}", num);
            return `, ${spoken},`;
        });
    } else {
        result = result.replace(/\[(\d+)\]/g, "");
    }

    return result;
}

/**
 * Handle bare URLs that aren't part of markdown links.
 */
function handleBareUrls(text: string): string {
    // Match URLs that aren't already processed
    const urlPattern = /\bhttps?:\/\/[^\s<>[\]()]+/g;
    return text.replace(urlPattern, "link");
}

/**
 * Normalize whitespace for natural speech.
 */
function normalizeWhitespace(text: string): string {
    // Replace multiple newlines/spaces with single space
    let result = text.replace(/[\n\r]+/g, " ");
    result = result.replace(/ {2,}/g, " ");

    // Clean up punctuation spacing
    result = result.replace(/\s+([.,!?;:])/g, "$1");

    // Remove duplicate commas from citation handling
    result = result.replace(/,\s*,/g, ",");

    return result.trim();
}

/**
 * Decode common HTML entities.
 */
function decodeHtmlEntities(text: string): string {
    const entities: Record<string, string> = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&apos;": "'",
        "&nbsp;": " ",
        "&#39;": "'",
        "&#x27;": "'",
        "&#x2F;": "/",
    };

    let result = text;
    for (const [entity, char] of Object.entries(entities)) {
        result = result.replaceAll(entity, char);
    }

    // Handle numeric entities
    result = result.replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code, 10)));
    result = result.replace(/&#x([0-9a-fA-F]+);/g, (_, code) => String.fromCharCode(parseInt(code, 16)));

    return result;
}

/**
 * Convert markdown text to natural speech-friendly text.
 *
 * @param text - Markdown-formatted text
 * @param options - Optional configuration for conversion behavior
 * @returns Plain text suitable for TTS
 *
 * @example
 * ```ts
 * markdownToSpeech("This is **bold** text")
 * // Returns: "This is bold text"
 *
 * markdownToSpeech("Click [here](https://example.com)")
 * // Returns: "Click here"
 * ```
 */
export function markdownToSpeech(text: string, options?: MarkdownToSpeechOptions): string {
    if (!text) {
        return "";
    }

    const opts = { ...DEFAULT_OPTIONS, ...options };

    // Step 1: Handle SAM-specific citations before markdown parsing
    // (marked doesn't recognize these custom formats)
    let result = handleSamCitations(text, opts);

    // Step 2: Use marked with custom renderer to strip markdown
    const renderer = createSpeechRenderer(opts);
    result = marked(result, {
        renderer,
        async: false,
        gfm: true, // GitHub Flavored Markdown for tables, strikethrough, etc.
        breaks: false,
    }) as string;

    // Step 3: Handle bare URLs that marked might have missed
    result = handleBareUrls(result);

    // Step 4: Decode HTML entities
    result = decodeHtmlEntities(result);

    // Step 5: Normalize whitespace
    result = normalizeWhitespace(result);

    return result;
}

export default markdownToSpeech;
