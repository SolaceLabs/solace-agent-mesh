/**
 * User Presence Avatars Component
 *
 * Displays circular avatars with user initials in the header
 * Shows active collaborators in a shared chat session
 */

import type { CollaborativeUser } from "@/lib/types/collaboration";
import { UserAvatar } from "./UserAvatar";

interface UserPresenceAvatarsProps {
    /** List of users currently in the session */
    readonly users: CollaborativeUser[];
    /** ID of the current user (to optionally exclude from display) */
    readonly currentUserId?: string;
}

export function UserPresenceAvatars({ users, currentUserId }: UserPresenceAvatarsProps) {
    // Return null if no users provided
    if (!users || users.length === 0) {
        return null;
    }

    // Filter out current user if specified
    const displayUsers = currentUserId ? users.filter(u => u.id !== currentUserId) : users;

    if (displayUsers.length === 0) {
        return null;
    }

    // Get all active users to display
    const activeUsers = displayUsers.filter(u => u.isOnline);

    return (
        <div className="flex items-center">
            {/* Show all active users' avatars */}
            {activeUsers.map((user, index) => (
                <div key={user.id} style={{ marginLeft: index > 0 ? "-8px" : "0" }}>
                    <UserAvatar name={user.name} userIndex={index} avatarUrl={user.avatar} className="cursor-pointer" showTooltip={true} />
                </div>
            ))}
        </div>
    );
}
