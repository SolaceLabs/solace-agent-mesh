/**
 * ShareNotification - Display notification when a chat is shared
 */

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
    const formatTime = (timestamp: number) => {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        // Show time if today, date if older
        if (diffDays === 0) {
            if (diffMins < 1) return "just now";
            if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? "s" : ""} ago`;
            if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
        }

        // Use toLocaleTimeString for time formatting
        return date.toLocaleTimeString("en-US", {
            hour: "numeric",
            minute: "2-digit",
            hour12: true,
        });
    };

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
            <p className="text-muted-foreground/70 mt-0.5 text-xs">{formatTime(sharedAt)}</p>
            <p>{getShareMessage()}</p>
        </div>
    );
}
