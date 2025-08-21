import { useMemo } from "react";

import type { TextPart } from "@/lib/types";
import { useChatContext } from "./useChatContext";

/**
 * Custom hook to get the session preview text based on the first user message.
 * Returns "New Chat" if no user message exists, otherwise returns the first 100 characters
 * of the first user message with "..." if truncated.
 */
export const useSessionPreview = (): string => {
    const { messages } = useChatContext();

    return useMemo(() => {
        const firstUserMessage = messages.find(msg => {
            if (!msg.isUser) return false;
            // Check if there's at least one text part with content
            return msg.parts.some(p => p.kind === "text" && (p as TextPart).text.trim());
        });

        if (firstUserMessage) {
            const textParts = firstUserMessage.parts.filter(p => p.kind === "text") as TextPart[];
            const combinedText = textParts.map(p => p.text).join(" ").trim();

            if (combinedText) {
                return combinedText.length > 100 ? `${combinedText.substring(0, 100)}...` : combinedText;
            }
        }

        return "New Chat";
    }, [messages]);
};
