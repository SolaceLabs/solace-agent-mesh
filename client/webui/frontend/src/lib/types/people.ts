/**
 * Represents a person/user in the organization
 */
export interface Person {
    id: string;
    name: string;
    email: string;
    title?: string;
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
