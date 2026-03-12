/**
 * Type definitions for Agent Visualization components
 */

import type { Edge } from "../../workflowVisualization/utils/types";

/**
 * Visual node types for agent diagram
 */
export type AgentVisualNodeType = "agent-header" | "tool" | "skill" | "toolset-group";

/**
 * Represents a positioned node in the agent visual layout
 */
export interface AgentLayoutNode {
    id: string;
    type: AgentVisualNodeType;
    data: {
        label: string;
        // Agent header fields
        agentName?: string;
        description?: string;
        instruction?: string;
        inputModes?: string[];
        outputModes?: string[];
        // Tool fields
        toolType?: string; // "builtin", "sam_remote", "mcp"
        toolName?: string;
        toolDescription?: string;
        // Skill fields
        skillName?: string;
        skillDescription?: string;
        // Toolset group fields
        groupName?: string;
    };
    x: number;
    y: number;
    width: number;
    height: number;
}

/**
 * Input configuration for the agent diagram
 */
export interface AgentDiagramConfig {
    name: string;
    description?: string;
    instruction?: string;
    skills?: Array<{ name: string; description?: string }>;
    tools?: Array<{
        tool_type: string;
        tool_name?: string;
        group_name?: string;
        tool_description?: string;
    }>;
    toolsets?: string[];
    inputModes?: string[];
    outputModes?: string[];
}

/**
 * Result of agent layout calculation
 */
export interface AgentLayoutResult {
    nodes: AgentLayoutNode[];
    edges: Edge[];
    totalWidth: number;
    totalHeight: number;
}

/**
 * Common props for agent node components
 */
export interface AgentNodeProps {
    node: AgentLayoutNode;
    isSelected?: boolean;
    onClick?: (node: AgentLayoutNode) => void;
}

/**
 * Layout constants for agent diagram sizing
 */
export const AGENT_LAYOUT_CONSTANTS = {
    NODE_WIDTHS: {
        AGENT_HEADER: 320,
        TOOL: 220,
        SKILL: 220,
        TOOLSET_GROUP: 220,
    },
    NODE_HEIGHTS: {
        AGENT_HEADER: 72,
        TOOL: 48,
        SKILL: 48,
        TOOLSET_GROUP: 48,
    },
    SPACING: {
        VERTICAL: 60,
        HORIZONTAL: 16,
        GROUP_GAP: 48,
    },
    PADDING: 40,
};
