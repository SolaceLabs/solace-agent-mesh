import * as React from "react";
import DOMPurify from "dompurify";
import { cn } from "@/lib/utils";
import type { Person } from "@/lib/types/people";
import { getDisplayText, INTERNAL_MENTION_REGEX } from "@/lib/utils/mentionUtils";

interface MentionContentEditableProps {
    value: string; // Internal format with @[Name](id)
    onChange: (value: string) => void;
    onKeyDown?: (event: React.KeyboardEvent) => void;
    placeholder?: string;
    disabled?: boolean;
    className?: string;
    onPaste?: (event: React.ClipboardEvent) => void;
    cursorPosition?: number; // Optional cursor position to set after update
    mentionMap?: Map<string, Person>; // Map of person ID to Person object
    disambiguatedIds?: Set<string>; // IDs that need disambiguation display
}

/**
 * ContentEditable input with visual mention chips.
 * Internal format: @[Name](id) - stores person ID for unique identification
 * Display format: @Name or @Name [email] (when disambiguated)
 */
const MentionContentEditable = React.forwardRef<HTMLDivElement, MentionContentEditableProps>(({ value, onChange, onKeyDown, placeholder, disabled, className, onPaste, cursorPosition, mentionMap, disambiguatedIds }, ref) => {
    const editableRef = React.useRef<HTMLDivElement>(null);
    const isUpdatingRef = React.useRef(false);

    // Combine refs
    React.useImperativeHandle(ref, () => editableRef.current!);

    // Helper to escape HTML
    const escapeHtml = React.useCallback((str: string) => {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;").replace(/\n/g, "<br>"); // Preserve newlines as <br>
    }, []);

    // Parse internal format @[Name](id) and render with mention spans
    const renderContent = React.useCallback(
        (text: string) => {
            if (!text) return "";

            const parts: string[] = [];
            let lastIndex = 0;

            // Match internal mention format: @[Name](id)
            const regex = new RegExp(INTERNAL_MENTION_REGEX.source, "g");
            let match;

            while ((match = regex.exec(text)) !== null) {
                const matchStart = match.index;
                const matchEnd = matchStart + match[0].length;
                const name = match[1];
                const id = match[2];

                // Add text before mention (escaped)
                if (matchStart > lastIndex) {
                    parts.push(escapeHtml(text.substring(lastIndex, matchStart)));
                }

                // Get person data from mentionMap (keyed by ID)
                const person = mentionMap?.get(id);

                // Check if this person needs disambiguation
                const needsDisambiguation = disambiguatedIds?.has(id) ?? false;

                // Determine display text
                let displayText: string;
                if (person) {
                    displayText = getDisplayText(person, needsDisambiguation);
                } else {
                    // Fallback if person not in map
                    displayText = `@${name}`;
                }

                // Create mention chip with data attributes
                // data-internal stores the internal format for extraction
                parts.push(
                    `<span class="mention-chip" contenteditable="false" ` +
                        `data-internal="${escapeHtml(match[0])}" ` +
                        `data-person-id="${escapeHtml(id)}" ` +
                        `data-person-name="${escapeHtml(name)}" ` +
                        `data-display="${escapeHtml(displayText)}"` +
                        `>${escapeHtml(displayText)}</span>`
                );

                lastIndex = matchEnd;
            }

            // Add remaining text (escaped)
            if (lastIndex < text.length) {
                parts.push(escapeHtml(text.substring(lastIndex)));
            }

            return parts.join("");
        },
        [mentionMap, disambiguatedIds, escapeHtml]
    );

    // Extract internal format from contenteditable (convert spans back to @[Name](id))
    const extractPlainText = React.useCallback((element: HTMLElement): string => {
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
                    // Use the internal format stored in data-internal
                    const internal = el.getAttribute("data-internal");
                    if (internal) {
                        parts.push(internal);
                    } else {
                        // Fallback: reconstruct from data attributes
                        const personId = el.getAttribute("data-person-id");
                        const personName = el.getAttribute("data-person-name");
                        if (personId && personName) {
                            parts.push(`@[${personName}](${personId})`);
                        } else {
                            // Last resort: just use display text
                            parts.push(el.textContent || "");
                        }
                    }
                } else if (el.tagName === "BR") {
                    parts.push("\n");
                }
            }
        }

        return parts.join("");
    }, []);

    // Handle input changes
    const handleInput = React.useCallback(() => {
        if (isUpdatingRef.current || !editableRef.current) return;

        const plainText = extractPlainText(editableRef.current);
        onChange(plainText);
    }, [onChange, extractPlainText]);

    // Helper to set cursor position by character offset (in internal format)
    const setCursorPosition = React.useCallback((offset: number) => {
        if (!editableRef.current) return;

        const selection = window.getSelection();
        if (!selection) return;

        let currentOffset = 0;
        let targetNode: Node | null = null;
        let targetOffset = 0;

        // Walk through all nodes (text and elements) to find the target position
        const walker = document.createTreeWalker(editableRef.current, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
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

        let node: Node | null;
        while ((node = walker.nextNode())) {
            if (node.nodeType === Node.TEXT_NODE) {
                const nodeLength = node.textContent?.length || 0;
                if (currentOffset + nodeLength >= offset) {
                    targetNode = node;
                    targetOffset = offset - currentOffset;
                    break;
                }
                currentOffset += nodeLength;
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                const el = node as HTMLElement;
                if (el.classList.contains("mention-chip")) {
                    // Use internal format length for cursor positioning
                    const internal = el.getAttribute("data-internal") || "";
                    const mentionLength = internal.length;

                    if (currentOffset + mentionLength > offset) {
                        // Cursor is within this mention (not at the end)
                        // Position after the mention span
                        targetNode = el.nextSibling || el.parentNode;
                        targetOffset = el.nextSibling?.nodeType === Node.TEXT_NODE ? 0 : 0;

                        // If no next sibling, we need to position after this element
                        if (!el.nextSibling) {
                            targetNode = el.parentNode;
                            targetOffset = Array.from(el.parentNode?.childNodes || []).indexOf(el) + 1;
                        }
                        break;
                    }
                    currentOffset += mentionLength;
                } else if (el.tagName === "BR") {
                    // BR represents a newline
                    if (currentOffset + 1 > offset) {
                        // Position before the BR
                        targetNode = el.parentNode;
                        targetOffset = Array.from(el.parentNode?.childNodes || []).indexOf(el);
                        break;
                    }
                    currentOffset += 1;
                }
            }
        }

        // Set the cursor
        try {
            if (targetNode) {
                const range = document.createRange();
                range.setStart(targetNode, targetOffset);
                range.collapse(true);
                selection.removeAllRanges();
                selection.addRange(range);
            } else {
                // Fallback: position at the end
                const range = document.createRange();
                range.selectNodeContents(editableRef.current);
                range.collapse(false);
                selection.removeAllRanges();
                selection.addRange(range);
            }
        } catch {
            // Final fallback: just focus the element
            editableRef.current?.focus();
        }
    }, []);

    // Update content when value prop changes (from parent)
    React.useEffect(() => {
        if (!editableRef.current || isUpdatingRef.current) {
            return;
        }

        const currentPlainText = extractPlainText(editableRef.current);

        // Only update if content actually changed
        if (currentPlainText !== value) {
            isUpdatingRef.current = true;

            // Update content
            editableRef.current.innerHTML = renderContent(value);

            // Set cursor position after update
            setTimeout(() => {
                if (cursorPosition !== undefined) {
                    setCursorPosition(cursorPosition);
                }
                isUpdatingRef.current = false;
            }, 0);
        }
    }, [value, renderContent, extractPlainText, setCursorPosition, cursorPosition]);

    // Handle copy to preserve mention information
    const handleCopy = React.useCallback(
        (e: React.ClipboardEvent<HTMLDivElement>) => {
            if (!editableRef.current) return;

            const selection = window.getSelection();
            if (!selection || selection.rangeCount === 0) return;

            // Get the selected HTML (includes mention spans)
            const range = selection.getRangeAt(0);
            const fragment = range.cloneContents();
            const div = document.createElement("div");
            div.appendChild(fragment);

            // Get internal format for our own paste handling
            const internalText = extractPlainText(div);

            // Get display text for cross-app compatibility (convert @[Name](id) to @Name)
            const displayText = internalText.replace(INTERNAL_MENTION_REGEX, "@$1");

            // Set both plain text and HTML to clipboard
            e.clipboardData?.setData("text/plain", displayText);
            e.clipboardData?.setData("text/html", div.innerHTML);
            e.preventDefault();
        },
        [extractPlainText]
    );

    // Handle paste to preserve mentions when pasting from our own input
    const handlePaste = React.useCallback(
        (e: React.ClipboardEvent<HTMLDivElement>) => {
            // First, call the parent's onPaste handler if provided
            // This handles file pastes and large text detection
            // Pass the original event so preventDefault() works correctly
            if (onPaste) {
                onPaste(e);
            }

            // If the parent didn't prevent default, handle paste
            if (!e.defaultPrevented) {
                e.preventDefault();

                // Try to get HTML first (preserves mention chips)
                const html = e.clipboardData.getData("text/html");
                const text = e.clipboardData.getData("text/plain");

                if (html && html.includes("mention-chip")) {
                    // HTML contains our mention chips, insert it directly
                    // But we need to extract just the mention spans and text, not full HTML structure
                    const tempDiv = document.createElement("div");
                    tempDiv.innerHTML = html;

                    // Extract mention chips and text nodes
                    const processedContent = Array.from(tempDiv.childNodes)
                        .map(node => {
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                const el = node as HTMLElement;
                                if (el.classList.contains("mention-chip")) {
                                    // Preserve the mention chip
                                    return el.outerHTML;
                                }
                            }
                            return node.textContent || "";
                        })
                        .join("");

                    // Sanitize the HTML to prevent XSS attacks
                    // Only allow mention chip spans with specific data attributes
                    const sanitizedContent = DOMPurify.sanitize(processedContent, {
                        ALLOWED_TAGS: ["span", "br"],
                        ALLOWED_ATTR: ["class", "contenteditable", "data-internal", "data-person-id", "data-person-name", "data-display"],
                    });

                    // Insert the sanitized HTML using execCommand
                    document.execCommand("insertHTML", false, sanitizedContent);
                } else {
                    // No mention chips, just insert plain text
                    document.execCommand("insertText", false, text);
                }
            }
        },
        [onPaste]
    );

    return (
        <div className="relative">
            <div
                ref={editableRef}
                contentEditable={!disabled}
                onInput={handleInput}
                onKeyDown={onKeyDown}
                onCopy={handleCopy}
                onPaste={handlePaste}
                className={cn("w-full outline-none", !value && placeholder ? "empty" : "", disabled ? "cursor-not-allowed opacity-50" : "", className)}
                data-testid="chat-input"
                data-placeholder={placeholder}
                suppressContentEditableWarning
                style={{
                    minHeight: "inherit",
                    maxHeight: "inherit",
                }}
            />

            {/* Show placeholder when empty */}
            {!value && placeholder && <div className="pointer-events-none absolute inset-0 flex items-start p-3 text-[var(--muted-foreground)]">{placeholder}</div>}
        </div>
    );
});

MentionContentEditable.displayName = "MentionContentEditable";

export { MentionContentEditable };
export type { MentionContentEditableProps };
