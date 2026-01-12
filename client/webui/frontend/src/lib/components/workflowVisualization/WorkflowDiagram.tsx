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
}) => {
    const canvasRef = useRef<PanZoomCanvasRef>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [collapsedNodes, setCollapsedNodes] = useState<Set<string>>(new Set());
    const [hasUserInteracted, setHasUserInteracted] = useState(false);
    const [measuredEdges, setMeasuredEdges] = useState<Edge[]>([]);

    // Calculate layout whenever config or collapsed state changes
    const layout = useMemo(() => {
        return processWorkflowConfig(config, collapsedNodes, knownWorkflows);
    }, [config, collapsedNodes, knownWorkflows]);

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

        // Initial measurement on next frame
        const rafId = requestAnimationFrame(() => {
            measureAndCalculateEdges();
        });

        // Also measure after CSS transitions complete (200ms + buffer)
        // This handles container expand/collapse animations
        const timeoutId = setTimeout(() => {
            measureAndCalculateEdges();
        }, 250);

        return () => {
            cancelAnimationFrame(rafId);
            clearTimeout(timeoutId);
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
                        onNodeClick={handleNodeClick}
                        onExpand={handleExpand}
                        onCollapse={handleCollapse}
                        nodeRefs={nodeRefs}
                    />
                </div>
            </PanZoomCanvas>
        </div>
    );
};

export default WorkflowDiagram;
