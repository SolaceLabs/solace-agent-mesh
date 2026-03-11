/**
 * User Presence Avatars Component
 *
 * Displays circular avatars with user initials in the header
 * Shows active collaborators in a shared chat session
 */

import { Tooltip, TooltipContent, TooltipTrigger } from "../ui";
import type { CollaborativeUser } from "@/lib/types/collaboration";
import { getUserInitials } from "@/lib/mockData/collaborativeChat";

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

    // Sequential accent colors from our design system (n1-n9)
    const accentColors = [
        "bg-[var(--color-accent-n1-wMain)] text-white",
        "bg-[var(--color-accent-n2-wMain)] text-white",
        "bg-[var(--color-accent-n3-wMain)] text-white",
        "bg-[var(--color-accent-n4-wMain)] text-white",
        "bg-[var(--color-accent-n5-wMain)] text-white",
        "bg-[var(--color-accent-n6-wMain)] text-white",
        "bg-[var(--color-accent-n7-wMain)] text-white",
        "bg-[var(--color-accent-n8-wMain)] text-white",
        "bg-[var(--color-accent-n9-wMain)] text-white",
    ];

    return (
        <div className="flex items-center">
            {/* Show all active users' avatars */}
            {activeUsers.map((user, index) => (
                <Tooltip key={user.id}>
                    <TooltipTrigger asChild>
                        <div className={`flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-sm font-medium ${accentColors[index % accentColors.length]}`} style={{ marginLeft: index > 0 ? "-8px" : "0" }}>
                            {getUserInitials(user.name)}
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        <div className="text-sm font-medium">{user.name}</div>
                    </TooltipContent>
                </Tooltip>
            ))}
        </div>
    );
}
