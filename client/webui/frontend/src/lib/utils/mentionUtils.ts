import type { Person, Mention } from "@/lib/types/people";

/**
 * Internal mention format: @[Name](id)
 * This embeds the person ID in the text so we can uniquely identify each mention
 * even when multiple people have the same name.
 *
 * Display format (normal): @Name
 * Display format (disambiguated): @Name [email]
 */

/** Regex to match internal mention format: @[Name](id) */
export const INTERNAL_MENTION_REGEX = /@\[([^\]]+)\]\(([^)]+)\)/g;

/**
 * Parses a single internal mention format and returns name and id
 * Returns null if not a valid internal mention format
 */
export function parseInternalMention(text: string): { name: string; id: string } | null {
    const match = /@\[([^\]]+)\]\(([^)]+)\)/.exec(text);
    if (!match) return null;
    return { name: match[1], id: match[2] };
}

/**
 * Formats a person as internal mention format: @[Name](id)
 */
export function formatInternalMention(person: Person): string {
    return `@[${person.displayName}](${person.id})`;
}

/**
 * Detects if cursor is in a mention trigger position
 * Returns the query string after "@" or null if not in mention mode
 * Updated to handle internal format - doesn't trigger inside @[...](...)
 */
export function detectMentionTrigger(text: string, cursorPosition: number): string | null {
    const textBeforeCursor = text.substring(0, cursorPosition);

    // Find the last "@" before cursor
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");
    if (lastAtIndex === -1) return null;

    // Check if "@" is at start or preceded by whitespace/newline
    const charBeforeAt = lastAtIndex > 0 ? textBeforeCursor[lastAtIndex - 1] : " ";
    if (charBeforeAt !== " " && charBeforeAt !== "\n") return null;

    // Check if this @ is part of an internal mention format @[...](...)
    // If the character after @ is '[', it's an existing mention, not a trigger
    const charAfterAt = lastAtIndex < text.length - 1 ? text[lastAtIndex + 1] : "";
    if (charAfterAt === "[") return null;

    // Extract query after "@"
    const query = textBeforeCursor.substring(lastAtIndex + 1);

    // Check if query contains spaces or newlines (mention should be contiguous)
    if (query.includes(" ") || query.includes("\n")) return null;

    return query;
}

/**
 * Formats a person as a mention display string (for UI display)
 * Example: "@Edward Funnekotter"
 */
export function formatMentionDisplay(person: Person): string {
    return `@${person.displayName}`;
}

/**
 * Formats a person as a disambiguated mention display string
 * Used when multiple people have the same name
 * Example: "@John Smith [john.smith@example.com]"
 */
export function formatDisambiguatedMentionDisplay(person: Person): string {
    const disambiguator = person.workEmail || person.id;
    return `@${person.displayName} [${disambiguator}]`;
}

/**
 * Gets the display name for rendering, with optional disambiguation
 * @param person The person to display
 * @param disambiguate Whether to show disambiguation (email/id)
 * @returns Display string like "@John Doe" or "@John Doe [email]"
 */
export function getDisplayText(person: Person, disambiguate: boolean): string {
    if (disambiguate) {
        return formatDisambiguatedMentionDisplay(person);
    }
    return formatMentionDisplay(person);
}

/**
 * Formats a person as the backend expects: "displayName <user_id:id>"
 * Example: "Edward Funnekotter <user_id:edward.funnekotter@solace.com>"
 */
export function formatMentionForBackend(person: Person): string {
    return `${person.displayName} <user_id:${person.id}>`;
}

/**
 * Replaces a mention trigger (@query) in text with the selected person
 * Uses internal format: @[Name](id)
 * Returns new text and new cursor position
 */
export function insertMention(text: string, cursorPosition: number, person: Person): { newText: string; newCursorPosition: number } {
    const textBeforeCursor = text.substring(0, cursorPosition);
    const textAfterCursor = text.substring(cursorPosition);

    // Find the "@" that triggered this mention
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");

    // Use internal format with embedded ID
    const mentionInternal = formatInternalMention(person);
    const beforeMention = text.substring(0, lastAtIndex);
    const newText = beforeMention + mentionInternal + " " + textAfterCursor;
    const newCursorPosition = (beforeMention + mentionInternal + " ").length;

    return { newText, newCursorPosition };
}

/**
 * Extracts all internal mentions from text
 * Returns array of {name, id, startIndex, endIndex}
 */
