import type { AgentCardInfo, AgentExtension } from "@/lib/types";

const EXTENSION_URI_WORKFLOW_VISUALIZATION = "https://solace.com/a2a/extensions/sam/workflow-visualization";
const EXTENSION_URI_AGENT_TYPE = "https://solace.com/a2a/extensions/agent-type";

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
 * Extract mermaid diagram source from workflow agent card
 */
export function getMermaidSource(agent: AgentCardInfo): string | null {
    const extensions = agent.capabilities?.extensions;
    if (!extensions || extensions.length === 0) return null;

    const vizExtension = extensions.find((ext: AgentExtension) => ext.uri === EXTENSION_URI_WORKFLOW_VISUALIZATION);
    if (!vizExtension?.params) return null;

    const mermaidSource = vizExtension.params.mermaid_source;
    return typeof mermaidSource === 'string' ? mermaidSource : null;
}

/**
 * Count workflow nodes from mermaid source
 * This is a simple heuristic based on mermaid node definitions
 */
export function getWorkflowNodeCount(mermaidSource: string): number {
    if (!mermaidSource) return 0;

    // Count node definitions in mermaid syntax
    // Nodes are typically defined as: nodeId[...] or nodeId{...} or nodeId(...)
    const nodeMatches = mermaidSource.match(/\w+[\[\{\(]/g);

    if (!nodeMatches) return 0;

    // Create a set to count unique nodes (avoid counting edges)
    const uniqueNodes = new Set(nodeMatches.map(match => match.replace(/[\[\{\(]/, '')));

    return uniqueNodes.size;
}
