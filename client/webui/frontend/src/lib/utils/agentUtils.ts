import type { AgentCardInfo, AgentExtension } from "@/lib/types";

const EXTENSION_URI_WORKFLOW_VISUALIZATION = "https://solace.com/a2a/extensions/sam/workflow-visualization";
const EXTENSION_URI_AGENT_TYPE = "https://solace.com/a2a/extensions/agent-type";
const EXTENSION_URI_SCHEMAS = "https://solace.com/a2a/extensions/sam/schemas";

/**
 * Workflow configuration JSON structure
 */
export interface WorkflowConfig {
    description?: string;
    version?: string;
    nodes: WorkflowNodeConfig[];
    input_schema?: Record<string, unknown>;
    output_schema?: Record<string, unknown>;
    output_mapping?: Record<string, unknown>;
}

export interface WorkflowNodeConfig {
    id: string;
    type: "agent" | "switch" | "map" | "loop" | "workflow";
    depends_on?: string[];
    agent_name?: string;
    workflow_name?: string; // For workflow node type
    input?: Record<string, unknown>;
    instruction?: string;
    input_schema_override?: Record<string, unknown>;
    output_schema_override?: Record<string, unknown>;
    cases?: { condition: string; node: string }[];
    default?: string;
    node?: string;
    items?: string;
    condition?: string;
    max_iterations?: number;
    delay?: string;
}

export interface InitialAgentSelection {
    /** The agent to select, or null to bail (Agent Mode pinned agent not yet available). */
    agent: AgentCardInfo | null;
    /** Whether the caller should seed the welcome bubble. Always false in Agent Mode. */
    shouldSeedWelcome: boolean;
}

/**
 * Decide which agent to pin when a chat opens with no agent yet selected.
 *
 * Priority: URL ?agent= param, then project default, then OrchestratorAgent,
 * then first available. In Agent Mode a pinned ?agent= that isn't available yet
 * bails (agent === null) so the caller waits for it to register, and the welcome
 * bubble is never seeded.
 *
 * Callers must guarantee `agents` is non-empty.
 */
export function selectInitialAgent({ agents, urlAgentName, agentMode, projectDefaultAgentId }: { agents: AgentCardInfo[]; urlAgentName: string | null; agentMode: boolean; projectDefaultAgentId?: string | null }): InitialAgentSelection {
    let selectedAgent = agents[0];

    const urlAgent = urlAgentName ? agents.find(agent => agent.name === urlAgentName) : undefined;
    if (urlAgent) {
        selectedAgent = urlAgent;
    }

    // Agent Mode: pin to the named agent or wait — never fall back.
    if (agentMode && urlAgentName && !urlAgent) {
        return { agent: null, shouldSeedWelcome: false };
    }

    if (!urlAgent) {
        if (projectDefaultAgentId) {
            selectedAgent = agents.find(agent => agent.name === projectDefaultAgentId) ?? agents.find(agent => agent.name === "OrchestratorAgent") ?? agents[0];
        } else {
            selectedAgent = agents.find(agent => agent.name === "OrchestratorAgent") ?? agents[0];
        }
    }

    return { agent: selectedAgent, shouldSeedWelcome: !agentMode };
}

/**
 * Extract agent type from agent card extensions
 */
export function getAgentType(agent: AgentCardInfo): "workflow" | "agent" | null {
    const extensions = agent.capabilities?.extensions;
    if (!extensions || extensions.length === 0) return null;

    const agentTypeExtension = extensions.find((ext: AgentExtension) => ext.uri === EXTENSION_URI_AGENT_TYPE);
    if (!agentTypeExtension?.params) return null;

    const type = agentTypeExtension.params.type;
    if (type === "workflow") return "workflow";

    return "agent";
}

/**
 * Check if an agent is a workflow
 */
export function isWorkflowAgent(agent: AgentCardInfo): boolean {
    return getAgentType(agent) === "workflow";
}

/**
 * Extract workflow configuration from workflow agent card
 */
export function getWorkflowConfig(agent: AgentCardInfo): WorkflowConfig | null {
    const extensions = agent.capabilities?.extensions;
    if (!extensions || extensions.length === 0) return null;

    const vizExtension = extensions.find((ext: AgentExtension) => ext.uri === EXTENSION_URI_WORKFLOW_VISUALIZATION);
    if (!vizExtension?.params) return null;

    const workflowConfig = vizExtension.params.workflow_config;
    if (!workflowConfig || typeof workflowConfig !== "object") return null;

    return workflowConfig as WorkflowConfig;
}

/**
 * Count workflow nodes from workflow configuration
 */
export function getWorkflowNodeCount(agent: AgentCardInfo): number {
    const config = getWorkflowConfig(agent);
    if (!config || !config.nodes) return 0;
    return config.nodes.length;
}

/**
 * Schema information extracted from agent card
 */
export interface AgentSchemas {
    inputSchema?: Record<string, unknown>;
    outputSchema?: Record<string, unknown>;
}

/**
 * Extract input/output schemas from agent card extensions
 */
export function getAgentSchemas(agent: AgentCardInfo): AgentSchemas {
    const extensions = agent.capabilities?.extensions;
    if (!extensions || extensions.length === 0) return {};

    const schemasExtension = extensions.find((ext: AgentExtension) => ext.uri === EXTENSION_URI_SCHEMAS);
    if (!schemasExtension?.params) return {};

    return {
        inputSchema: schemasExtension.params.input_schema as Record<string, unknown> | undefined,
        outputSchema: schemasExtension.params.output_schema as Record<string, unknown> | undefined,
    };
}
