/**
 * Collaborative User Message Component
 *
 * Wraps a user message from another collaborator with proper styling
 * Shows attribution and uses "other-user" bubble variant
 */

import { ChatBubble, ChatBubbleMessage } from "@/lib/components/ui";
import { MessageHoverButtons } from "./MessageHoverButtons";
import { MarkdownWrapper } from "@/lib/components";
import type { MessageFE, TextPart } from "@/lib/types";
import { MessageUserAttribution } from "./MessageUserAttribution";

interface CollaborativeUserMessageProps {
    readonly message: MessageFE;
    readonly userName: string;
    readonly timestamp: number;
    readonly userIndex?: number;
}

export function CollaborativeUserMessage({ message, userName, timestamp, userIndex }: CollaborativeUserMessageProps) {
    // Extract text content
    const textPart = message.parts?.find(p => p.kind === "text") as TextPart | undefined;
    const text = textPart?.text || "";

    return (
        <div className="flex flex-col items-start gap-1">
            <MessageUserAttribution userName={userName} timestamp={timestamp} userIndex={userIndex} />
            <div className="ml-10 flex max-w-[70%] flex-col gap-1">
                <ChatBubble variant="other-user">
                    <ChatBubbleMessage variant="other-user">
                        <MarkdownWrapper content={text} />
                    </ChatBubbleMessage>
                </ChatBubble>
                <div className="flex justify-start">
                    <MessageHoverButtons message={message} />
                </div>
            </div>
        </div>
    );
}
