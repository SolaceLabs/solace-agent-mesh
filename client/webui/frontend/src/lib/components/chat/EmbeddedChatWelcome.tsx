import React from "react";

interface EmbeddedChatWelcomeProps {
    message?: string;
}

export const EmbeddedChatWelcome: React.FC<EmbeddedChatWelcomeProps> = ({ message }) => {
    return <h1 className="text-foreground text-center text-3xl font-semibold tracking-tight">{message || "How can I help?"}</h1>;
};
