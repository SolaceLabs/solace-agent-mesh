import React, { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { ReactFlow, ReactFlowProvider, MarkerType, useNodesState, type Node, type Edge as RFEdge, type NodeMouseHandler } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import type { PanZoomCanvasRef } from "@/lib/components/activities/FlowChart/PanZoomCanvas";
import { processWorkflowConfig } from "./utils/layoutEngine";
import type { LayoutNode, WorkflowFlowNodeData } from "./utils/types";
import StartFlowNode from "./nodes/StartFlowNode";
import EndFlowNode from "./nodes/EndFlowNode";
import AgentFlowNode from "./nodes/AgentFlowNode";
import WorkflowRefFlowNode from "./nodes/WorkflowRefFlowNode";
import SwitchFlowNode from "./nodes/SwitchFlowNode";
import MapFlowNode from "./nodes/MapFlowNode";
import LoopFlowNode from "./nodes/LoopFlowNode";
import ConditionPillFlowNode from "./nodes/ConditionPillFlowNode";
import { WorkflowDiagramEdge } from "./WorkflowDiagramEdge";
import "./workflowDiagram.css";

const nodeTypes = {
    "start": StartFlowNode,
    "end": EndFlowNode,
    "agent": AgentFlowNode,
    "workflow": WorkflowRefFlowNode,
    "switch": SwitchFlowNode,
    "map": MapFlowNode,
    "loop": LoopFlowNode,
    "condition": ConditionPillFlowNode,
};

const EMPTY_WORKFLOWS = new Set<string>();

const edgeTypes = {
    "workflow-edge": WorkflowDiagramEdge,
};

const DEFAULT_EDGE_MARKER = {
    type: MarkerType.ArrowClosed,
    width: 16,
    height: 16,
};

interface WorkflowDiagramProps {
    config: WorkflowConfig;
    knownWorkflows?: Set<string>;
    sidePanelWidth?: number;
    onNodeSelect?: (node: LayoutNode | null) => void;
    /** Controlled highlighted node IDs (from parent) */
    highlightedNodeIds?: Set<string>;
    /** Callback when highlight changes (for controlled mode) */
    onHighlightNodes?: (nodeIds: string[]) => void;
    /** Set of known node IDs (optional, will be computed if not provided) */
    knownNodeIds?: Set<string>;
    /** Callback when canvas transform (zoom/pan) changes */
    onTransformChange?: (transform: { scale: number; x: number; y: number }) => void;
    /** Ref to access canvas control methods (zoom, fit, etc.) */
    canvasRef?: React.RefObject<PanZoomCanvasRef | null>;
    /** Callback when content size changes (for fit-to-view calculations) */
    onContentSizeChange?: (width: number, height: number) => void;
    /** Current workflow name - used for building sub-workflow navigation URLs */
    currentWorkflowName?: string;
    /** Parent workflow path (for breadcrumb navigation) */
    parentPath?: string[];
    /** Additional CSS class for the root container (e.g. to override background) */
    className?: string;
}

/**
 * WorkflowDiagram - Main workflow visualization component using ReactFlow.
 * Shows workflow nodes in a top-to-bottom flow with smooth-step edge routing.
 */
const WorkflowDiagram: React.FC<WorkflowDiagramProps> = (props) => {
    const { className, ...innerProps } = props;
    return (
        <div className={`workflow-diagram ${className ?? "bg-card-background"} relative h-full w-full`}>
            <ReactFlowProvider>
                <WorkflowDiagramInner {...innerProps} />
            </ReactFlowProvider>
        </div>
    );
};

type WorkflowDiagramInnerProps = Omit<WorkflowDiagramProps, "className">;

const WorkflowDiagramInner: React.FC<WorkflowDiagramInnerProps> = ({
    config,
    knownWorkflows = EMPTY_WORKFLOWS,
    onNodeSelect,
    highlightedNodeIds: controlledHighlightedNodeIds,
    onHighlightNodes: controlledOnHighlightNodes,
    knownNodeIds: controlledKnownNodeIds,
    onTransformChange,
    onContentSizeChange,
    currentWorkflowName,
    parentPath,
}) => {
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());
    const [internalHighlightedNodeIds, setInternalHighlightedNodeIds] = useState<Set<string>>(new Set());

    // Calculate layout whenever config or collapsed state changes
    const layout = useMemo(() => {
        return processWorkflowConfig(config, collapsedNodes, knownWorkflows);
    }, [config, collapsedNodes, knownWorkflows]);

    // Notify parent of content size changes
    useEffect(() => {
        if (layout.totalWidth > 0 && layout.totalHeight > 0) {
            onContentSizeChange?.(layout.totalWidth, layout.totalHeight);
        }
    }, [layout.totalWidth, layout.totalHeight, onContentSizeChange]);

    // Build a set of all known node IDs for validating expression references
    const computedKnownNodeIds = useMemo(() => {
        const ids = new Set<string>();
        const collectNodeIds = (nodes: LayoutNode[]) => {
            for (const node of nodes) {
                ids.add(node.id);
                if (node.children && node.children.length > 0) {
                    collectNodeIds(node.children);
                }
            }
        };
        collectNodeIds(layout.nodes);
        return ids;
    }, [layout.nodes]);

    const knownNodeIds = controlledKnownNodeIds ?? computedKnownNodeIds;

    // Use controlled highlighted node IDs if provided, otherwise use internal state
    const highlightedNodeIds = controlledHighlightedNodeIds ?? internalHighlightedNodeIds;

    // Handle highlighting nodes when hovering over expressions
    const handleHighlightNodes = useCallback(
        (nodeIds: string[]) => {
            if (controlledOnHighlightNodes) {
                controlledOnHighlightNodes(nodeIds);
            } else {
                setInternalHighlightedNodeIds(new Set(nodeIds));
            }
        },
        [controlledOnHighlightNodes]
    );

    // Node click handler (for both RF clicks and child clicks inside containers)
    const handleNodeClick = useCallback(
        (node: LayoutNode) => {
            setSelectedNodeId(node.id);
            onNodeSelect?.(node);
        },
        [onNodeSelect]
    );

    // Handle expand
    const handleExpand = useCallback((nodeId: string) => {
        setCollapsedNodes(prev => {
            const next = new Set(prev);
            next.delete(nodeId);
            return next;
        });
    }, []);

    // Handle collapse
    const handleCollapse = useCallback((nodeId: string) => {
        setCollapsedNodes(prev => {
            const next = new Set(prev);
            next.add(nodeId);
            return next;
        });
    }, []);

    // Convert layout nodes to ReactFlow nodes
    const initialNodes = useMemo<Node<WorkflowFlowNodeData>[]>(() => {
        return layout.nodes.map(n => ({
            id: n.id,
            type: n.type,
            position: { x: n.x, y: n.y },
            data: {
                layoutNode: n,
                onNodeClick: handleNodeClick,
                onExpand: handleExpand,
                onCollapse: handleCollapse,
                onHighlightNodes: handleHighlightNodes,
                knownNodeIds,
                currentWorkflowName,
                parentPath,
            } as WorkflowFlowNodeData,
            width: n.width,
            height: n.height,
            selectable: true,
        }));
    }, [layout.nodes, handleNodeClick, handleExpand, handleCollapse, handleHighlightNodes, knownNodeIds, currentWorkflowName, parentPath]);

    const [nodes, setNodes, onNodesChange] = useNodesState<Node<WorkflowFlowNodeData>>(initialNodes);

    // Re-sync when config/layout changes
    useEffect(() => {
        setNodes(initialNodes);
    }, [initialNodes, setNodes]);

    // Build pill↔target maps for drag-group synchronization
    const { pillToTarget, targetToPills } = useMemo(() => {
        const p2t = new Map<string, string>();
        const t2p = new Map<string, string[]>();
        for (const n of layout.nodes) {
            if (n.type === "condition" && n.data.targetNodeId) {
                p2t.set(n.id, n.data.targetNodeId);
                const existing = t2p.get(n.data.targetNodeId);
                if (existing) {
                    existing.push(n.id);
                } else {
                    t2p.set(n.data.targetNodeId, [n.id]);
                }
            }
        }
        return { pillToTarget: p2t, targetToPills: t2p };
    }, [layout.nodes]);

    // Drag-group: capture starting positions of dragged node + paired nodes
    const dragStartPositions = useRef<Map<string, { x: number; y: number }>>(new Map());

    const handleNodeDragStart: NodeMouseHandler<Node<WorkflowFlowNodeData>> = useCallback(
        (_event, node) => {
            dragStartPositions.current.clear();
            dragStartPositions.current.set(node.id, { x: node.position.x, y: node.position.y });

            // Collect paired node IDs
            const pairedIds: string[] = [];
            const targetId = pillToTarget.get(node.id);
            if (targetId) pairedIds.push(targetId);
            const pillIds = targetToPills.get(node.id);
            if (pillIds) pairedIds.push(...pillIds);

            // Capture their current positions from state
            for (const pairedId of pairedIds) {
                const pairedNode = nodes.find(n => n.id === pairedId);
                if (pairedNode) {
                    dragStartPositions.current.set(pairedId, { x: pairedNode.position.x, y: pairedNode.position.y });
                }
            }
        },
        [pillToTarget, targetToPills, nodes]
    );

    const handleNodeDrag: NodeMouseHandler<Node<WorkflowFlowNodeData>> = useCallback(
        (_event, node) => {
            const startPos = dragStartPositions.current.get(node.id);
            if (!startPos || dragStartPositions.current.size <= 1) return;

            const dx = node.position.x - startPos.x;
            const dy = node.position.y - startPos.y;

            setNodes(prev => prev.map(n => {
                if (n.id === node.id) return n; // Already moved by ReactFlow
                const nStart = dragStartPositions.current.get(n.id);
                if (!nStart) return n; // Not a paired node
                return { ...n, position: { x: nStart.x + dx, y: nStart.y + dy } };
            }));
        },
        [setNodes]
    );

    // Convert layout edges to ReactFlow edges
    const rfEdges = useMemo<RFEdge[]>(() => {
        return layout.edges.map(e => ({
            id: e.id,
            source: e.source,
            target: e.target,
            sourceHandle: "bottom",
            targetHandle: "top",
            type: "workflow-edge",
            data: { isStraight: e.isStraight },
            // No arrow marker on edges going TO condition pills
            markerEnd: e.target.startsWith("__condition_") ? undefined : DEFAULT_EDGE_MARKER,
        }));
    }, [layout.edges]);

    // ReactFlow node click handler
    const handleRFNodeClick: NodeMouseHandler<Node<WorkflowFlowNodeData>> = useCallback(
        (_event, node) => {
            handleNodeClick(node.data.layoutNode);
        },
        [handleNodeClick]
    );

    // Handle pane click — deselect
    const handlePaneClick = useCallback(() => {
        setSelectedNodeId(null);
        onNodeSelect?.(null);
    }, [onNodeSelect]);

    // Merge selection + highlight state into nodes
    const nodesWithState = useMemo<Node<WorkflowFlowNodeData>[]>(() => {
        return nodes.map(n => ({
            ...n,
            selected: n.id === selectedNodeId,
            data: {
                ...n.data,
                selectedNodeId,
                highlightedNodeIds,
            },
        }));
    }, [nodes, selectedNodeId, highlightedNodeIds]);

    return (
        <ReactFlow
                nodes={nodesWithState}
                edges={rfEdges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodesChange={onNodesChange}
                onNodeClick={handleRFNodeClick}
                onNodeDragStart={handleNodeDragStart}
                onNodeDrag={handleNodeDrag}
                onPaneClick={handlePaneClick}
                onMove={onTransformChange ? (_event, viewport) => onTransformChange({ scale: viewport.zoom, x: viewport.x, y: viewport.y }) : undefined}
                nodesDraggable={true}
                nodesConnectable={false}
                elementsSelectable={true}
                fitView
                fitViewOptions={{ padding: 0.15 }}
                minZoom={0.25}
                maxZoom={2}
                proOptions={{ hideAttribution: true }}
            />
    );
};

export default WorkflowDiagram;
