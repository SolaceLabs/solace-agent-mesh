/**
 * Message User Attribution Component
 *
 * Displays user information (name, avatar, timestamp) above messages in collaborative chats
 * Only shown for other users' messages, not for the current user's messages
 */

import { formatCollaborativeTimestamp, getUserInitials } from "@/lib/mockData/collaborativeChat";

interface MessageUserAttributionProps {
    /** User's display name */
    readonly userName: string;
    /** Message timestamp */
    readonly timestamp: number;
    /** Optional avatar URL */
    readonly avatarUrl?: string;
    /** User's index in the collaborators list (for consistent color assignment) */
    readonly userIndex?: number;
}

export function MessageUserAttribution({ userName, timestamp, avatarUrl, userIndex = 0 }: MessageUserAttributionProps) {
    const initials = getUserInitials(userName);

    // Use same sequential accent colors as UserPresenceAvatars
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

    const avatarColorClass = accentColors[userIndex % accentColors.length];

    return (
        <div className="flex items-center gap-2">
            {/* Avatar circle */}
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium ${avatarColorClass}`}>
                {avatarUrl ? <img src={avatarUrl} alt={userName} className="h-full w-full rounded-full object-cover" /> : initials}
            </div>

            {/* User name and timestamp */}
            <div className="flex items-baseline gap-2">
                <span className="text-sm font-bold">{userName}</span>
                <span className="text-sm text-[var(--color-secondary-text-wMain)]">{formatCollaborativeTimestamp(timestamp)}</span>
            </div>
        </div>
    );
}