export function extractInternalMentions(text: string): Array<{
    name: string;
    id: string;
    startIndex: number;
    endIndex: number;
    fullMatch: string;
}> {
    const mentions: Array<{
        name: string;
        id: string;
        startIndex: number;
        endIndex: number;
        fullMatch: string;
    }> = [];

    const regex = new RegExp(INTERNAL_MENTION_REGEX.source, "g");
    let match;
    while ((match = regex.exec(text)) !== null) {
        mentions.push({
            name: match[1],
            id: match[2],
            startIndex: match.index,
            endIndex: match.index + match[0].length,
            fullMatch: match[0],
        });
    }

    return mentions;
}

/**
 * Converts internal mention format to plain text for display/copying
 * @[Name](id) -> @Name
 */
export function internalToDisplayText(text: string): string {
    return text.replace(INTERNAL_MENTION_REGEX, "@$1");
}

/**
 * Extracts display text from HTML, preserving @mention format instead of backend format
 * This is used for copying user messages to clipboard
 */
export function extractDisplayTextFromHTML(html: string): string {
    // Create a temporary div to parse the HTML
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = html;

    // Walk through the DOM and build plain text
    const walker = document.createTreeWalker(tempDiv, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
        acceptNode: (node: Node) => {
            // Skip text nodes that are children of mention-chip spans
            if (node.nodeType === Node.TEXT_NODE) {
                const parent = node.parentElement;
                if (parent && parent.classList.contains("mention-chip")) {
                    return NodeFilter.FILTER_REJECT;
                }
            }
            return NodeFilter.FILTER_ACCEPT;
        },
    });

    const parts: string[] = [];
    let node: Node | null;

    while ((node = walker.nextNode())) {
        if (node.nodeType === Node.TEXT_NODE) {
            parts.push(node.textContent || "");
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const el = node as HTMLElement;
            if (el.classList.contains("mention-chip")) {
                // Use the data-display attribute which has the @Name format
                parts.push(el.getAttribute("data-display") || el.textContent || "");
            } else if (el.tagName === "BR") {
                parts.push("\n");
            }
        }
    }

    return parts.join("");
}

/**
 * Extracts mentions from a contenteditable element's DOM
 * Returns a map of person ID to Person object
 */
export function extractMentionsFromDOM(element: HTMLElement): Map<string, Person> {
    const mentionMap = new Map<string, Person>();

    // Find all mention-chip spans
    const mentionChips = element.querySelectorAll(".mention-chip");

    mentionChips.forEach(chip => {
        const personId = chip.getAttribute("data-person-id");
        const personName = chip.getAttribute("data-person-name");

        if (personId && personName) {
            // Key by ID for uniqueness
            mentionMap.set(personId, {
                id: personId,
                displayName: personName,
                workEmail: personId, // Assuming ID is email
            });
        }
    });

    return mentionMap;
}

/**
 * Builds the backend message by walking the DOM and converting mention chips
 * This is more reliable than regex parsing because it uses the actual DOM structure
 */
export function buildMessageFromDOM(element: HTMLElement): string {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
        acceptNode: (node: Node) => {
            // Skip text nodes that are children of mention-chip spans
            if (node.nodeType === Node.TEXT_NODE) {
                const parent = node.parentElement;
                if (parent && parent.classList.contains("mention-chip")) {
                    return NodeFilter.FILTER_REJECT;
                }
            }
            return NodeFilter.FILTER_ACCEPT;
        },
    });

    const parts: string[] = [];
    let node: Node | null;

    while ((node = walker.nextNode())) {
        if (node.nodeType === Node.TEXT_NODE) {
            parts.push(node.textContent || "");
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const el = node as HTMLElement;
            if (el.classList.contains("mention-chip")) {
                const personId = el.getAttribute("data-person-id");
                const personName = el.getAttribute("data-person-name");

                if (personId && personName) {
                    // Convert to backend format: "Name <user_id:id>"
                    parts.push(`${personName} <user_id:${personId}>`);
                } else {
                    // Fallback: just use the display text
                    parts.push(el.getAttribute("data-display") || el.textContent || "");
                }
            } else if (el.tagName === "BR") {
                parts.push("\n");
            }
        }
    }

    return parts.join("");
}

/**
 * Extracts all mentions from text as structured data
 */
export function extractMentions(text: string): Mention[] {
    const mentions: Mention[] = [];
    const internalMentions = extractInternalMentions(text);

    for (const m of internalMentions) {
        mentions.push({
            id: m.id,
            name: m.name,
            startIndex: m.startIndex,
            endIndex: m.endIndex,
        });
    }

    return mentions;
}
