import { useCallback } from "react";
import { useChatContext } from "./useChatContext";
import { api } from "@/lib/api/client";

export const useAgentSelection = () => {
    const { agents, sessionId, messages, selectedAgentName, setMessages, setSelectedAgentName, handleNewSession, agentNameDisplayNameMap } = useChatContext();

    const handleAgentSelection = useCallback(
        async (agentName: string, startNewChat = false) => {
            if (!agentName) return;

            const selectedAgent = agents.find(agent => agent.name === agentName);
            if (!selectedAgent) {
                console.warn(`Selected agent not found: ${agentName}`);
                return;
            }

            if (startNewChat) {
                handleNewSession();
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
                return;
            }

            // Mid-session agent switch: transfer context if there's an active session
            const previousAgentName = selectedAgentName;
            const hasConversation = sessionId && previousAgentName && previousAgentName !== agentName && messages.length > 1;

            if (hasConversation) {
                // Get display name of the previous agent for context marker
                const previousDisplayName = agentNameDisplayNameMap[previousAgentName] || previousAgentName;

                try {
                    console.log(`[useAgentSelection] Transferring context from ${previousAgentName} to ${agentName} for session ${sessionId}`);
                    await api.webui.post(`/api/v1/sessions/${sessionId}/transfer-context`, {
                        source_agent_name: previousAgentName,
                        target_agent_name: agentName,
                        source_agent_display_name: previousDisplayName,
                    });
                    console.log(`[useAgentSelection] Context transfer successful`);
                } catch (error) {
                    console.warn("[useAgentSelection] Context transfer failed, new agent starts fresh:", error);
                }
            }

            setSelectedAgentName(agentName);

            // Append an agent switch indicator message (preserving existing messages)
            const switchText = hasConversation ? `Switched to ${selectedAgent.displayName}.` : `Hi! I'm the ${selectedAgent.displayName}. How can I help?`;

            setMessages(prev => [
                ...prev,
                {
                    parts: [{ kind: "text", text: switchText }],
                    isUser: false,
                    isComplete: true,
                    role: "agent",
                    isAgentSwitchIndicator: hasConversation ? true : undefined,
                    metadata: {
                        sessionId: sessionId || "",
                        lastProcessedEventSequence: 0,
                    },
                },
            ]);
        },
        [agents, sessionId, messages.length, selectedAgentName, setMessages, setSelectedAgentName, handleNewSession, agentNameDisplayNameMap]
    );

    return { handleAgentSelection };
};
