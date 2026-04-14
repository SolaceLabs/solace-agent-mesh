/**
 * API functions and transforms for agent card discovery.
 */

import { api } from "@/lib/api";

import type { AgentCard, AgentExtension, AgentCardInfo, AgentSkill } from "@/lib/types";

const DISPLAY_NAME_EXTENSION_URI = "https://solace.com/a2a/extensions/display-name";
const PEER_AGENT_TOPOLOGY_EXTENSION_URI = "https://solace.com/a2a/extensions/peer-agent-topology";
const TOOL_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/tools";
const AGENT_TYPE_EXTENSION_URI = "https://solace.com/a2a/extensions/agent-type";

/**
 * Transforms a raw A2A AgentCard into a UI-friendly AgentCardInfo object,
 * extracting the displayName and peer_agents from the extensions array.
 */
export const transformAgentCard = (card: AgentCard): AgentCardInfo => {
    let displayName: string | undefined;
    let peerAgents: string[] | undefined;
    let tools: AgentSkill[] | undefined;
    let isWorkflow = false;

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

        const agentTypeExtension = card.capabilities.extensions.find((ext: AgentExtension) => ext.uri === AGENT_TYPE_EXTENSION_URI);
        if (agentTypeExtension?.params?.type === "workflow") {
            isWorkflow = true;
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
        isWorkflow,
    };
};

/**
 * Fetch all discovered agent cards from the gateway.
 */
export async function fetchAgentCards(): Promise<AgentCard[]> {
    return api.webui.get("/api/v1/agentCards");
}
