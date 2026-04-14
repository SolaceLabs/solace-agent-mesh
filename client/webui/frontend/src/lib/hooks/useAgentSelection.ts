import { useCallback } from "react";
import { useChatContext } from "./useChatContext";
import { useAgentCards } from "@/lib/api/agent-cards";

export const useAgentSelection = () => {
    const { sessionId, setMessages, setSelectedAgentName, handleNewSession } = useChatContext();
    const { agents } = useAgentCards();

    const handleAgentSelection = useCallback(
        (agentName: string, startNewChat = false) => {
            if (agentName) {
                const selectedAgent = agents.find(agent => agent.name === agentName);
                if (selectedAgent) {
                    if (startNewChat) {
                        handleNewSession();
                    }

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
        [agents, sessionId, setMessages, setSelectedAgentName, handleNewSession]
    );

    return { handleAgentSelection };
};
