import { useMemo } from "react";
import { useChatContext } from "./useChatContext";


export const useSessionPreview = (): string => {
    const { messages, sessionName } = useChatContext();

    return useMemo(() => {
        if (sessionName) {
            return sessionName;
        }
        const firstUserMessage = messages.find(msg => msg.isUser && msg.text && msg.text.trim());
        if (firstUserMessage && firstUserMessage.text) {
            const preview = firstUserMessage.text.trim();
            return preview.length > 100 ? preview.substring(0, 100) + "..." : preview;
        }
        return "New Chat";
    }, [messages, sessionName]);
};
