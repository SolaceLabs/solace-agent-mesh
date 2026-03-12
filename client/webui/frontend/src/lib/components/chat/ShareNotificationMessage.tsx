/**
 * Share Notification Message Component
 *
 * Displays a centered notification when a chat is shared with other users or a sharing link is created
 * Appears in the message stream at the point where sharing occurred
 */

import { Eye, Pencil } from "lucide-react";
import { formatCollaborativeTimestamp } from "@/lib/mockData/collaborativeChat";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/tooltip";

/**
 * Message templates for share notifications
 */
const SHARE_MESSAGES = {
    createdLink: () => `You created a view-only sharing link`,
} as const;

export type ShareNotificationMessageProps =
    | {
          /** Variant: shared with specific users */
          variant: "shared-with-users";
          /** Name of the person who shared (defaults to "You") */
          sharedBy?: string;
          /** Names of users who were added to the chat */
          sharedWith: string[];
          /** Access level granted to users */
          accessLevel: "viewer" | "editor";
          /** Timestamp of when the share occurred */
          timestamp: number;
      }
    | {
          /** Variant: created a sharing link (always view-only access, requires authentication) */
          variant: "created-link";
          /** Name of the user who created the link */
          sharedBy: string;
          /** Timestamp of when the link was created */
          timestamp: number;
      };

/**
 * Helper to format a list of recipient names
 */
function formatRecipients(recipients: string[]): string {
    if (recipients.length === 1) {
        return recipients[0];
    }
    if (recipients.length === 2) {
        return `${recipients[0]} and ${recipients[1]}`;
    }
    return `${recipients.slice(0, -1).join(", ")}, and ${recipients.at(-1)}`;
}

export function ShareNotificationMessage(props: ShareNotificationMessageProps) {
    const { timestamp } = props;

    if (props.variant === "shared-with-users") {
        const { sharedBy = "You", sharedWith, accessLevel } = props;
        const AccessIcon = accessLevel === "viewer" ? Eye : Pencil;
        const accessLevelText = accessLevel === "viewer" ? "Viewer" : "Editor";

        // Truncate recipient list at 3 names
        const maxVisible = 3;
        const visibleRecipients = sharedWith.slice(0, maxVisible);
        const hiddenRecipients = sharedWith.slice(maxVisible);
        const hasHidden = hiddenRecipients.length > 0;

        const visibleRecipientsText = formatRecipients(visibleRecipients);

        return (
            <div className="flex flex-col items-center gap-1 py-4">
                <p className="text-secondary-foreground text-sm">{formatCollaborativeTimestamp(timestamp)}</p>
                <p className="text-foreground flex items-center gap-1.5 text-sm">
                    <span>{sharedBy} gave</span>
                    <span className="inline-flex items-center gap-1">
                        <AccessIcon className="h-3.5 w-3.5" />
                        <span className="font-bold">{accessLevelText}</span>
                    </span>
                    <span>
                        access to {visibleRecipientsText}
                        {hasHidden && (
                            <>
                                {" and "}
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <span
                                            className="text-secondary-foreground hover:bg-accent cursor-pointer"
                                            style={{
                                                borderBottom: "1px dashed var(--color-secondary-wMain)",
                                                paddingBottom: "2px",
                                            }}
                                        >
                                            {hiddenRecipients.length} other {hiddenRecipients.length === 1 ? "user" : "users"}
                                        </span>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <div className="flex flex-col gap-1">
                                            {hiddenRecipients.map(name => (
                                                <span key={name}>{name}</span>
                                            ))}
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </>
                        )}
                    </span>
                </p>
            </div>
        );
    } else {
        // created-link variant (always view-only, requires authentication)
        const messageText = SHARE_MESSAGES.createdLink();

        return (
            <div className="flex flex-col items-center gap-1 py-4">
                <p className="text-secondary-foreground text-sm">{formatCollaborativeTimestamp(timestamp)}</p>
                <p className="text-foreground flex items-center gap-1.5 text-sm">
                    <span>{messageText}</span>
                </p>
            </div>
        );
    }
}

/**
 * @deprecated Use ShareNotificationMessage instead
 * This is an alias for backward compatibility
 */
export const ShareNotification = ShareNotificationMessage;
