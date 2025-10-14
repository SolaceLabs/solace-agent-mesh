import { useCallback } from "react";
import { useChatContext } from "./useChatContext";

export const useAgentSelection = () => {
    const { agents, sessionId, setMessages, setSelectedAgentName } = useChatContext();

    const handleAgentSelection = useCallback(
        (agentName: string) => {
            if (agentName) {
                const selectedAgent = agents.find(agent => agent.name === agentName);
                if (selectedAgent) {
                    setSelectedAgentName(agentName);

                    const displayedText = `Hi! I'm the ${selectedAgent.displayName}. How can I help?`;
                    setMessages(prev => [
                        ...prev,
                        {
                            parts: [{ kind: "text", text: displayedText }],
                            isUser: false,
                            isComplete: true,
                            role: "agent",
                            metadata: {
                                sessionId: sessionId || "",
                                lastProcessedEventSequence: 0,
                            },
                        },
                    ]);
                } else {
                    console.warn(`Selected agent not found: ${agentName}`);
                }
            }
        },
        [agents, sessionId, setMessages, setSelectedAgentName]
    );

    return { handleAgentSelection };
};
