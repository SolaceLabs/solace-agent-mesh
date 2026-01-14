import React, { useMemo, useState, useRef, useEffect, useCallback, useLayoutEffect } from "react";
import type { WorkflowConfig } from "@/lib/utils/agentUtils";
import PanZoomCanvas, { type PanZoomCanvasRef } from "@/lib/components/activities/FlowChart/PanZoomCanvas";
import { processWorkflowConfig } from "./utils/layoutEngine";
import type { LayoutNode, Edge } from "./utils/types";
import WorkflowNodeRenderer from "./WorkflowNodeRenderer";
import EdgeLayer from "./edges/EdgeLayer";

/** Measured node position and dimensions from DOM */
interface NodeMeasurement {
    x: number;
    y: number;
    width: number;
    height: number;
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
}) => {
    const internalCanvasRef = useRef<PanZoomCanvasRef>(null);
    const canvasRef = externalCanvasRef || internalCanvasRef;
    const containerRef = useRef<HTMLDivElement>(null);
    const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());
    const [hasUserInteracted, setHasUserInteracted] = useState(false);
    const [measuredEdges, setMeasuredEdges] = useState<Edge[]>([]);
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

    // Function to measure nodes and calculate edges
    const measureAndCalculateEdges = useCallback(() => {
        if (!containerRef.current) return;

        const containerRect = containerRef.current.getBoundingClientRect();

        // Measure all nodes
        const measurements = new Map<string, NodeMeasurement>();
        for (const [nodeId, element] of nodeRefs.current) {
            const rect = element.getBoundingClientRect();
            measurements.set(nodeId, {
                x: rect.left - containerRect.left,
                y: rect.top - containerRect.top,
                width: rect.width,
                height: rect.height,
            });
        }

        // Calculate edges based on measured positions
        const edges: Edge[] = [];
        for (const edge of layout.edges) {
            const sourceMeasurement = measurements.get(edge.source);
            const targetMeasurement = measurements.get(edge.target);

            if (sourceMeasurement && targetMeasurement) {
                edges.push({
                    ...edge,
                    sourceX: sourceMeasurement.x + sourceMeasurement.width / 2,
                    sourceY: sourceMeasurement.y + sourceMeasurement.height,
                    targetX: targetMeasurement.x + targetMeasurement.width / 2,
                    targetY: targetMeasurement.y,
                });
            }
        }

        setMeasuredEdges(edges);
    }, [layout.edges]);

    // Measure nodes and calculate edges after render
    useLayoutEffect(() => {
        if (!containerRef.current || layout.nodes.length === 0) {
            setMeasuredEdges([]);
            return;
        }

        // Measure at multiple points to catch various transition timings
        // This ensures edges stay aligned during expand/collapse animations
        const rafId = requestAnimationFrame(() => {
            measureAndCalculateEdges();
        });

        // Multiple measurement points to handle different transition durations
        const timeout100 = setTimeout(() => measureAndCalculateEdges(), 100);
        const timeout200 = setTimeout(() => measureAndCalculateEdges(), 200);
        const timeout350 = setTimeout(() => measureAndCalculateEdges(), 350);

        return () => {
            cancelAnimationFrame(rafId);
            clearTimeout(timeout100);
            clearTimeout(timeout200);
            clearTimeout(timeout350);
        };
    }, [layout, collapsedNodes, measureAndCalculateEdges]);

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

    // Handle click on background (deselect)
    const handleBackgroundClick = useCallback(() => {
        setSelectedNodeId(null);
        onNodeSelect?.(null);
    }, [onNodeSelect]);

    return (
        <div className="relative h-full w-full bg-gray-50 dark:bg-gray-900" onClick={handleBackgroundClick}>
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
                    {/* Edge layer (behind nodes) - uses measured positions */}
                    <EdgeLayer edges={measuredEdges} width={layout.totalWidth} height={layout.totalHeight} />

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
                    />
                </div>
            </PanZoomCanvas>
        </div>
    );
};

export default WorkflowDiagram;
