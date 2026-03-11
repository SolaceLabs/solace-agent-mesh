/**
 * User Avatar Component
 *
 * Shared avatar component for user presence and message attribution
 * Uses sequential accent colors for consistency
 * Includes optional tooltip with user name
 */

import { Tooltip, TooltipContent, TooltipTrigger } from "../ui";
import { getUserInitials } from "@/lib/mockData/collaborativeChat";

// Sequential accent colors from our design system (n1-n9)
export const USER_AVATAR_COLORS = [
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

interface UserAvatarProps {
    readonly name: string;
    readonly userIndex: number;
    readonly avatarUrl?: string;
    readonly className?: string;
    readonly showTooltip?: boolean;
}

export function UserAvatar({ name, userIndex, avatarUrl, className = "", showTooltip = false }: UserAvatarProps) {
    const initials = getUserInitials(name);
    const colorClass = USER_AVATAR_COLORS[userIndex % USER_AVATAR_COLORS.length];

    const avatar = (
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium ${colorClass} ${className}`}>
            {avatarUrl ? <img src={avatarUrl} alt={name} className="h-full w-full rounded-full object-cover" /> : initials}
        </div>
    );

    if (!showTooltip) {
        return avatar;
    }

    return (
        <Tooltip>
            <TooltipTrigger asChild>{avatar}</TooltipTrigger>
            <TooltipContent>
                <div className="text-sm font-medium">{name}</div>
            </TooltipContent>
        </Tooltip>
    );
}
