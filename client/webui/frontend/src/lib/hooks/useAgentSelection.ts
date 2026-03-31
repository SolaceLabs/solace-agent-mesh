import { useCallback, useRef } from "react";
import { useChatContext } from "./useChatContext";
import { useTransferContext } from "@/lib/api/sessions/hooks";

// Generation counter to implement "latest wins" for rapid agent switching.
// If user switches A->B->C rapidly, only the last transfer's indicator message
// is shown — earlier transfers are silently discarded.
let transferGeneration = 0;

export const useAgentSelection = () => {
    const { agents, sessionId, messages, selectedAgentName, setMessages, setSelectedAgentName, handleNewSession } = useChatContext();
    const { mutateAsync: transferContext } = useTransferContext();

    // Use refs to avoid stale closures in the async callback
    const sessionIdRef = useRef(sessionId);
    sessionIdRef.current = sessionId;

    const messagesRef = useRef(messages);
    messagesRef.current = messages;

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
                            // handleNewSession resets sessionId asynchronously — use empty string
                            // since the new session ID hasn't been assigned yet
                            sessionId: "",
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
            // Use ref to get fresh messages.length (avoids stale closure)
            const hasConversation = !!(currentSessionId && previousAgentName && previousAgentName !== agentName && messagesRef.current.length > 1);

            // Update selection immediately — this prevents race conditions where
            // a message is sent to the old agent while transfer is in progress
            setSelectedAgentName(agentName);

            // Increment generation counter for "latest wins" pattern
            const thisGeneration = ++transferGeneration;

            let contextTransferred = false;

            if (hasConversation) {
                try {
                    const result = await transferContext({
                        sessionId: currentSessionId,
                        request: {
                            sourceAgentName: previousAgentName,
                            targetAgentName: agentName,
                        },
                    });
                    contextTransferred = result.contextTransferred;
                } catch {
                    // Context transfer failed — agent starts fresh
                    contextTransferred = false;
                }
            }

            // "Latest wins": if another switch happened while we were awaiting,
            // skip appending the indicator message (the newer switch will handle it)
            if (thisGeneration !== transferGeneration) {
                return;
            }

            // Drive messaging based on transfer result
            let switchText: string;
            if (!hasConversation) {
                switchText = `Hi! I'm the ${selectedAgent.displayName}. How can I help?`;
            } else if (contextTransferred) {
                switchText = `Switched to ${selectedAgent.displayName}. I have context from your previous conversation.`;
            } else {
                switchText = `Switched to ${selectedAgent.displayName}. Starting fresh.`;
            }

            setMessages(prev => [
                ...prev,
                {
                    parts: [{ kind: "text", text: switchText }],
                    isUser: false,
                    isComplete: true,
                    role: "agent",
                    isAgentSwitchIndicator: hasConversation || undefined,
                    metadata: {
                        sessionId: currentSessionId || "",
                        lastProcessedEventSequence: 0,
                    },
                },
            ]);
        },
        [agents, selectedAgentName, setMessages, setSelectedAgentName, handleNewSession, transferContext]
    );

    return { handleAgentSelection };
};
