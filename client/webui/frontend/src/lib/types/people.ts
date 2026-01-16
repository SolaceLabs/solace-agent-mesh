/**
 * Represents a person/user in the organization
 *
 * Field names may vary depending on the identity provider:
 * - LocalFileIdentityService uses: name, email, title
 * - BambooHR provider uses: displayName, workEmail, jobTitle
 *
 * Components should handle both formats using fallbacks.
 */
export interface Person {
    id: string;
    // Standard field names (LocalFileIdentityService)
    name?: string;
    email?: string;
    title?: string;
    // Alternative field names (BambooHR format)
    displayName?: string;
    workEmail?: string;
    jobTitle?: string;
}

/**
 * Helper functions to get person fields regardless of format
 */
export const getPersonName = (person: Person): string => person.name || person.displayName || "";

export const getPersonEmail = (person: Person): string => person.email || person.workEmail || "";

export const getPersonTitle = (person: Person): string | undefined => person.title || person.jobTitle;

/**
 * Represents a mention in the chat input
 */
export interface Mention {
    id: string; // User's ID (email)
    name: string; // Display name
    startIndex: number; // Position in text where mention starts
    endIndex: number; // Position in text where mention ends
}

/**
 * Response from people search API
 */
export interface PeopleSearchResponse {
    data: Person[];
}
