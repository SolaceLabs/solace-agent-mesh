/**
 * Message Attribution Component
 *
 * Unified component for displaying attribution above messages in collaborative chats
 * Supports both user attribution (with avatar) and agent attribution (with icon)
 */

import { Bot } from "lucide-react";
import { formatCollaborativeTimestamp } from "@/lib/mockData/collaborativeChat";
import { UserAvatar } from "./UserAvatar";

interface MessageAttributionProps {
    /** Type of attribution - user or agent */
    readonly type: "user" | "agent";
    /** Display name (user name or agent name) */
    readonly name: string;
    /** User's index in collaborators list (for user type only) */
    readonly userIndex?: number;
    /** Message timestamp (for user type only) */
    readonly timestamp?: number;
    /** Optional avatar URL (for user type only) */
    readonly avatarUrl?: string;
}

export function MessageAttribution({ type, name, userIndex = 0, timestamp, avatarUrl }: MessageAttributionProps) {
    return (
        <div className="flex items-center gap-2">
            {/* Icon/Avatar */}
            {type === "agent" ? (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-(--color-accent-n2-w10) dark:bg-(--color-accent-n2-w100)">
                    <Bot className="h-4 w-4 text-(--color-brand-wMain)" />
                </div>
            ) : (
                <UserAvatar name={name} userIndex={userIndex} avatarUrl={avatarUrl} />
            )}

            {/* Name and optional timestamp */}
            <div className="flex items-baseline gap-2">
                <span className="text-sm font-bold">{name}</span>
                {type === "user" && timestamp !== undefined && <span className="text-sm text-[var(--color-secondary-text-wMain)]">{formatCollaborativeTimestamp(timestamp)}</span>}
            </div>
        </div>
    );
}
