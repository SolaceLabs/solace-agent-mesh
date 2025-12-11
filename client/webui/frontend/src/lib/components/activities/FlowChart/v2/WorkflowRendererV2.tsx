import React, { useMemo, useState } from "react";
import type { VisualizerStep } from "@/lib/types";
import { processSteps } from "./utils/layoutEngine";
import type { LayoutNode, Edge } from "./utils/types";
import AgentNodeV2 from "./nodes/AgentNodeV2";
import UserNodeV2 from "./nodes/UserNodeV2";
import WorkflowGroupV2 from "./nodes/WorkflowGroupV2";
import EdgeLayerV2 from "./EdgeLayerV2";

/**
 * Recursively collapse nested agents (level > 0) and recalculate their dimensions
 */
function collapseNestedAgents(node: LayoutNode, nestingLevel: number): LayoutNode {
    // Special handling for Map/Fork nodes (pill variant with parallel branches)
    // Don't collapse these - instead, flatten their parallel branches
    if (node.type === 'agent' && node.data.variant === 'pill' && node.parallelBranches && node.parallelBranches.length > 0) {
        // Flatten all branches into a single array of children
        const flattenedChildren: LayoutNode[] = [];
        for (const branch of node.parallelBranches) {
            for (const child of branch) {
                flattenedChildren.push(collapseNestedAgents(child, nestingLevel + 1));
            }
        }

        // Recalculate height based on flattened children
        const padding = 16;
        const gap = 16;

        const childrenHeight = flattenedChildren.reduce((sum, child, idx) => {
            return sum + child.height + (idx < flattenedChildren.length - 1 ? gap : 0);
        }, 0);

        // Height includes the pill itself (40px) + padding + children
        const newHeight = 40 + padding * 2 + childrenHeight;

        return {
            ...node,
            children: flattenedChildren,
            parallelBranches: undefined, // Clear parallel branches
            height: newHeight,
        };
    }

    // For regular agents at level > 0, collapse them
    if (node.type === 'agent' && nestingLevel > 0) {
        // Collapsed agent: just header + padding, no children
        const headerHeight = 50;
        const padding = 16;
        const collapsedHeight = headerHeight + padding;

        return {
            ...node,
            children: [],
            parallelBranches: undefined,
            height: collapsedHeight,
        };
    }

    // For workflow groups at level > 0, collapse nested agents inside them
    if (node.type === 'group' && nestingLevel > 0) {
        const collapsedChildren = node.children.map(child => collapseNestedAgents(child, nestingLevel + 1));

        // Recalculate height based on collapsed children
        const padding = 24; // p-6
        const gap = 16;
        const childrenHeight = collapsedChildren.reduce((sum, child, idx) => {
            return sum + child.height + (idx < collapsedChildren.length - 1 ? gap : 0);
        }, 0);
        const newHeight = padding * 2 + childrenHeight;

        return {
            ...node,
            children: collapsedChildren,
            height: newHeight,
        };
    }

    // For top-level nodes or non-agent nodes, process children recursively
    if (node.children.length > 0) {
        const collapsedChildren = node.children.map(child => collapseNestedAgents(child, nestingLevel + 1));

        // Recalculate height
        const headerHeight = node.type === 'agent' ? 50 : 0;
        const padding = node.type === 'agent' ? 16 : (node.type === 'group' ? 24 : 0);
        const gap = 16;

        const childrenHeight = collapsedChildren.reduce((sum, child, idx) => {
            return sum + child.height + (idx < collapsedChildren.length - 1 ? gap : 0);
        }, 0);

        const newHeight = headerHeight + padding * 2 + childrenHeight;

        return {
            ...node,
            children: collapsedChildren,
            height: newHeight,
        };
    }

    // Handle parallel branches - flatten them into sequential children when collapsed
    if (node.parallelBranches && node.parallelBranches.length > 0) {
        // Flatten all branches into a single array of children
        const flattenedChildren: LayoutNode[] = [];
        for (const branch of node.parallelBranches) {
            for (const child of branch) {
                flattenedChildren.push(collapseNestedAgents(child, nestingLevel + 1));
            }
        }

        // Recalculate height based on flattened children
        const headerHeight = node.type === 'agent' ? 50 : 0;
        const padding = node.type === 'agent' ? 16 : (node.type === 'group' ? 24 : 0);
        const gap = 16;

        const childrenHeight = flattenedChildren.reduce((sum, child, idx) => {
            return sum + child.height + (idx < flattenedChildren.length - 1 ? gap : 0);
        }, 0);

        const newHeight = headerHeight + padding * 2 + childrenHeight;

        return {
            ...node,
            children: flattenedChildren,
            parallelBranches: undefined, // Clear parallel branches
            height: newHeight,
        };
    }

    return node;
}

