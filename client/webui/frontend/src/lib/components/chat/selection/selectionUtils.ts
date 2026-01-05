/**
 * Gets the currently selected text from the browser's selection API
 */
export function getSelectedText(): string | null {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
        return null;
    }
    const text = selection.toString().trim();
    return text || null;
}

/**
 * Gets the current selection range
 */
export function getSelectionRange(): Range | null {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
        return null;
    }
    return selection.getRangeAt(0);
}

/**
 * Gets the bounding rectangle of the current selection
 */
export function getSelectionBoundingRect(): DOMRect | null {
    const range = getSelectionRange();
    if (!range) {
        return null;
    }
    return range.getBoundingClientRect();
}

/**
 * Calculates the optimal position for the context menu based on selection bounds
 * Ensures the menu stays within viewport boundaries
 */
export function calculateMenuPosition(rect: DOMRect): { x: number; y: number } {
    const menuWidth = 160; // Approximate menu width (matches max-w-[160px])
    const menuHeight = 40; // Approximate menu height for single button
    const padding = 8;

    // Position at the left edge of the selection
    let x = rect.left;
    // Position above the selection
    let y = rect.top - menuHeight - padding;

    // Adjust if menu would go off right edge
    if (x + menuWidth > window.innerWidth) {
        x = window.innerWidth - menuWidth - padding;
    }

    // Adjust if menu would go off left edge
    if (x < padding) {
        x = padding;
    }

    // If menu would go off top, show below selection instead
    if (y < padding) {
        y = rect.bottom + padding;
    }

    return { x, y };
}

/**
 * Maximum character limit for text selection in "Ask Followup" feature.
 * This prevents users from selecting excessively large amounts of text
 * which could subvert the pasted text flow and lead to very large prompts.
 */
export const MAX_SELECTION_LENGTH = 5000;

/**
 * Validates if a selection is meaningful (not just whitespace, meets minimum length,
 * and doesn't exceed maximum length)
 */
export function isValidSelection(text: string | null): boolean {
    if (!text) {
        return false;
    }
    const trimmed = text.trim();
    return trimmed.length >= 3 && trimmed.length <= MAX_SELECTION_LENGTH && /\S/.test(trimmed);
}

/**
 * Clears the browser's current text selection
 */
export function clearBrowserSelection(): void {
    const selection = window.getSelection();
    if (selection) {
        selection.removeAllRanges();
    }
}

/**
 * Checks if the selection is fully contained within a single container element.
 * This prevents selections that span across multiple messages.
 * @param range - The selection range to check
 * @param container - The container element that should fully contain the selection
 * @returns True if the selection is fully contained within the container
 */
export function isSelectionContainedInElement(range: Range, container: HTMLElement): boolean {
    // Check if both the start and end of the selection are within the container
    const startContainer = range.startContainer;
    const endContainer = range.endContainer;

    // Check if start container is within the element
    const startInContainer = container.contains(startContainer);
    // Check if end container is within the element
    const endInContainer = container.contains(endContainer);

    return startInContainer && endInContainer;
}
