import { useCallback, useRef } from "react";
import { useChatContext } from "./useChatContext";
import { useTransferContext } from "@/lib/api/sessions/hooks";

export const useAgentSelection = () => {
    const { agents, sessionId, messages, selectedAgentName, setMessages, setSelectedAgentName, handleNewSession } = useChatContext();
    const { mutateAsync: transferContext } = useTransferContext();
    const hasExistingConversation = messages.length > 1;
    const sessionIdRef = useRef(sessionId);
    sessionIdRef.current = sessionId;

    const handleAgentSelection = useCallback(
        async (agentName: string, startNewChat = false) => {
            if (!agentName) return;

            const selectedAgent = agents.find(agent => agent.name === agentName);
            if (!selectedAgent) return;

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
                            // sessionIdRef may be stale after handleNewSession resets state
                            sessionId: sessionIdRef.current || "",
                            lastProcessedEventSequence: 0,
                        },
                    },
                ]);
                return;
            }

            // Mid-session agent switch: transfer context if there's an active session
            const previousAgentName = selectedAgentName;

            // Guard against re-selecting the same agent
            if (agentName === previousAgentName) return;

            const currentSessionId = sessionIdRef.current;
            const hasConversation = currentSessionId && previousAgentName && previousAgentName !== agentName && hasExistingConversation;

            // Update selection immediately to prevent race condition
            setSelectedAgentName(agentName);

            if (hasConversation) {
                try {
                    await transferContext({
                        sessionId: currentSessionId,
                        request: {
                            sourceAgentName: previousAgentName,
                            targetAgentName: agentName,
                        },
                    });
                } catch {
                    // Context transfer is best-effort; new agent starts fresh on failure
                }
            }

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
                        sessionId: currentSessionId || "",
                        lastProcessedEventSequence: 0,
                    },
                },
            ]);
        },
        [agents, hasExistingConversation, selectedAgentName, setMessages, setSelectedAgentName, handleNewSession, transferContext]
    );

    return { handleAgentSelection };
};
