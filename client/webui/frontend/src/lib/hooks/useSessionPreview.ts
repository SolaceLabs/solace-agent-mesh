import { useMemo } from "react";
import { useChatContext } from "./useChatContext";

/**
 * Custom hook to get the session preview text based on the first user message.
 * Returns "New Chat" if no user message exists, otherwise returns the first 100 characters
 * of the first user message with "..." if truncated.
 */
export const useSessionPreview = (): string => {
    const { messages } = useChatContext();

    return useMemo(() => {
        const firstUserMessage = messages.find(msg => msg.isUser && msg.text && msg.text.trim());
        if (firstUserMessage && firstUserMessage.text) {
            const preview = firstUserMessage.text.trim();
            return preview.length > 100 ? preview.substring(0, 100) + "..." : preview;
        }
        return "New Chat";
    }, [messages]);
};
