/**
 * Mock data for collaborative chat UI development and testing
 */

import type { CollaborativeUser, CollaborativeSessionInfo, SharedSessionListItem } from "../types/collaboration";

/**
 * Mock users for collaborative chat scenarios
 */
export const mockCollaborativeUsers: Record<string, CollaborativeUser> = {
    alice: {
        id: "user-alice-001",
        name: "Olive Operations",
        email: "olive@company.com",
        role: "owner",
        isOnline: true,
    },
    bob: {
        id: "user-bob-002",
        name: "Parminder Procurement",
        email: "parminder@company.com",
        role: "collaborator",
        isOnline: true,
    },
    charlie: {
        id: "user-charlie-003",
        name: "Charlie Chang",
        email: "charlie@company.com",
        role: "collaborator",
        isOnline: false,
        lastSeen: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
    },
};

/**
 * Mock collaborative session info for active shared session
 * Current user is Charlie (viewer) so we can see BOTH Alice and Bob's attributions
 */
export const mockActiveCollaborativeSession: CollaborativeSessionInfo = {
    isSharedSession: true,
    wasSharedSession: false,
    collaborators: [mockCollaborativeUsers.alice, mockCollaborativeUsers.bob, mockCollaborativeUsers.charlie],
    currentUserId: mockCollaborativeUsers.charlie.id, // Charlie is viewing, so we see both Alice and Bob's attributions
    ownerId: mockCollaborativeUsers.alice.id,
    sharedAt: Date.now() - 3 * 60 * 60 * 1000, // 3 hours ago
    sharedByName: "Olive Operations",
    sharedWithNames: ["Parminder Procurement"],
};

/**
 * Mock collaborative session info for formerly shared session (now private)
 */
export const mockFormerlySharedSession: CollaborativeSessionInfo = {
    isSharedSession: false,
    wasSharedSession: true,
    collaborators: [mockCollaborativeUsers.alice], // Only owner remains
    currentUserId: mockCollaborativeUsers.alice.id,
    ownerId: mockCollaborativeUsers.alice.id,
    sharedAt: Date.now() - 7 * 24 * 60 * 60 * 1000, // 7 days ago
    sharedByName: "Olive Operations",
    sharedWithNames: ["Parminder Procurement", "Charlie Chang"],
};

/**
 * Mock shared sessions list for "Shared with me" section
 */
export const mockSharedSessionsList: SharedSessionListItem[] = [
    {
        shareId: "share-001",
        sessionId: "session-shared-001",
        title: "Python Script Development",
        ownerName: "Olive Operations",
        ownerEmail: "olive@company.com",
        accessLevel: "collaborate",
        sharedAt: Date.now() - 3 * 60 * 60 * 1000, // 3 hours ago
        unreadCount: 2,
        activeUserCount: 2,
    },
    {
        shareId: "share-002",
        sessionId: "session-shared-002",
        title: "React App Help",
        ownerName: "David Developer",
        ownerEmail: "david@company.com",
        accessLevel: "read-only",
        sharedAt: Date.now() - 1 * 24 * 60 * 60 * 1000, // 1 day ago
        unreadCount: 0,
        activeUserCount: 1,
    },
    {
        shareId: "share-003",
        sessionId: "session-shared-003",
        title: "API Integration Discussion",
        ownerName: "Sarah Systems",
        ownerEmail: "sarah@company.com",
        accessLevel: "collaborate",
        sharedAt: Date.now() - 5 * 24 * 60 * 60 * 1000, // 5 days ago
        unreadCount: 5,
        activeUserCount: 3,
    },
];

/**
 * Helper function to get user initials from name
 */
export function getUserInitials(name: string): string {
    const words = name.trim().split(/\s+/);
    if (words.length === 0) return "?";
    if (words.length === 1) return words[0].substring(0, 2).toUpperCase();
    return (words[0][0] + words[1][0]).toUpperCase();
}

/**
 * Helper function to get avatar color based on user ID
 */
export function getAvatarColor(userId: string): string {
    const colors = ["bg-blue-100 text-blue-700", "bg-green-100 text-green-700", "bg-purple-100 text-purple-700", "bg-orange-100 text-orange-700", "bg-pink-100 text-pink-700", "bg-teal-100 text-teal-700"];
    const hash = userId.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length];
}

/**
 * Format timestamp for display (e.g., "9:48 am")
 */
export function formatCollaborativeTimestamp(timestamp: number): string {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
    });
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(timestamp: number): string {
    const now = Date.now();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes} minute${minutes > 1 ? "s" : ""} ago`;
    if (hours < 24) return `${hours} hour${hours > 1 ? "s" : ""} ago`;
    return `${days} day${days > 1 ? "s" : ""} ago`;
}

/**
 * Mock message user attributions
 * Maps message index to user info for collaborative chat demo
 * This simulates a conversation where Alice, Bob, and Charlie (current user) take turns messaging
 */
export const mockMessageAttributions: Record<number, { userId: string; userName: string; timestamp: number }> = {
    // Alice's first message (before sharing)
    0: {
        userId: mockCollaborativeUsers.alice.id,
        userName: mockCollaborativeUsers.alice.name,
        timestamp: Date.now() - 4 * 60 * 60 * 1000, // 4 hours ago
    },
    // Alice's second message (before sharing)
    2: {
        userId: mockCollaborativeUsers.alice.id,
        userName: mockCollaborativeUsers.alice.name,
        timestamp: Date.now() - 3.5 * 60 * 60 * 1000, // 3.5 hours ago
    },
    // Share event happens at index 3
    // Bob's first message (after being added)
    4: {
        userId: mockCollaborativeUsers.bob.id,
        userName: mockCollaborativeUsers.bob.name,
        timestamp: Date.now() - 2 * 60 * 60 * 1000, // 2 hours ago
    },
    // Charlie's message (current user - index 6, no attribution will show)
    6: {
        userId: mockCollaborativeUsers.charlie.id,
        userName: mockCollaborativeUsers.charlie.name,
        timestamp: Date.now() - 1.5 * 60 * 60 * 1000, // 1.5 hours ago
    },
    // Alice responds
    8: {
        userId: mockCollaborativeUsers.alice.id,
        userName: mockCollaborativeUsers.alice.name,
        timestamp: Date.now() - 1 * 60 * 60 * 1000, // 1 hour ago
    },
};
