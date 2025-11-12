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
    const menuWidth = 200; // Approximate menu width
    const menuHeight = 150; // Approximate menu height
    const padding = 10;

    let x = rect.left + rect.width / 2;
    let y = rect.bottom + padding;

    // Adjust if menu would go off right edge
    if (x + menuWidth / 2 > window.innerWidth) {
        x = window.innerWidth - menuWidth / 2 - padding;
    }

    // Adjust if menu would go off left edge
    if (x - menuWidth / 2 < 0) {
        x = menuWidth / 2 + padding;
    }

    // If menu would go off bottom, show above selection
    if (y + menuHeight > window.innerHeight) {
        y = rect.top - menuHeight - padding;
    }

    // If still off screen, position at top
    if (y < 0) {
        y = padding;
    }

    return { x, y };
}

/**
 * Validates if a selection is meaningful (not just whitespace, meets minimum length)
 */
export function isValidSelection(text: string | null): boolean {
    if (!text) {
        return false;
    }
    const trimmed = text.trim();
    return trimmed.length >= 3 && /\S/.test(trimmed);
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