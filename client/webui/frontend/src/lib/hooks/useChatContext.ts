import { useContext } from "react";

import { ChatContext } from "@/lib/contexts/ChatContext";
import type { ChatContextValue } from "@/lib/contexts/ChatContext";

export const useChatContext = (): ChatContextValue => {
    const context = useContext(ChatContext);
    if (context === undefined) {
        throw new Error("useChatContext must be used within a ChatProvider");
    }
    return context;
};
