/**
 * Markdown to Speech Preprocessor
 *
 * Converts markdown-formatted text to natural, speakable text suitable for
 * Text-to-Speech (TTS) engines. Removes markdown syntax while preserving
 * the semantic meaning of the content.
 *
 * This is the frontend version that mirrors the backend Python implementation
 * for use with browser-based TTS.
 */

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
 * Convert markdown text to natural speech-friendly text.
 *
 * This function removes markdown syntax while preserving the semantic
 * meaning of the content, making it suitable for TTS engines.
 *
 * @param text - Markdown-formatted text
 * @param options - Optional configuration for conversion behavior
 * @returns Plain text suitable for TTS
 */
export function markdownToSpeech(text: string, options?: MarkdownToSpeechOptions): string {
    if (!text) {
        return "";
    }

    const opts = { ...DEFAULT_OPTIONS, ...options };
    let result = text;

    // Step 1: Handle code blocks (``` ... ```)
    result = handleCodeBlocks(result, opts);

    // Step 2: Handle inline code (`code`)
    result = handleInlineCode(result);

    // Step 3: Handle images ![alt](url)
    result = handleImages(result, opts);

    // Step 4: Handle links [text](url)
    result = handleLinks(result);

    // Step 5: Handle reference-style links [text][ref] and [ref]: url
    result = handleReferenceLinks(result);

    // Step 6: Handle bold and italic
    result = handleEmphasis(result);

    // Step 7: Handle headers
    result = handleHeaders(result, opts);

    // Step 8: Handle blockquotes
    result = handleBlockquotes(result);

    // Step 9: Handle horizontal rules
    result = handleHorizontalRules(result);

    // Step 10: Handle lists (unordered and ordered)
    result = handleLists(result);

    // Step 11: Handle citations [1], [2], etc.
    result = handleCitations(result, opts);

    // Step 12: Handle tables (basic - just extract text)
    result = handleTables(result);

    // Step 13: Strip HTML tags
    result = stripHtmlTags(result);

    // Step 14: Decode HTML entities
    result = decodeHtmlEntities(result);

    // Step 15: Handle bare URLs
    result = handleBareUrls(result);

    // Step 16: Normalize whitespace
    result = normalizeWhitespace(result);

    return result.trim();
}

function handleCodeBlocks(text: string, opts: Required<MarkdownToSpeechOptions>): string {
    // Match ```language\ncode\n``` or ```\ncode\n```
    const pattern = /```[\w]*\n?[\s\S]*?```/g;

    if (opts.readCodeBlocks) {
        return text.replace(pattern, ` ${opts.codeBlockPrefix} `);
    } else {
        return text.replace(pattern, " ");
    }
}

