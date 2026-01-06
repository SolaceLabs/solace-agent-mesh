import * as React from "react";
import { cn } from "@/lib/utils";

interface MentionContentEditableProps {
    value: string;
    onChange: (value: string) => void;
    onKeyDown?: (event: React.KeyboardEvent) => void;
    placeholder?: string;
    disabled?: boolean;
    className?: string;
    onPaste?: (event: React.ClipboardEvent) => void;
    cursorPosition?: number; // Optional cursor position to set after update
    mentionMap?: Map<string, any>; // Map of mention names to person objects
}

/**
 * ContentEditable input with visual mention chips.
 * Mentions are rendered as styled spans, while regular text is plain text nodes.
 * This avoids cursor alignment issues of overlay techniques.
 */
const MentionContentEditable = React.forwardRef<HTMLDivElement, MentionContentEditableProps>(
    (
        {
            value,
            onChange,
            onKeyDown,
            placeholder,
            disabled,
            className,
            onPaste,
            cursorPosition,
            mentionMap,
        },
        ref
    ) => {
        const editableRef = React.useRef<HTMLDivElement>(null);
        const isUpdatingRef = React.useRef(false);

        // Combine refs
        React.useImperativeHandle(ref, () => editableRef.current!);

        // Parse text and render with mention spans
        const renderContent = React.useCallback((text: string) => {
            if (!text) return "";

            // Helper to escape HTML
            const escapeHtml = (str: string) => {
                return str
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#039;')
                    .replace(/\n/g, '<br>'); // Preserve newlines as <br>
            };

            // Only render mentions that exist in mentionMap
            if (!mentionMap || mentionMap.size === 0) {
                return escapeHtml(text); // No mentions to render, but escape HTML
            }

            const parts: string[] = [];
            let lastIndex = 0;

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

            matches.forEach(match => {
                const matchStart = match.index!;
                const matchEnd = matchStart + match[0].length;

                // Add text before mention (escaped)
                if (matchStart > lastIndex) {
                    parts.push(escapeHtml(text.substring(lastIndex, matchStart)));
                }

                // Get person data for this mention
                const mentionName = match[1]; // Name without @
                const person = mentionMap.get(mentionName);

                // Add mention as a span with person data
                if (person) {
                    parts.push(
                        `<span class="mention-chip" contenteditable="false" data-mention="${match[0]}" data-person-id="${person.id}" data-person-name="${person.name}">${match[0]}</span>`
                    );
                } else {
                    parts.push(
                        `<span class="mention-chip" contenteditable="false" data-mention="${match[0]}">${match[0]}</span>`
                    );
                }

                lastIndex = matchEnd;
            });

            // Add remaining text (escaped)
            if (lastIndex < text.length) {
                parts.push(escapeHtml(text.substring(lastIndex)));
            }

            return parts.join("");
        }, [mentionMap]);

        // Extract plain text from contenteditable (convert spans back to @mentions)
        const extractPlainText = React.useCallback((element: HTMLElement): string => {
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
                        parts.push(el.getAttribute("data-mention") || el.textContent || "");
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

        // Helper to set cursor position by character offset
        const setCursorPosition = React.useCallback((offset: number) => {
            if (!editableRef.current) return;

            const selection = window.getSelection();
            if (!selection) return;

            let currentOffset = 0;
            let targetNode: Node | null = null;
            let targetOffset = 0;

            // Walk through all nodes (text and elements) to find the target position
            const walker = document.createTreeWalker(
                editableRef.current,
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
                        const mentionText = el.getAttribute("data-mention") || el.textContent || "";
                        const mentionLength = mentionText.length;

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
        const handleCopy = React.useCallback((e: React.ClipboardEvent<HTMLDivElement>) => {
            if (!editableRef.current) return;

            const selection = window.getSelection();
            if (!selection || selection.rangeCount === 0) return;

            // Get the selected HTML (includes mention spans)
            const range = selection.getRangeAt(0);
            const fragment = range.cloneContents();
            const div = document.createElement("div");
            div.appendChild(fragment);

            // Get plain text version (for cross-app compatibility)
            const plainText = extractPlainText(div);

            // Set both plain text and HTML to clipboard
            e.clipboardData?.setData("text/plain", plainText);
            e.clipboardData?.setData("text/html", div.innerHTML);
            e.preventDefault();
        }, [extractPlainText]);

        // Handle paste to preserve mentions when pasting from our own input
        const handlePaste = React.useCallback((e: React.ClipboardEvent<HTMLDivElement>) => {
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

                    // Insert the HTML using execCommand
                    document.execCommand("insertHTML", false, processedContent);
                } else {
                    // No mention chips, just insert plain text
                    document.execCommand("insertText", false, text);
                }
            }
        }, [onPaste, extractPlainText]);

        return (
            <div className="relative">
                <div
                    ref={editableRef}
                    contentEditable={!disabled}
                    onInput={handleInput}
                    onKeyDown={onKeyDown}
                    onCopy={handleCopy}
                    onPaste={handlePaste}
                    className={cn(
                        "w-full outline-none",
                        !value && placeholder ? "empty" : "",
                        disabled ? "cursor-not-allowed opacity-50" : "",
                        className
                    )}
                    data-placeholder={placeholder}
                    suppressContentEditableWarning
                    style={{
                        minHeight: "inherit",
                        maxHeight: "inherit",
                    }}
                />

                {/* Show placeholder when empty */}
                {!value && placeholder && (
                    <div className="pointer-events-none absolute inset-0 flex items-start p-3 text-[var(--muted-foreground)]">
                        {placeholder}
                    </div>
                )}
            </div>
        );
    }
);

MentionContentEditable.displayName = "MentionContentEditable";

export { MentionContentEditable };
export type { MentionContentEditableProps };