interface WorkflowRendererV2Props {
    processedSteps: VisualizerStep[];
    agentNameMap: Record<string, string>;
    selectedStepId?: string | null;
    onNodeClick?: (node: LayoutNode) => void;
    onEdgeClick?: (edge: Edge) => void;
    showDetail?: boolean;
}

const WorkflowRendererV2: React.FC<WorkflowRendererV2Props> = ({
    processedSteps,
    agentNameMap,
    selectedStepId,
    onNodeClick,
    onEdgeClick,
    showDetail = true,
}) => {
    const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

    // Process steps into layout
    const baseLayoutResult = useMemo(() => {
        if (!processedSteps || processedSteps.length === 0) {
            return { nodes: [], edges: [], totalWidth: 800, totalHeight: 600 };
        }

        try {
            return processSteps(processedSteps, agentNameMap);
        } catch (error) {
            console.error("[WorkflowRendererV2] Error processing steps:", error);
            return { nodes: [], edges: [], totalWidth: 800, totalHeight: 600 };
        }
    }, [processedSteps, agentNameMap]);

    // Collapse nested agents when showDetail is false
    const layoutResult = useMemo(() => {
        if (showDetail) {
            return baseLayoutResult;
        }

        // Deep clone and collapse nodes
        const collapsedNodes = baseLayoutResult.nodes.map(node => collapseNestedAgents(node, 0));
        return {
            ...baseLayoutResult,
            nodes: collapsedNodes,
        };
    }, [baseLayoutResult, showDetail]);

    const { nodes, edges, totalWidth, totalHeight } = layoutResult;

    // Handle node click
    const handleNodeClick = (node: LayoutNode) => {
        onNodeClick?.(node);
    };

    // Handle edge click
    const handleEdgeClick = (edge: Edge) => {
        setSelectedEdgeId(edge.id);
        onEdgeClick?.(edge);
    };

    // Render a top-level node
    const renderNode = (node: LayoutNode, index: number) => {
        const isSelected = node.data.visualizerStepId === selectedStepId;
        const nextNode = nodes[index + 1];

        const nodeProps = {
            node,
            isSelected,
            onClick: handleNodeClick,
            onChildClick: handleNodeClick, // For nested clicks
        };

        let component: React.ReactNode;

        switch (node.type) {
            case 'agent':
                component = <AgentNodeV2 {...nodeProps} />;
                break;
            case 'user':
                component = <UserNodeV2 {...nodeProps} />;
                break;
            case 'group':
                component = <WorkflowGroupV2 {...nodeProps} />;
                break;
            default:
                return null;
        }

        return (
            <React.Fragment key={node.id}>
                {component}
                {/* Add connector line between nodes */}
                {index < nodes.length - 1 && (
                    <div className="w-0.5 h-4 bg-gray-400 dark:bg-gray-600 my-0" />
                )}
            </React.Fragment>
        );
    };

    if (nodes.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">
                {processedSteps.length > 0 ? "Processing flow data..." : "No steps to display in flow chart."}
            </div>
        );
    }

    return (
        <div
            className="flex flex-col items-center p-12"
            style={{
                minWidth: "100%",
                minHeight: "100%",
            }}
        >
            {/* Nodes in vertical flow */}
            {nodes.map((node, index) => renderNode(node, index))}
        </div>
    );
};

export default WorkflowRendererV2;
