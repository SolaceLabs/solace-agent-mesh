/**
 * User Presence Avatars Component
 *
 * Displays circular avatars with user initials in the header
 * Shows active collaborators in a shared chat session
 */

import type { CollaborativeUser } from "@/lib/types/collaboration";
import { UserAvatar } from "./UserAvatar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";

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

    // Limit to 5 visible avatars, show overflow for the rest
    const maxVisible = 5;
    const visibleUsers = activeUsers.slice(0, maxVisible);
    const overflowUsers = activeUsers.slice(maxVisible);
    const hasOverflow = overflowUsers.length > 0;

    return (
        <div className="flex items-center">
            {/* Show visible users' avatars - use email hash for consistent colors with chat messages */}
            {visibleUsers.map((user, index) => {
                const emailHash = (user.email || user.name || "")
                    .toLowerCase()
                    .split("")
                    .reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
                return (
                    <div key={user.id} style={{ marginLeft: index > 0 ? "-8px" : "0" }}>
                        <UserAvatar name={user.name} userIndex={emailHash} avatarUrl={user.avatar} className="cursor-pointer" showTooltip={true} />
                    </div>
                );
            })}

            {/* Show overflow indicator if there are more users */}
            {hasOverflow && (
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div className="bg-muted text-muted-foreground ring-background flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-xs font-semibold ring-2" style={{ marginLeft: "-8px" }}>
                            +{overflowUsers.length}
                        </div>
                    </TooltipTrigger>
                    <TooltipContent className="flex flex-col gap-2 p-3">
                        {overflowUsers.map(user => {
                            const overflowHash = (user.email || user.name || "")
                                .toLowerCase()
                                .split("")
                                .reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
                            return (
                                <div key={user.id} className="flex items-center gap-2">
                                    <UserAvatar name={user.name} userIndex={overflowHash} avatarUrl={user.avatar} />
                                    <span className="text-sm">{user.name}</span>
                                </div>
                            );
                        })}
                    </TooltipContent>
                </Tooltip>
            )}
        </div>
    );
}
