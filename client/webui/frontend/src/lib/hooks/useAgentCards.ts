import { useState, useEffect, useCallback, useMemo } from "react";

import type { AgentCard, AgentExtension, AgentCardInfo, AgentSkill } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

const DISPLAY_NAME_EXTENSION_URI = "https://solace.com/a2a/extensions/display-name";
const PEER_AGENT_TOPOLOGY_EXTENSION_URI = "https://solace.com/a2a/extensions/peer-agent-topology";
const TOOL_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools";

/**
 * Transforms a raw A2A AgentCard into a UI-friendly AgentCardInfo object,
 * extracting the displayName and peer_agents from the extensions array.
 */
const transformAgentCard = (card: AgentCard): AgentCardInfo => {
    let displayName: string | undefined;
    let peerAgents: string[] | undefined;
    let tools: AgentSkill[] | undefined;

    if (card.capabilities?.extensions) {
        const displayNameExtension = card.capabilities.extensions.find((ext: AgentExtension) => ext.uri === DISPLAY_NAME_EXTENSION_URI);
        if (displayNameExtension?.params?.display_name) {
            displayName = displayNameExtension.params.display_name as string;
        }

        const peerAgentTopologyExtension = card.capabilities.extensions.find((ext: AgentExtension) => ext.uri === PEER_AGENT_TOPOLOGY_EXTENSION_URI);
        if (peerAgentTopologyExtension?.params?.peer_agent_names) {
            peerAgents = peerAgentTopologyExtension.params.peer_agent_names as string[];
        }

        const toolsExtension = card.capabilities.extensions.find((ext: AgentExtension) => ext.uri === TOOL_EXTENSION_URI);
        if (toolsExtension?.params?.tools) {
            tools = toolsExtension.params.tools as AgentSkill[];
        }
    }
    return {
        ...card,
        // deprecated fields, remove when no longer used
        display_name: displayName,
        peer_agents: peerAgents || [],
        // end deprecated fields
        tools: tools || [],
        displayName: displayName,
        peerAgents: peerAgents || [],
    };
};

interface useAgentCardsReturn {
    agents: AgentCardInfo[];
    agentNameMap: Record<string, string>;
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

export const useAgentCards = (): useAgentCardsReturn => {
    const { configServerUrl } = useConfigContext();
    const [agents, setAgents] = useState<AgentCardInfo[]>([]);
    const [agentNameMap, setAgentNameMap] = useState<Record<string, string>>({});
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAgents = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const apiPrefix = `${configServerUrl}/api/v1`;
            const response = await authenticatedFetch(`${apiPrefix}/agentCards`, { credentials: "include" });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Failed to fetch agents: ${response.statusText}` }));
                throw new Error(errorData.message || `Failed to fetch agents: ${response.statusText}`);
            }
            const data: AgentCard[] = await response.json();
            const transformedAgents = data.map(transformAgentCard);
            setAgents(transformedAgents);

            // Create a mapping of agent names to display names for easy lookup
            const nameDisplayNameMap: Record<string, string> = {};
            transformedAgents.forEach(agent => {
                if (agent.name) {
                    nameDisplayNameMap[agent.name] = agent.displayName || agent.name;
                }
            });
            setAgentNameMap(nameDisplayNameMap);
        } catch (err: unknown) {
            console.error("Error fetching agents:", err);
            setError(err instanceof Error ? err.message : "Could not load agent information.");
            setAgents([]);
        } finally {
            setIsLoading(false);
        }
    }, [configServerUrl]);

    useEffect(() => {
        fetchAgents();
    }, [fetchAgents]);

    return useMemo(
        () => ({
            agents,
            agentNameMap,
            isLoading,
            error,
            refetch: fetchAgents,
        }),
        [agents, agentNameMap, isLoading, error, fetchAgents]
    );
};
