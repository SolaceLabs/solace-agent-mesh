/**
 * Represents a person/user in the organization.
 *
 * Uses canonical field names from the identity provider:
 * - displayName: Full display name
 * - workEmail: Work email address
 * - jobTitle: Job title (optional)
 */
export interface Person {
    id: string;
    displayName: string;
    workEmail: string;
    jobTitle?: string;
}

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
