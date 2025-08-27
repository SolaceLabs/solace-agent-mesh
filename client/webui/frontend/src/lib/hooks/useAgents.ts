import { useState, useEffect, useCallback } from "react";

import type { AgentCard, AgentExtension, AgentInfo, AgentSkill } from "@/lib/types";
import { authenticatedFetch } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

const DISPLAY_NAME_EXTENSION_URI = "https://solace.com/a2a/extensions/display-name";
const PEER_AGENT_TOPOLOGY_EXTENSION_URI = "https://solace.com/a2a/extensions/peer-agent-topology";
const TOOL_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools";

/**
 * Transforms a raw A2A AgentCard into a UI-friendly AgentInfo object,
 * extracting the display_name and peer_agents from the extensions array.
 */
const transformAgentCard = (card: AgentCard): AgentInfo => {
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
        display_name: displayName,
        peer_agents: peerAgents || [],
        tools: tools || [],
    };
};

interface UseAgentsReturn {
    agents: AgentInfo[];
    isLoading: boolean;
    error: string | null;
    refetch: () => Promise<void>;
}

export const useAgents = (): UseAgentsReturn => {
    const { configServerUrl } = useConfigContext();
    const [agents, setAgents] = useState<AgentInfo[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const apiPrefix = `${configServerUrl}/api/v1`;

    const fetchAgents = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await authenticatedFetch(`${apiPrefix}/agents`, { credentials: "include" });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Failed to fetch agents: ${response.statusText}` }));
                throw new Error(errorData.message || `Failed to fetch agents: ${response.statusText}`);
            }
            const data: AgentCard[] = await response.json();
            const transformedAgents = data.map(transformAgentCard);
            setAgents(transformedAgents);
        } catch (err: unknown) {
            console.error("Error fetching agents:", err);
            setError(err instanceof Error ? err.message : "Could not load agent information.");
            setAgents([]);
        } finally {
            setIsLoading(false);
        }
    }, [apiPrefix]);

    useEffect(() => {
        fetchAgents();
    }, [fetchAgents]);

    return {
        agents,
        isLoading,
        error,
        refetch: fetchAgents,
    };
};
