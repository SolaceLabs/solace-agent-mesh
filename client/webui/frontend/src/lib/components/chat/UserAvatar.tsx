/**
 * User Avatar Component
 *
 * Shared avatar component for user presence and message attribution
 * Uses sequential accent colors for consistency
 * Includes optional tooltip with user name
 */

import { Tooltip, TooltipContent, TooltipTrigger } from "../ui";
import { cn } from "@/lib/utils";
import { getUserInitials } from "@/lib/utils/userFormatting";

// Sequential accent colors from our design system (n1-n9)
export const USER_AVATAR_COLORS = [
    "bg-(--accent-n1-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n2-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n3-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n4-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n5-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n6-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n7-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n8-wMain) text-(--darkSurface-text)",
    "bg-(--accent-n9-wMain) text-(--darkSurface-text)",
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
        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-medium", colorClass, className)}>
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
