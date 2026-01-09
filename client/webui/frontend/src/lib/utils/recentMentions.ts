import type { Person } from "@/lib/types";

const STORAGE_KEY = "recent_mentions";
const MAX_RECENT_MENTIONS = 10;

/**
 * Retrieves recent mentions from localStorage
 */
export function getRecentMentions(): Person[] {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return [];

        const parsed = JSON.parse(stored);
        return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
        console.error("Error reading recent mentions from localStorage:", error);
        return [];
    }
}

/**
 * Adds a person to recent mentions (most recent first, deduped by id)
 */
export function addRecentMention(person: Person): void {
    try {
        let recent = getRecentMentions();

        // Remove if already exists (to move to front)
        recent = recent.filter(p => p.id !== person.id);

        // Add to front
        recent.unshift(person);

        // Keep only the most recent MAX_RECENT_MENTIONS
        recent = recent.slice(0, MAX_RECENT_MENTIONS);

        localStorage.setItem(STORAGE_KEY, JSON.stringify(recent));
    } catch (error) {
        console.error("Error saving recent mention to localStorage:", error);
    }
}

/**
 * Clears all recent mentions from localStorage
 */
export function clearRecentMentions(): void {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
        console.error("Error clearing recent mentions from localStorage:", error);
    }
}
