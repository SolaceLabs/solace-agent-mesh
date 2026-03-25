/**
 * ShareNotification - Display notification when a chat is shared
 */

import { formatRelativeTime } from "@/lib/utils/format";

type ShareType = "user-specific" | "domain-restricted" | "authenticated" | "public";

interface ShareNotificationProps {
    /** User who shared the chat */
    sharedBy: string;
    /** Type of sharing */
    shareType: ShareType;
    /** Who the chat was shared with (for user-specific sharing) */
    sharedWith?: string;
    /** Timestamp when the chat was shared (epoch milliseconds) */
    sharedAt: number;
}

export function ShareNotification({ sharedBy, shareType, sharedWith, sharedAt }: Readonly<ShareNotificationProps>) {
    const getShareMessage = () => {
        switch (shareType) {
            case "user-specific":
                return (
                    <>
                        <span className="font-medium">{sharedBy}</span> shared this chat with <span className="font-medium">{sharedWith}</span>
                    </>
                );
            case "domain-restricted":
                return (
                    <>
                        <span className="font-medium">{sharedBy}</span> shared this chat with <span className="font-medium">your domain</span>
                    </>
                );
            case "authenticated":
                return (
                    <>
                        <span className="font-medium">{sharedBy}</span> shared this chat with <span className="font-medium">authenticated users</span>
                    </>
                );
            case "public":
                return (
                    <>
                        <span className="font-medium">{sharedBy}</span> created a <span className="font-medium">public link</span> for this chat
                    </>
                );
        }
    };

    return (
        <div className="text-muted-foreground mx-auto my-4 max-w-3xl rounded-lg px-4 py-3 text-center text-sm">
            <p className="text-muted-foreground/70 mt-0.5 text-xs">{formatRelativeTime(new Date(sharedAt).toISOString())}</p>
            <p>{getShareMessage()}</p>
        </div>
    );
}
