/**
 * User display formatting utilities
 */

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
