/**
 * Clipboard utility functions
 */

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        console.error("Failed to copy to clipboard:", err);
        return false;
    }
}

/**
 * Copy the result of an async operation to the clipboard while preserving
 * the user gesture. Call this synchronously inside a click handler —
 * it creates the ClipboardItem immediately and lets the browser resolve
 * the content when the promise settles.
 */
export function copyDeferredToClipboard(textPromise: Promise<string>): Promise<boolean> {
    try {
        const item = new ClipboardItem({
            "text/plain": textPromise.then(text => new Blob([text], { type: "text/plain" })),
        });
        return navigator.clipboard.write([item]).then(() => true);
    } catch (err) {
        console.error("Failed to copy to clipboard (deferred):", err);
        return Promise.resolve(false);
    }
}
