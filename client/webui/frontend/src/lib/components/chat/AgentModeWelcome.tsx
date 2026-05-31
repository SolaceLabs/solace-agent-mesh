import React from "react";

interface AgentModeWelcomeProps {
    message?: string;
}

export const AgentModeWelcome: React.FC<AgentModeWelcomeProps> = ({ message }) => {
    return <h1 className="text-foreground text-center text-3xl font-semibold tracking-tight">{message || "How can I help?"}</h1>;
};
