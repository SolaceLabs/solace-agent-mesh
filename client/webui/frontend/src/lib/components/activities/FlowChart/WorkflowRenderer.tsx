import React, { useMemo, useState } from "react";
import type { VisualizerStep } from "@/lib/types";
import { processSteps } from "./utils/layoutEngine";
import type { LayoutNode, Edge } from "./utils/types";
import AgentNode from "./nodes/AgentNode";
import UserNode from "./nodes/UserNode";
import WorkflowGroup from "./nodes/WorkflowGroup";
// import EdgeLayer from "./EdgeLayer";

/**
 * Check if a node or any of its descendants has status 'in-progress'
 */
function hasProcessingDescendant(node: LayoutNode): boolean {
    if (node.data.status === "in-progress") {
        return true;
    }
    for (const child of node.children) {
        if (hasProcessingDescendant(child)) {
            return true;
        }
    }
    if (node.parallelBranches) {
        for (const branch of node.parallelBranches) {
            for (const branchNode of branch) {
                if (hasProcessingDescendant(branchNode)) {
                    return true;
                }
            }
        }
    }
    return false;
}

/**
 * Recursively collapse nested agents (level > 0) and recalculate their dimensions
 */
function collapseNestedAgents(node: LayoutNode, nestingLevel: number, expandedNodeIds: Set<string> = new Set()): LayoutNode {
    // Check if this node is manually expanded
    const isManuallyExpanded = expandedNodeIds.has(node.id);

    // Special handling for Map/Fork nodes (pill variant with parallel branches)
    // Don't collapse these - instead, flatten their parallel branches
    if (node.type === "agent" && node.data.variant === "pill" && node.parallelBranches && node.parallelBranches.length > 0) {
        // Flatten all branches into a single array of children
        const flattenedChildren: LayoutNode[] = [];
        for (const branch of node.parallelBranches) {
            for (const child of branch) {
                flattenedChildren.push(collapseNestedAgents(child, nestingLevel + 1, expandedNodeIds));
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

    // For regular agents at level > 0, collapse them (unless manually expanded)
    if (node.type === "agent" && nestingLevel > 0) {
        if (isManuallyExpanded) {
            // Node is manually expanded - process children but mark as expanded
            const expandedChildren = node.children.map(child => collapseNestedAgents(child, nestingLevel + 1, expandedNodeIds));

            // Recalculate height
            const headerHeight = 50;
            const padding = 16;
            const gap = 16;
            const childrenHeight = expandedChildren.reduce((sum, child, idx) => {
                return sum + child.height + (idx < expandedChildren.length - 1 ? gap : 0);
            }, 0);
            const newHeight = headerHeight + padding * 2 + childrenHeight;

            return {
                ...node,
                children: expandedChildren,
                height: newHeight,
                data: {
                    ...node.data,
                    isExpanded: true, // Mark as expanded so collapse icon shows
                },
            };
        }

        // Check if any children are processing before we collapse them
        const childrenProcessing = hasProcessingDescendant(node);

        // Collapsed agent: just header + padding, no children
        const headerHeight = 50;
        const padding = 16;
        const collapsedHeight = headerHeight + padding;

        return {
            ...node,
            children: [],
            parallelBranches: undefined,
            height: collapsedHeight,
            data: {
                ...node.data,
                isCollapsed: true,
                // If children were processing, mark the collapsed node as processing
                hasProcessingChildren: childrenProcessing,
            },
        };
    }

    // For workflow groups, collapse them entirely (unless manually expanded)
    if (node.type === "group") {
        if (isManuallyExpanded) {
            // Node is manually expanded - process children but mark as expanded
            const expandedChildren = node.children.map(child => collapseNestedAgents(child, nestingLevel + 1, expandedNodeIds));

            // Recalculate height (group uses 24px padding)
            const padding = 24;
            const gap = 16;
            const childrenHeight = expandedChildren.reduce((sum, child, idx) => {
                return sum + child.height + (idx < expandedChildren.length - 1 ? gap : 0);
            }, 0);
            const newHeight = padding * 2 + childrenHeight;

            return {
                ...node,
                children: expandedChildren,
                height: newHeight,
                data: {
                    ...node.data,
                    isExpanded: true, // Mark as expanded so collapse icon shows
                },
            };
        }

        // Check if any children are processing before we collapse them
        const childrenProcessing = hasProcessingDescendant(node);

        // Collapsed workflow: just header + padding, no children
        const headerHeight = 50;
        const padding = 16;
        const collapsedHeight = headerHeight + padding;

        return {
            ...node,
            children: [],
            parallelBranches: undefined,
            height: collapsedHeight,
            data: {
                ...node.data,
                isCollapsed: true,
                // If children were processing, mark the collapsed node as processing
                hasProcessingChildren: childrenProcessing,
            },
        };
    }

    // For top-level nodes or non-agent nodes, process children recursively
    if (node.children.length > 0) {
        const collapsedChildren = node.children.map(child => collapseNestedAgents(child, nestingLevel + 1, expandedNodeIds));

        // Recalculate height
        const headerHeight = node.type === "agent" ? 50 : 0;
        const padding = node.type === "agent" ? 16 : (node.type as string) === "group" ? 24 : 0;
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
                flattenedChildren.push(collapseNestedAgents(child, nestingLevel + 1, expandedNodeIds));
            }
        }

        // Recalculate height based on flattened children
        const headerHeight = node.type === "agent" ? 50 : 0;
        const padding = node.type === "agent" ? 16 : (node.type as string) === "group" ? 24 : 0;
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

interface WorkflowRendererProps {
    processedSteps: VisualizerStep[];
    agentNameMap: Record<string, string>;
    selectedStepId?: string | null;
    onNodeClick?: (node: LayoutNode) => void;
    onEdgeClick?: (edge: Edge) => void;
    showDetail?: boolean;
}

const WorkflowRenderer: React.FC<WorkflowRendererProps> = ({ processedSteps, agentNameMap, selectedStepId, onNodeClick, onEdgeClick, showDetail = true }) => {
    const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());

    // Handle expand toggle for a node
    const handleExpandNode = (nodeId: string) => {
        setExpandedNodeIds(prev => {
            const newSet = new Set(prev);
            if (newSet.has(nodeId)) {
                newSet.delete(nodeId);
            } else {
                newSet.add(nodeId);
            }
            return newSet;
        });
    };

    // Process steps into layout
    const baseLayoutResult = useMemo(() => {
        if (!processedSteps || processedSteps.length === 0) {
            return { nodes: [], edges: [], totalWidth: 800, totalHeight: 600 };
        }

        try {
            return processSteps(processedSteps, agentNameMap);
        } catch (error) {
            console.error("[WorkflowRenderer] Error processing steps:", error);
            return { nodes: [], edges: [], totalWidth: 800, totalHeight: 600 };
        }
    }, [processedSteps, agentNameMap]);

    // Collapse nested agents when showDetail is false
    const layoutResult = useMemo(() => {
        if (showDetail) {
            return baseLayoutResult;
        }

        // Deep clone and collapse nodes (respecting manually expanded nodes)
        const collapsedNodes = baseLayoutResult.nodes.map(node => collapseNestedAgents(node, 0, expandedNodeIds));
        return {
            ...baseLayoutResult,
            nodes: collapsedNodes,
        };
    }, [baseLayoutResult, showDetail, expandedNodeIds]);

    const { nodes } = layoutResult;

    // Handle node click
    const handleNodeClick = (node: LayoutNode) => {
        onNodeClick?.(node);
    };

    // Handle edge click - currently unused but kept for future use
    const handleEdgeClick = (edge: Edge) => {
        onEdgeClick?.(edge);
    };
    void handleEdgeClick; // Suppress unused variable warning

    // Render a top-level node
    const renderNode = (node: LayoutNode, index: number) => {
        const isSelected = node.data.visualizerStepId === selectedStepId;

        const nodeProps = {
            node,
            isSelected,
            onClick: handleNodeClick,
            onChildClick: handleNodeClick, // For nested clicks
            onExpand: handleExpandNode,
            onCollapse: handleExpandNode, // Same handler - toggles expanded state
        };

        let component: React.ReactNode;

        switch (node.type) {
            case "agent":
                component = <AgentNode {...nodeProps} />;
                break;
            case "user":
                component = <UserNode {...nodeProps} />;
                break;
            case "group":
                component = <WorkflowGroup {...nodeProps} />;
                break;
            default:
                return null;
        }

        return (
            <React.Fragment key={node.id}>
                {component}
                {/* Add connector line between nodes */}
                {index < nodes.length - 1 && <div className="my-0 h-4 w-0.5 bg-gray-400 dark:bg-gray-600" />}
            </React.Fragment>
        );
    };

    if (nodes.length === 0) {
        return <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">{processedSteps.length > 0 ? "Processing flow data..." : "No steps to display in flow chart."}</div>;
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

export default WorkflowRenderer;
