import type { Person, Mention } from "@/lib/types/people";

/**
 * Detects if cursor is in a mention trigger position
 * Returns the query string after "@" or null if not in mention mode
 */
export function detectMentionTrigger(
    text: string,
    cursorPosition: number
): string | null {
    const textBeforeCursor = text.substring(0, cursorPosition);

    // Find the last "@" before cursor
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");
    if (lastAtIndex === -1) return null;

    // Check if "@" is at start or preceded by whitespace/newline
    const charBeforeAt = lastAtIndex > 0 ? textBeforeCursor[lastAtIndex - 1] : " ";
    if (charBeforeAt !== " " && charBeforeAt !== "\n") return null;

    // Extract query after "@"
    const query = textBeforeCursor.substring(lastAtIndex + 1);

    // Check if query contains spaces or newlines (mention should be contiguous)
    if (query.includes(" ") || query.includes("\n")) return null;

    return query;
}

/**
 * Formats a person as a mention display string
 * Example: "@Edward Funnekotter"
 */
export function formatMentionDisplay(person: Person): string {
    return `@${person.name}`;
}

/**
 * Formats a person as the backend expects: "name <id:id>"
 * Example: "Edward Funnekotter <id:edward.funnekotter@solace.com>"
 */
export function formatMentionForBackend(person: Person): string {
    return `${person.name} <id:${person.id}>`;
}

/**
 * Replaces a mention trigger in text with the selected person
 * Returns new text and new cursor position
 */
export function insertMention(
    text: string,
    cursorPosition: number,
    person: Person
): { newText: string; newCursorPosition: number } {
    const textBeforeCursor = text.substring(0, cursorPosition);
    const textAfterCursor = text.substring(cursorPosition);

    // Find the "@" that triggered this mention
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");

    const mentionDisplay = formatMentionDisplay(person);
    const beforeMention = text.substring(0, lastAtIndex);
    const newText = beforeMention + mentionDisplay + " " + textAfterCursor;
    const newCursorPosition = (beforeMention + mentionDisplay + " ").length;

    return { newText, newCursorPosition };
}

/**
 * Parses mentions from input text and converts to backend format
 * Converts "@Name" to "Name <id:email>" using a map of known mentions
 */
export function parseMentionsForSubmit(
    text: string,
    mentionMap: Map<string, Person>
): string {
    let result = text;

    if (mentionMap.size === 0) {
        return result; // No mentions to process
    }

    // Build a regex that matches exact mention names from the map
    // Sort by length (longest first) to match longer names before shorter ones
    const mentionNames = Array.from(mentionMap.keys()).sort((a, b) => b.length - a.length);

    // Escape special regex characters in names
    const escapedNames = mentionNames.map(name =>
        name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    );

    // Match @Name where Name is one of our known mentions
    // Must be followed by space, newline, or end of string
    const mentionRegex = new RegExp(`@(${escapedNames.join('|')})(?=\\s|$)`, 'g');
    const matches = Array.from(text.matchAll(mentionRegex));

    // Process in reverse order to maintain string indices
    for (let i = matches.length - 1; i >= 0; i--) {
        const match = matches[i];
        const displayName = match[1];
        const fullMatch = match[0]; // "@Name"
        const startIndex = match.index!;

        // Look up person by display name
        const person = mentionMap.get(displayName);
        if (person) {
            const backendFormat = formatMentionForBackend(person);
            result = result.substring(0, startIndex) +
                     backendFormat +
                     result.substring(startIndex + fullMatch.length);
        }
    }

    return result;
}

/**
 * Extracts display text from HTML, preserving @mention format instead of backend format
 * This is used for copying user messages to clipboard
 */
export function extractDisplayTextFromHTML(html: string): string {
    // Create a temporary div to parse the HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;

    // Walk through the DOM and build plain text
    const walker = document.createTreeWalker(
        tempDiv,
        NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
        {
            acceptNode: (node: Node) => {
                // Skip text nodes that are children of mention-chip spans
                if (node.nodeType === Node.TEXT_NODE) {
                    const parent = node.parentElement;
                    if (parent && parent.classList.contains("mention-chip")) {
                        return NodeFilter.FILTER_REJECT;
                    }
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        }
    );

    const parts: string[] = [];
    let node: Node | null;

    while ((node = walker.nextNode())) {
        if (node.nodeType === Node.TEXT_NODE) {
            parts.push(node.textContent || "");
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const el = node as HTMLElement;
            if (el.classList.contains("mention-chip")) {
                // Use the data-mention attribute which has the @Name format
                parts.push(el.getAttribute('data-mention') || el.textContent || "");
            } else if (el.tagName === "BR") {
                parts.push("\n");
            }
        }
    }

    return parts.join("");
}

/**
 * Extracts mentions from a contenteditable element's DOM
 * This handles mentions that were pasted (and have data-person-id attributes)
 * Returns a map of mention names to person objects
 */
export function extractMentionsFromDOM(element: HTMLElement): Map<string, Person> {
    const mentionMap = new Map<string, Person>();

    // Find all mention-chip spans
    const mentionChips = element.querySelectorAll('.mention-chip');

    mentionChips.forEach(chip => {
        const personId = chip.getAttribute('data-person-id');
        const personName = chip.getAttribute('data-person-name');
        const mention = chip.getAttribute('data-mention');

        if (personId && personName && mention) {
            // Extract the name without @ symbol
            const displayName = mention.startsWith('@') ? mention.substring(1) : mention;

            // Create a minimal Person object
            mentionMap.set(displayName, {
                id: personId,
                name: personName,
                email: personId, // Assuming ID is email, adjust if needed
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
    const walker = document.createTreeWalker(
        element,
        NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
        {
            acceptNode: (node: Node) => {
                // Skip text nodes that are children of mention-chip spans
                if (node.nodeType === Node.TEXT_NODE) {
                    const parent = node.parentElement;
                    if (parent && parent.classList.contains("mention-chip")) {
                        return NodeFilter.FILTER_REJECT;
                    }
                }
                return NodeFilter.FILTER_ACCEPT;
            }
        }
    );

    const parts: string[] = [];
    let node: Node | null;

    while ((node = walker.nextNode())) {
        if (node.nodeType === Node.TEXT_NODE) {
            parts.push(node.textContent || "");
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            const el = node as HTMLElement;
            if (el.classList.contains("mention-chip")) {
                const personId = el.getAttribute('data-person-id');
                const personName = el.getAttribute('data-person-name');

                if (personId && personName) {
                    // Convert to backend format: "Name <id:email>"
                    parts.push(`${personName} <id:${personId}>`);
                } else {
                    // Fallback: just use the mention text as-is
                    parts.push(el.getAttribute('data-mention') || el.textContent || "");
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
    const mentionRegex = /@([^\s@]+(?:\s+[^\s@]+)*)/g;

    let match;
    while ((match = mentionRegex.exec(text)) !== null) {
        mentions.push({
            id: "", // Will be filled when person is selected
            name: match[1],
            startIndex: match.index,
            endIndex: match.index + match[0].length
        });
    }

    return mentions;
}