function handleInlineCode(text: string): string {
    // Match `code` but not inside code blocks (already handled)
    return text.replace(/`([^`]+)`/g, "$1");
}

function handleImages(text: string, opts: Required<MarkdownToSpeechOptions>): string {
    if (opts.readImages) {
        return text.replace(/!\[([^\]]*)\]\([^)]+\)/g, (_, altText: string) => {
            const trimmedAlt = altText.trim();
            if (trimmedAlt) {
                return ` ${opts.imagePrefix} ${trimmedAlt}. `;
            }
            return " ";
        });
    } else {
        return text.replace(/!\[([^\]]*)\]\([^)]+\)/g, " ");
    }
}

function handleLinks(text: string): string {
    // Keep the link text, remove the URL
    return text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
}

function handleReferenceLinks(text: string): string {
    // Remove reference definitions [ref]: url
    let result = text.replace(/^\s*\[[^\]]+\]:\s*\S+.*$/gm, "");

    // Convert [text][ref] to just text
    result = result.replace(/\[([^\]]+)\]\[[^\]]*\]/g, "$1");

    return result;
}

function handleEmphasis(text: string): string {
    // Bold: **text** or __text__
    let result = text.replace(/\*\*([^*]+)\*\*/g, "$1");
    result = result.replace(/__([^_]+)__/g, "$1");

    // Italic: *text* or _text_ (but not inside words like snake_case)
    result = result.replace(/\*([^*]+)\*/g, "$1");
    result = result.replace(/(?<!\w)_([^_]+)_(?!\w)/g, "$1");

    // Strikethrough: ~~text~~
    result = result.replace(/~~([^~]+)~~/g, "$1");

    return result;
}

function handleHeaders(text: string, opts: Required<MarkdownToSpeechOptions>): string {
    // Handle headers at start of line
    let result = text.replace(/^(#{1,6})\s+(.+)$/gm, (_, _hashes: string, headerText: string) => {
        const trimmed = headerText.trim();
        if (opts.addHeaderPauses) {
            return `${trimmed}. `;
        }
        return `${trimmed} `;
    });

    // Handle setext-style headers (underlined with === or ---)
    result = result.replace(/^(.+)\n[=]+\s*$/gm, "$1. ");
    result = result.replace(/^(.+)\n[-]+\s*$/gm, "$1. ");

    return result;
}

function handleBlockquotes(text: string): string {
    // Remove > at the start of lines
    return text.replace(/^>\s*/gm, "");
}

function handleHorizontalRules(text: string): string {
    // Match ---, ***, ___ (3 or more)
    return text.replace(/^[-*_]{3,}\s*$/gm, " ");
}

function handleLists(text: string): string {
    // Unordered lists: -, *, +
    let result = text.replace(/^[\s]*[-*+]\s+/gm, "");

    // Ordered lists: 1., 2., etc. - keep the number for context
    result = result.replace(/^[\s]*(\d+)\.\s+/gm, "$1, ");

    return result;
}

function handleCitations(text: string, opts: Required<MarkdownToSpeechOptions>): string {
    /**
     * Handle citation references in various formats:
     * - Simple: [1], [2], etc.
     * - SAM cite format: [[cite:search0]], [[cite:research0]], [[cite:file0]], [[cite:ref0]]
     * - Web search format: [[cite:s1r1]], [[cite:s2r3]] (s=search turn, r=result index)
     * - Multi-citations: [[cite:search0, search1, search2]] or [[cite:research0, cite:research1]]
     * - Single bracket variants: [cite:search0]
     */
    if (!opts.readCitations) {
        // Remove all citation formats entirely
        // Multi-citation pattern first (to avoid partial matches)
        let result = text.replace(/\[?\[cite:[^\]]+\]\]?/g, "");
        // Simple citations
        result = result.replace(/\[(\d+)\]/g, "");
        return result;
    }

    let result = text;

    // Handle web search format: [[cite:s1r1]], [[cite:s2r3]] (s=search turn, r=result index)
    // This must come BEFORE the general SAM citation pattern to avoid conflicts
    const webSearchPattern = /\[?\[cite:s(\d+)r(\d+)\]\]?/g;
    result = result.replace(webSearchPattern, (_, searchTurn: string, resultIndex: string) => {
        // Keep as-is since they're already 1-indexed
        return `, search ${searchTurn} result ${resultIndex},`;
    });

    // Handle SAM-style multi-citations: [[cite:search0, search1]] or [[cite:research0, cite:research1]]
    const multiCitePattern = /\[?\[cite:((?:(?:file|ref|search|research)?\d+)(?:\s*,\s*(?:cite:)?(?:file|ref|search|research)?\d+)+)\]\]?/g;
    result = result.replace(multiCitePattern, (_, content: string) => {
        // Extract individual citation numbers
        const individualPattern = /(?:cite:)?(file|ref|search|research)?(\d+)/g;
        const citations: Array<[string, string]> = [];
        let match;
        while ((match = individualPattern.exec(content)) !== null) {
            citations.push([match[1] || "search", match[2]]);
        }

        if (citations.length === 0) {
            return "";
        }

        // Build spoken text for each citation
        const spokenParts = citations.map(([citeType, num]) => {
            // Convert 0-indexed to 1-indexed for natural speech
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
            // Join with commas and "and" for last item
            return `, ${spokenParts.slice(0, -1).join(", ")}, and ${spokenParts[spokenParts.length - 1]},`;
        }
    });

    // Handle SAM-style single citations: [[cite:search0]], [[cite:research0]], etc.
    const samCitePattern = /\[?\[cite:(?:(file|ref|search|research))?(\d+)\]\]?/g;
    result = result.replace(samCitePattern, (_, citeType: string | undefined, num: string) => {
        const type = citeType || "search"; // Default to search if no type
        // Convert 0-indexed to 1-indexed for natural speech
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

function handleTables(text: string): string {
    const lines = text.split("\n");
    const resultLines: string[] = [];

    for (const line of lines) {
        // Skip separator lines (|---|---|)
        if (/^\s*\|[\s\-:|]+\|\s*$/.test(line)) {
            continue;
        }

        // Extract cell content from table rows
        if (line.includes("|")) {
            const cells = line
                .trim()
                .replace(/^\||\|$/g, "")
                .split("|");
            const cellText = cells
                .map(cell => cell.trim())
                .filter(cell => cell)
                .join(" ");
            resultLines.push(cellText);
        } else {
            resultLines.push(line);
        }
    }

    return resultLines.join("\n");
}

function stripHtmlTags(text: string): string {
    // Remove HTML comments
    let result = text.replace(/<!--[\s\S]*?-->/g, "");

    // Remove HTML tags but keep content
    result = result.replace(/<[^>]+>/g, "");

    return result;
}

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
        "&#60;": "<",
        "&#62;": ">",
    };

    let result = text;
    for (const [entity, char] of Object.entries(entities)) {
        result = result.replace(new RegExp(entity, "g"), char);
    }

    // Handle numeric entities
    result = result.replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code, 10)));
    result = result.replace(/&#x([0-9a-fA-F]+);/g, (_, code) => String.fromCharCode(parseInt(code, 16)));

    return result;
}

function handleBareUrls(text: string): string {
    // Match URLs that aren't part of markdown links
    // eslint-disable-next-line no-useless-escape
    const urlPattern = /(?<!\()\b(https?:\/\/[^\s<>\[\]()]+)/g;
    return text.replace(urlPattern, "link");
}

function normalizeWhitespace(text: string): string {
    // Replace multiple newlines with single space
    let result = text.replace(/\n{2,}/g, " ");

    // Replace single newlines with space
    result = result.replace(/\n/g, " ");

    // Replace multiple spaces with single space
    result = result.replace(/ {2,}/g, " ");

    // Clean up punctuation spacing
    result = result.replace(/\s+([.,!?;:])/g, "$1");

    // Remove spaces before commas that we added for citations
    result = result.replace(/\s*,\s*,/g, ",");

    return result;
}

export default markdownToSpeech;
