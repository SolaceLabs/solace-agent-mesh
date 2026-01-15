import React, { useCallback, useRef, useEffect } from "react";
import type { LayoutNode } from "./utils/types";
import StartNode from "./nodes/StartNode";
import EndNode from "./nodes/EndNode";
import AgentNode from "./nodes/AgentNode";
import WorkflowRefNode from "./nodes/WorkflowRefNode";
import MapNode from "./nodes/MapNode";
import LoopNode from "./nodes/LoopNode";
import SwitchNode from "./nodes/SwitchNode";
import ConditionPillNode from "./nodes/ConditionPillNode";

interface WorkflowNodeRendererProps {
    nodes: LayoutNode[];
    selectedNodeId?: string;
    highlightedNodeIds?: Set<string>;
    onNodeClick?: (node: LayoutNode) => void;
    onExpand?: (nodeId: string) => void;
    onCollapse?: (nodeId: string) => void;
    onHighlightNodes?: (nodeIds: string[]) => void;
    knownNodeIds?: Set<string>;
    nodeRefs: React.MutableRefObject<Map<string, HTMLDivElement>>;
    /** Current workflow name - used for building sub-workflow navigation URLs */
    currentWorkflowName?: string;
    /** Parent workflow path (for breadcrumb navigation) */
    parentPath?: string[];
}

/**
 * WorkflowNodeRenderer - Renders positioned nodes at their absolute positions
 * Handles recursive rendering for container nodes
 */
const WorkflowNodeRenderer: React.FC<WorkflowNodeRendererProps> = ({
    nodes,
    selectedNodeId,
    highlightedNodeIds,
    onNodeClick,
    onExpand,
    onCollapse,
    onHighlightNodes,
    knownNodeIds,
    nodeRefs,
    currentWorkflowName,
    parentPath,
}) => {
    // Track mounted node IDs for cleanup
    const mountedNodeIds = useRef<Set<string>>(new Set());

    // Cleanup refs for nodes that are no longer rendered
    useEffect(() => {
        const currentNodeIds = new Set(nodes.map(n => n.id));

        // Remove refs for nodes that are no longer in the list
        for (const nodeId of mountedNodeIds.current) {
            if (!currentNodeIds.has(nodeId)) {
                nodeRefs.current.delete(nodeId);
            }
        }

        mountedNodeIds.current = currentNodeIds;
    }, [nodes, nodeRefs]);

    // Create a stable ref callback using a Map
    const setNodeRef = useCallback(
        (nodeId: string, element: HTMLDivElement | null) => {
            if (element) {
                nodeRefs.current.set(nodeId, element);
            } else {
                nodeRefs.current.delete(nodeId);
            }
        },
        [nodeRefs]
    );
    /**
     * Render children for container nodes (map, loop)
     */
    const renderChildren = (children: LayoutNode[]) => {
        return children.map(child => (
            <div
                key={child.id}
                style={{
                    position: "relative",
                }}
            >
                {renderNode(child)}
            </div>
        ));
    };

    /**
     * Render a single node based on its type
     */
    const renderNode = (node: LayoutNode) => {
        const isSelected = node.id === selectedNodeId;
        const isHighlighted = highlightedNodeIds?.has(node.id) ?? false;
        const commonProps = {
            node,
            isSelected,
            isHighlighted,
            onClick: onNodeClick,
            onExpand,
            onCollapse,
            onHighlightNodes,
            knownNodeIds,
            currentWorkflowName,
            parentPath,
        };

        switch (node.type) {
            case "start":
                return <StartNode {...commonProps} />;

            case "end":
                return <EndNode {...commonProps} />;

            case "agent":
                return <AgentNode {...commonProps} />;

            case "workflow":
                return <WorkflowRefNode {...commonProps} />;

            case "map":
                return <MapNode {...commonProps} renderChildren={renderChildren} />;

            case "loop":
                return <LoopNode {...commonProps} renderChildren={renderChildren} />;

            case "switch":
                return <SwitchNode {...commonProps} />;

            case "condition":
                return <ConditionPillNode {...commonProps} />;

            default:
                return null;
        }
    };

    return (
        <>
            {nodes.map(node => (
                <div
                    key={node.id}
                    ref={el => setNodeRef(node.id, el)}
                    style={{
                        position: "absolute",
                        left: `${node.x}px`,
                        top: `${node.y}px`,
                    }}
                >
                    {renderNode(node)}
                </div>
            ))}
        </>
    );
};

export default WorkflowNodeRenderer;
