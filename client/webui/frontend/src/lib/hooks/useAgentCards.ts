import { useState, useEffect, useCallback, useMemo } from "react";

import type { AgentCard, AgentExtension, AgentCardInfo, AgentSkill } from "@/lib/types";
import { fetchJsonWithError } from "@/lib/utils/api";

import { useConfigContext } from "./useConfigContext";

const DISPLAY_NAME_EXTENSION_URI = "https://solace.com/a2a/extensions/display-name";
const PEER_AGENT_TOPOLOGY_EXTENSION_URI = "https://solace.com/a2a/extensions/peer-agent-topology";
const TOOL_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools";

/**
 * Transforms a raw A2A AgentCard into a UI-friendly AgentCardInfo object,
 * extracting the displayName and peer_agents from the extensions array.
 */
export const transformAgentCard = (card: AgentCard): AgentCardInfo => {
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
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    const fetchAgents = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const apiPrefix = `${configServerUrl}/api/v1`;
            const data: AgentCard[] = await fetchJsonWithError(`${apiPrefix}/agentCards`);
            const transformedAgents = data.map(transformAgentCard);
            setAgents(transformedAgents);
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

    const agentNameMap = useMemo(() => {
        const nameDisplayNameMap: Record<string, string> = {};
        agents.forEach(agent => {
            if (agent.name) {
                nameDisplayNameMap[agent.name] = agent.displayName || agent.name;
            }
        });
        return nameDisplayNameMap;
    }, [agents]);

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
