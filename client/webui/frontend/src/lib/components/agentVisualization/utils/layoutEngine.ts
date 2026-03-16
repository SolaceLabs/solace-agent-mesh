/**
 * Layout engine for Agent Visualization
 *
 * Positions the agent node at top center with skills in a left column
 * and tools in a right column below it. Generates edges from the agent
 * to each child node.
 */

import type { Edge } from "../../workflowVisualization/utils/types";
import type { AgentDiagramConfig, AgentLayoutNode, AgentLayoutResult } from "./types";
import { AGENT_LAYOUT_CONSTANTS as C } from "./types";

/**
 * Process an agent config into a positioned layout for rendering.
 */
export function processAgentConfig(config: AgentDiagramConfig): AgentLayoutResult {
    const nodes: AgentLayoutNode[] = [];
    const edges: Edge[] = [];

    // --- Build child node lists ---

    const skillNodes: AgentLayoutNode[] = (config.skills || []).map((skill, i) => ({
        id: `skill-${i}`,
        type: "skill" as const,
        data: {
            label: skill.name,
            skillName: skill.name,
            skillDescription: skill.description,
        },
        x: 0,
        y: 0,
        width: C.NODE_WIDTHS.SKILL,
        height: C.NODE_HEIGHTS.SKILL,
    }));

    const toolNodes: AgentLayoutNode[] = [];

    // Add toolset groups (from toolsets array)
    if (config.toolsets) {
        for (let i = 0; i < config.toolsets.length; i++) {
            const name = config.toolsets[i];
            toolNodes.push({
                id: `toolset-${i}`,
                type: "toolset-group",
                data: {
                    label: formatToolsetName(name),
                    groupName: name,
                },
                x: 0,
                y: 0,
                width: C.NODE_WIDTHS.TOOLSET_GROUP,
                height: C.NODE_HEIGHTS.TOOLSET_GROUP,
            });
        }
    }

    // Add individual tools (from tools array, skip builtin-group since those are in toolsets)
    if (config.tools) {
        for (let i = 0; i < config.tools.length; i++) {
            const tool = config.tools[i];
            if (tool.tool_type === "builtin-group") continue;
            toolNodes.push({
                id: `tool-${i}`,
                type: "tool",
                data: {
                    label: tool.tool_name || `tool-${i}`,
                    toolName: tool.tool_name,
                    toolType: tool.tool_type,
                    toolDescription: tool.tool_description,
                },
                x: 0,
                y: 0,
                width: C.NODE_WIDTHS.TOOL,
                height: C.NODE_HEIGHTS.TOOL,
            });
        }
    }

    const hasSkills = skillNodes.length > 0;
    const hasTools = toolNodes.length > 0;

    // --- Calculate column dimensions ---

    const skillColumnHeight = hasSkills ? skillNodes.length * C.NODE_HEIGHTS.SKILL + (skillNodes.length - 1) * C.SPACING.HORIZONTAL : 0;
    const toolColumnHeight = hasTools ? toolNodes.length * C.NODE_HEIGHTS.TOOL + (toolNodes.length - 1) * C.SPACING.HORIZONTAL : 0;

    // --- Position agent header ---
    // Tools go to the right of the agent; skills go below the agent.

    const agentX = C.PADDING;
    const agentY = C.PADDING;

    // Tools: vertical column to the right, first tool vertically center-aligned with agent
    const toolColX = agentX + C.NODE_WIDTHS.AGENT_HEADER + C.SPACING.GROUP_GAP;
    const toolFirstY = agentY + (C.NODE_HEIGHTS.AGENT_HEADER - C.NODE_HEIGHTS.TOOL) / 2;

    // Skills: below the agent (and below the tool column if it extends further)
    const agentBottom = agentY + C.NODE_HEIGHTS.AGENT_HEADER;
    const toolsBottom = hasTools ? toolFirstY + toolColumnHeight : agentBottom;
    const skillTopY = Math.max(agentBottom, toolsBottom) + C.SPACING.VERTICAL;
    const skillColX = agentX + (C.NODE_WIDTHS.AGENT_HEADER - C.NODE_WIDTHS.SKILL) / 2;

    // Create agent header node
    const agentNode: AgentLayoutNode = {
        id: "agent-header",
        type: "agent-header",
        data: {
            label: config.name,
            agentName: config.name,
            description: config.description,
            instruction: config.instruction,
            inputModes: config.inputModes,
            outputModes: config.outputModes,
        },
        x: agentX,
        y: agentY,
        width: C.NODE_WIDTHS.AGENT_HEADER,
        height: C.NODE_HEIGHTS.AGENT_HEADER,
    };
    nodes.push(agentNode);

    // --- Position tools (right of agent, stacked vertically) ---

    for (let i = 0; i < toolNodes.length; i++) {
        const node = toolNodes[i];
        node.x = toolColX;
        node.y = toolFirstY + i * (C.NODE_HEIGHTS.TOOL + C.SPACING.HORIZONTAL);
        nodes.push(node);

        edges.push({
            id: `edge-agent-${node.id}`,
            source: "agent-header",
            target: node.id,
            sourceX: 0,
            sourceY: 0,
            targetX: 0,
            targetY: 0,
        });
    }

    // --- Position skills (below agent, centered under it) ---

    for (let i = 0; i < skillNodes.length; i++) {
        const node = skillNodes[i];
        node.x = skillColX;
        node.y = skillTopY + i * (C.NODE_HEIGHTS.SKILL + C.SPACING.HORIZONTAL);
        nodes.push(node);

        edges.push({
            id: `edge-agent-${node.id}`,
            source: "agent-header",
            target: node.id,
            sourceX: 0,
            sourceY: 0,
            targetX: 0,
            targetY: 0,
        });
    }

    // --- Calculate total dimensions ---

    const rightEdge = hasTools ? toolColX + C.NODE_WIDTHS.TOOL : agentX + C.NODE_WIDTHS.AGENT_HEADER;
    const totalWidth = rightEdge + C.PADDING;

    let bottomEdge = agentBottom;
    if (hasTools) bottomEdge = Math.max(bottomEdge, toolFirstY + toolColumnHeight);
    if (hasSkills) bottomEdge = Math.max(bottomEdge, skillTopY + skillColumnHeight);
    const totalHeight = bottomEdge + C.PADDING;

    return { nodes, edges, totalWidth, totalHeight };
}

/**
 * Format a toolset name for display (e.g., "artifact_management" -> "Artifact Management")
 */
function formatToolsetName(name: string): string {
    return name
        .split("_")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}
