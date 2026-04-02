/**
 * User display formatting utilities
 */

/**
 * Extract a capitalized first name from an email or display name string.
 * For emails: takes the local part before '@', splits on '.', '_', '-', and capitalizes the first segment.
 * For display names: takes the first word and capitalizes it.
 * Returns null if the input is empty.
 */
export function extractFirstName(identifier: string): string | null {
    if (!identifier) return null;

    if (identifier.includes("@")) {
        const localPart = identifier.split("@")[0];
        const firstName = localPart.split(/[._-]/)[0];
        return firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase();
    }

    const firstName = identifier.split(/\s+/)[0];
    return firstName.charAt(0).toUpperCase() + firstName.slice(1);
}

/**
 * Get user initials from name
 */
export function getUserInitials(name: string): string {
    const words = name.trim().split(/\s+/);
    if (words.length === 0) return "?";
    if (words.length === 1) return words[0].substring(0, 2).toUpperCase();
    // Use first + last name initials (e.g., "Vincent Van Gogh" → "VG")
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/**
 * Format timestamp for display (e.g., "9:48 AM")
 */
export function formatCollaborativeTimestamp(timestamp: number): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
    });
}
