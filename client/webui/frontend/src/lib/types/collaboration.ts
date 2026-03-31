/**
 * TypeScript types for collaborative chat features
 */

/**
 * Represents a user in a collaborative session
 */
export interface CollaborativeUser {
    /** Unique user identifier */
    id: string;
    /** User's display name */
    name: string;
    /** User's email address */
    email: string;
    /** Optional avatar URL */
    avatar?: string;
    /** User's role in the session */
    role: "owner" | "collaborator";
    /** Whether the user is currently online */
    isOnline: boolean;
    /** Last seen timestamp (if offline) */
    lastSeen?: Date;
}

/**
 * Information about a collaborative session's state
 */
export interface CollaborativeSessionInfo {
    /** Whether the session is currently shared and active */
    isSharedSession: boolean;
    /** Whether the session was previously shared but access has been revoked */
    wasSharedSession: boolean;
    /** List of users with access to this session */
    collaborators: CollaborativeUser[];
    /** ID of the current user viewing the session */
    currentUserId: string;
    /** ID of the session owner */
    ownerId: string;
    /** Timestamp when the session was shared (if applicable) */
    sharedAt?: number;
    /** Name of the user who initiated the share */
    sharedByName?: string;
    /** Names of users who were added to the share */
    sharedWithNames?: string[];
}

/**
 * Represents a shared session item in the "Shared with me" list
 */
export interface SharedSessionListItem {
    /** Share link ID */
    shareId: string;
    /** Session ID */
    sessionId: string;
    /** Session title/name */
    title: string;
    /** Name of the session owner */
    ownerName: string;
    /** Email of the session owner */
    ownerEmail: string;
    /** User's access level */
    accessLevel: "read-only" | "collaborate";
    /** Timestamp when the session was shared with the user */
    sharedAt: number;
    /** Number of unread messages (optional) */
    unreadCount?: number;
    /** Number of currently active users (optional) */
    activeUserCount?: number;
}

/**
 * Share event that appears in message history
 */
export interface ShareEvent {
    /** Type identifier */
    type: "share_notification";
    /** Timestamp of the share event */
    timestamp: number;
    /** Name of the user who shared the session */
    sharedBy: string;
    /** Names of users who were added */
    sharedWith: string[];
}
