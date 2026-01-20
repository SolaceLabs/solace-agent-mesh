import React, { useMemo, useState, useRef, useEffect, useCallback } from "react";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import PanZoomCanvas, { type PanZoomCanvasRef } from "@/lib/components/activities/FlowChart/PanZoomCanvas";
import { processWorkflowConfig } from "./utils/layoutEngine";
import type { LayoutNode, Edge } from "./utils/types";
import WorkflowNodeRenderer from "./WorkflowNodeRenderer";
import EdgeLayer from "./edges/EdgeLayer";

/** Node position and dimensions */
interface NodePosition {
    x: number;
    y: number;
    width: number;
    height: number;
}

/**
 * Build a flat map of all node positions from the layout tree
 * Traverses nested children and accumulates offsets for absolute positions
 */
function buildNodePositionMap(nodes: LayoutNode[], offsetX = 0, offsetY = 0): Map<string, NodePosition> {
    const positions = new Map<string, NodePosition>();

    for (const node of nodes) {
        const absoluteX = node.x + offsetX;
        const absoluteY = node.y + offsetY;

        positions.set(node.id, {
            x: absoluteX,
            y: absoluteY,
            width: node.width,
            height: node.height,
        });

        // Recursively process children (for Map/Loop containers)
        if (node.children && node.children.length > 0) {
            const childPositions = buildNodePositionMap(node.children, absoluteX, absoluteY);
            for (const [childId, childPos] of childPositions) {
                positions.set(childId, childPos);
            }
        }
    }

    return positions;
}

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
}

/**
 * WorkflowDiagram - Main diagram component with pan/zoom canvas
 * Manages layout calculation and collapse state
 */
const WorkflowDiagram: React.FC<WorkflowDiagramProps> = ({
    config,
    knownWorkflows = new Set(),
    sidePanelWidth = 0,
    onNodeSelect,
    highlightedNodeIds: controlledHighlightedNodeIds,
    onHighlightNodes: controlledOnHighlightNodes,
    knownNodeIds: controlledKnownNodeIds,
    onTransformChange,
    canvasRef: externalCanvasRef,
    onContentSizeChange,
    currentWorkflowName,
    parentPath,
}) => {
    const internalCanvasRef = useRef<PanZoomCanvasRef>(null);
    const canvasRef = externalCanvasRef || internalCanvasRef;
    const containerRef = useRef<HTMLDivElement>(null);
    const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());
    const [hasUserInteracted, setHasUserInteracted] = useState(false);
    const [internalHighlightedNodeIds, setInternalHighlightedNodeIds] = useState<Set<string>>(new Set());

    // Track mouse position to distinguish click from drag
    const mouseDownPos = useRef<{ x: number; y: number } | null>(null);
    const isDragging = useRef(false);
    const lastClickTime = useRef(0);

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
    // Use controlled prop if provided, otherwise compute from layout
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
    const handleHighlightNodes = useCallback((nodeIds: string[]) => {
        if (controlledOnHighlightNodes) {
            controlledOnHighlightNodes(nodeIds);
        } else {
            setInternalHighlightedNodeIds(new Set(nodeIds));
        }
    }, [controlledOnHighlightNodes]);

    // Calculate edges from layout positions (not DOM measurements)
    // This avoids issues with pan/zoom transforms affecting edge positions
    const calculatedEdges = useMemo(() => {
        if (layout.nodes.length === 0) return [];

        // Build flat map of all node positions from layout tree
        const nodePositions = buildNodePositionMap(layout.nodes);

        // Calculate edges based on layout positions
        const edges: Edge[] = [];
        for (const edge of layout.edges) {
            const sourcePos = nodePositions.get(edge.source);
            const targetPos = nodePositions.get(edge.target);

            if (sourcePos && targetPos) {
                edges.push({
                    ...edge,
                    sourceX: sourcePos.x + sourcePos.width / 2,
                    sourceY: sourcePos.y + sourcePos.height,
                    targetX: targetPos.x + targetPos.width / 2,
                    targetY: targetPos.y,
                });
            }
        }

        return edges;
    }, [layout.nodes, layout.edges]);

    // Auto-fit on initial load (once)
    useEffect(() => {
        if (!hasUserInteracted && layout.totalWidth > 0) {
            // Small delay to ensure DOM is ready
            const timer = setTimeout(() => {
                canvasRef.current?.fitToContent(layout.totalWidth, { animated: true });
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [layout.totalWidth, hasUserInteracted]);

    // Handle node click
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

    // Handle user interaction (prevents auto-fit)
    const handleUserInteraction = useCallback(() => {
        setHasUserInteracted(true);
    }, []);

    // Track mouse down position to distinguish click from drag
    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        mouseDownPos.current = { x: e.clientX, y: e.clientY };
        isDragging.current = false;
    }, []);

    // Track mouse movement to detect drag
    const handleMouseMove = useCallback((e: React.MouseEvent) => {
        if (mouseDownPos.current) {
            const dx = Math.abs(e.clientX - mouseDownPos.current.x);
            const dy = Math.abs(e.clientY - mouseDownPos.current.y);
            // Consider it a drag if mouse moved more than 5 pixels
            if (dx > 5 || dy > 5) {
                isDragging.current = true;
            }
        }
    }, []);

    // Handle click on background (deselect) - only if it was a simple single click, not a drag or double-click
    const handleBackgroundClick = useCallback(() => {
        const now = Date.now();
        const timeSinceLastClick = now - lastClickTime.current;
        const isDoubleClick = timeSinceLastClick < 300;
        lastClickTime.current = now;

        if (!isDragging.current && !isDoubleClick) {
            setSelectedNodeId(null);
            onNodeSelect?.(null);
        }
        mouseDownPos.current = null;
        isDragging.current = false;
    }, [onNodeSelect]);

    return (
        <div
            className="relative h-full w-full bg-card-background"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onClick={handleBackgroundClick}
        >
            <PanZoomCanvas
                ref={canvasRef}
                initialScale={1}
                minScale={0.25}
                maxScale={2}
                sidePanelWidth={sidePanelWidth}
                onUserInteraction={handleUserInteraction}
                onTransformChange={onTransformChange}
            >
                <div
                    ref={containerRef}
                    className="relative"
                    style={{
                        width: `${layout.totalWidth}px`,
                        height: `${layout.totalHeight}px`,
                    }}
                >
                    {/* Edge layer (behind nodes) - uses layout positions */}
                    <EdgeLayer edges={calculatedEdges} width={layout.totalWidth} height={layout.totalHeight} />

                    {/* Node layer */}
                    <WorkflowNodeRenderer
                        nodes={layout.nodes}
                        selectedNodeId={selectedNodeId || undefined}
                        highlightedNodeIds={highlightedNodeIds}
                        onNodeClick={handleNodeClick}
                        onExpand={handleExpand}
                        onCollapse={handleCollapse}
                        onHighlightNodes={handleHighlightNodes}
                        knownNodeIds={knownNodeIds}
                        nodeRefs={nodeRefs}
                        currentWorkflowName={currentWorkflowName}
                        parentPath={parentPath}
                    />
                </div>
            </PanZoomCanvas>
        </div>
    );
};

export default WorkflowDiagram;
