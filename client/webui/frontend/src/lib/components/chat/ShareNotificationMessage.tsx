/**
 * Share Notification Message Component
 *
 * Displays a centered notification when a chat is shared with other users
 * Appears in the message stream at the point where sharing occurred
 */

import { formatCollaborativeTimestamp } from "@/lib/mockData/collaborativeChat";

interface ShareNotificationMessageProps {
    /** Name of the user who shared the chat */
    sharedBy: string;
    /** Names of users who were added to the chat */
    sharedWith: string[];
    /** Timestamp of when the share occurred */
    timestamp: number;
}

export function ShareNotificationMessage({ sharedBy, sharedWith, timestamp }: ShareNotificationMessageProps) {
    const sharedWithText = sharedWith.length === 1 ? sharedWith[0] : sharedWith.length === 2 ? `${sharedWith[0]} and ${sharedWith[1]}` : `${sharedWith.slice(0, -1).join(", ")}, and ${sharedWith[sharedWith.length - 1]}`;

    return (
        <div className="flex flex-col items-center gap-1 py-4">
            <p className="text-muted-foreground text-sm opacity-50">{formatCollaborativeTimestamp(timestamp)}</p>
            <p className="text-foreground text-sm">
                {sharedBy} shared this chat with {sharedWithText}
            </p>
        </div>
    );
}
