import type { MessageFE } from "@/lib/types";
import { Button, useChatContext } from "@/lib";

export const AuthenticationMessage: React.FC<{ message: MessageFE }> = ({ message }) => {
    const { handleCancel, setMessages } = useChatContext();

    if (message.authenticationLink) {
        const authenticationAttempted = message.authenticationLink.authenticationAttempted || false;
        const rejected = message.authenticationLink.rejected || false;

        const handleAuthClick = () => {
            if (authenticationAttempted || rejected) return;

            // Update the message to mark authentication as attempted
            setMessages((prevMessages: MessageFE[]) =>
                prevMessages.map(msg => (msg.metadata?.messageId === message.metadata?.messageId && msg.authenticationLink ? { ...msg, authenticationLink: { ...msg.authenticationLink, authenticationAttempted: true } } : msg))
            );

            const popup = window.open(message.authenticationLink!.url, "_blank", "width=800,height=700,scrollbars=yes,resizable=yes");
            if (popup) {
                popup.focus();
            }
        };

        const handleRejectClick = async () => {
            if (authenticationAttempted || rejected) return;

            const gatewayTaskId = message.authenticationLink?.gatewayTaskId;
            if (!gatewayTaskId) {
                console.error("No gateway_task_id available for rejection");

                // Still mark as rejected to disable buttons
                setMessages((prevMessages: MessageFE[]) =>
                    prevMessages.map(msg => (msg.metadata?.messageId === message.metadata?.messageId && msg.authenticationLink ? { ...msg, authenticationLink: { ...msg.authenticationLink, rejected: true } } : msg))
                );
                return;
            }

            // Mark as rejected immediately to disable buttons
            setMessages((prevMessages: MessageFE[]) =>
                prevMessages.map(msg => (msg.metadata?.messageId === message.metadata?.messageId && msg.authenticationLink ? { ...msg, authenticationLink: { ...msg.authenticationLink, rejected: true } } : msg))
            );

            handleCancel();
        };

        const targetAgent = message.authenticationLink.targetAgent || "Agent";

        return (
            <div className="w-1/2 rounded-lg border p-4 shadow-sm">
                <div className="font-semibold">Action Needed</div>
                <div className="py-4">The "{targetAgent}" agent requires authentication.</div>
                <div className="flex flex-row justify-end gap-2">
                    <Button variant="ghost" onClick={handleRejectClick} disabled={authenticationAttempted || rejected}>
                        Reject
                    </Button>
                    <Button onClick={handleAuthClick} disabled={authenticationAttempted || rejected}>
                        {message.authenticationLink.text}
                    </Button>
                </div>
                <div className="text-muted-foreground w-full text-center text-xs">
                    {rejected && <div className="mt-4">Authentication request rejected.</div>}
                    {authenticationAttempted && <div className="mt-4">Authentication window has been opened. Complete the process in the new window.</div>}
                </div>
            </div>
        );
    }

    return null;
};
