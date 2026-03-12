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

    // --- Calculate total width and position columns ---

    let totalChildrenWidth: number;
    let skillColumnX: number;
    let toolColumnX: number;

    if (hasSkills && hasTools) {
        totalChildrenWidth = C.NODE_WIDTHS.SKILL + C.SPACING.GROUP_GAP + C.NODE_WIDTHS.TOOL;
        skillColumnX = 0;
        toolColumnX = C.NODE_WIDTHS.SKILL + C.SPACING.GROUP_GAP;
    } else if (hasSkills) {
        totalChildrenWidth = C.NODE_WIDTHS.SKILL;
        skillColumnX = 0;
        toolColumnX = 0;
    } else if (hasTools) {
        totalChildrenWidth = C.NODE_WIDTHS.TOOL;
        skillColumnX = 0;
        toolColumnX = 0;
    } else {
        totalChildrenWidth = 0;
        skillColumnX = 0;
        toolColumnX = 0;
    }

    const contentWidth = Math.max(C.NODE_WIDTHS.AGENT_HEADER, totalChildrenWidth);
    const totalWidth = contentWidth + C.PADDING * 2;

    // Center agent header
    const agentX = C.PADDING + (contentWidth - C.NODE_WIDTHS.AGENT_HEADER) / 2;
    const agentY = C.PADDING;

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

    // --- Position child columns ---

    const childrenTopY = agentY + C.NODE_HEIGHTS.AGENT_HEADER + C.SPACING.VERTICAL;

    // Center columns under the content area
    const childrenOffsetX = C.PADDING + (contentWidth - totalChildrenWidth) / 2;

    // Position skills (left column)
    for (let i = 0; i < skillNodes.length; i++) {
        const node = skillNodes[i];
        node.x = childrenOffsetX + skillColumnX;
        node.y = childrenTopY + i * (C.NODE_HEIGHTS.SKILL + C.SPACING.HORIZONTAL);
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

    // Position tools (right column)
    for (let i = 0; i < toolNodes.length; i++) {
        const node = toolNodes[i];
        node.x = childrenOffsetX + toolColumnX;
        node.y = childrenTopY + i * (C.NODE_HEIGHTS.TOOL + C.SPACING.HORIZONTAL);
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

    // --- Calculate total height ---

    const maxColumnHeight = Math.max(skillColumnHeight, toolColumnHeight);
    const totalHeight = hasSkills || hasTools ? childrenTopY + maxColumnHeight + C.PADDING : agentY + C.NODE_HEIGHTS.AGENT_HEADER + C.PADDING;

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
