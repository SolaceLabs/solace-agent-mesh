import React from "react";

import { MessageCircle } from "lucide-react";

interface AgentModeWelcomeProps {
    message?: string;
}

export const AgentModeWelcome: React.FC<AgentModeWelcomeProps> = ({ message }) => {
    return (
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-4">
            <MessageCircle className="size-12 text-(--secondary-text-wMain)" />
            <p className="text-2xl font-medium text-(--primary-text-wMain)">{message || "How can I help?"}</p>
        </div>
    );
};
