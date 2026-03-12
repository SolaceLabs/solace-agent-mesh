import { useCallback, useState } from "react";
import { useChatContext } from "./useChatContext";
import { useConfigContext } from "./useConfigContext";

export const useAgentSelection = () => {
    const { agents, messages, selectedAgentName, setSelectedAgentName, handleNewSession } = useChatContext();
    const { persistenceEnabled } = useConfigContext();

    // State for the confirmation dialog when persistence is disabled
    const [switchConfirmOpen, setSwitchConfirmOpen] = useState(false);
    const [pendingAgentName, setPendingAgentName] = useState<string | null>(null);

    const executeSwitch = useCallback(
        (agentName: string) => {
            const selectedAgent = agents.find(agent => agent.name === agentName);
            if (!selectedAgent) {
                console.warn(`Selected agent not found: ${agentName}`);
                return;
            }
            handleNewSession();
            setSelectedAgentName(agentName);
        },
        [agents, handleNewSession, setSelectedAgentName]
    );

    const handleAgentSelection = useCallback(
        (agentName: string) => {
            if (!agentName || agentName === selectedAgentName) return;

            // Check if there's an active conversation (more than just the auto-injected greeting)
            const hasConversation = messages.length > 1 || (messages.length === 1 && messages[0].isUser);

            if (hasConversation && !persistenceEnabled) {
                // Show confirmation dialog — switching will lose the chat
                setPendingAgentName(agentName);
                setSwitchConfirmOpen(true);
            } else {
                executeSwitch(agentName);
            }
        },
        [selectedAgentName, messages, persistenceEnabled, executeSwitch]
    );

    const confirmAgentSwitch = useCallback(() => {
        if (pendingAgentName) {
            executeSwitch(pendingAgentName);
            setPendingAgentName(null);
            setSwitchConfirmOpen(false);
        }
    }, [pendingAgentName, executeSwitch]);

    const cancelAgentSwitch = useCallback(() => {
        setPendingAgentName(null);
        setSwitchConfirmOpen(false);
    }, []);

    return {
        handleAgentSelection,
        switchConfirmOpen,
        setSwitchConfirmOpen,
        confirmAgentSwitch,
        cancelAgentSwitch,
    };
};
