import React, { useMemo, useState, useRef, useEffect, useCallback } from "react";
import PanZoomCanvas, { type PanZoomCanvasRef } from "@/lib/components/activities/FlowChart/PanZoomCanvas";
import { processAgentConfig } from "./utils/layoutEngine";
import type { AgentDiagramConfig, AgentLayoutNode } from "./utils/types";
import type { Edge } from "../workflowVisualization/utils/types";
import AgentNodeRenderer from "./AgentNodeRenderer";
import EdgeLayer from "../workflowVisualization/edges/EdgeLayer";

interface AgentDiagramProps {
    config: AgentDiagramConfig;
    onNodeSelect?: (node: AgentLayoutNode | null) => void;
    /** Additional CSS class for the root container (e.g. to override background) */
    className?: string;
}

/**
 * AgentDiagram - Main agent visualization component with pan/zoom canvas.
 * Shows the agent at the top with skills and tools below.
 */
const AgentDiagram: React.FC<AgentDiagramProps> = ({ config, onNodeSelect, className }) => {
    const canvasRef = useRef<PanZoomCanvasRef>(null);
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
    const [hasUserInteracted, setHasUserInteracted] = useState(false);

    // Track mouse position to distinguish click from drag
    const mouseDownPos = useRef<{ x: number; y: number } | null>(null);
    const isDragging = useRef(false);
    const lastClickTime = useRef(0);

    // Calculate layout whenever config changes
    const layout = useMemo(() => {
        return processAgentConfig(config);
    }, [config]);

    // Calculate edges from layout positions
    const calculatedEdges = useMemo(() => {
        if (layout.nodes.length === 0) return [];

        const arrowheadOffset = 4;
        const edges: Edge[] = [];

        for (const edge of layout.edges) {
            const sourceNode = layout.nodes.find(n => n.id === edge.source);
            const targetNode = layout.nodes.find(n => n.id === edge.target);

            if (sourceNode && targetNode) {
                edges.push({
                    ...edge,
                    sourceX: sourceNode.x + sourceNode.width / 2,
                    sourceY: sourceNode.y + sourceNode.height,
                    targetX: targetNode.x + targetNode.width / 2,
                    targetY: targetNode.y - arrowheadOffset,
                });
            }
        }

        return edges;
    }, [layout.nodes, layout.edges]);

    // Auto-fit on initial load (once)
    useEffect(() => {
        if (!hasUserInteracted && layout.totalWidth > 0) {
            const timer = setTimeout(() => {
                canvasRef.current?.fitToContent(layout.totalWidth, { animated: true });
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [layout.totalWidth, hasUserInteracted]);

    // Handle node click
    const handleNodeClick = useCallback(
        (node: AgentLayoutNode) => {
            setSelectedNodeId(node.id);
            onNodeSelect?.(node);
        },
        [onNodeSelect]
    );

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
            if (dx > 5 || dy > 5) {
                isDragging.current = true;
            }
        }
    }, []);

    // Handle click on background (deselect)
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
        <div className={`${className ?? "bg-card-background"} relative h-full w-full`} onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onClick={handleBackgroundClick}>
            <PanZoomCanvas ref={canvasRef} initialScale={1} minScale={0.25} maxScale={2} onUserInteraction={handleUserInteraction}>
                <div
                    role="region"
                    aria-label="Agent visualization"
                    className="relative"
                    style={{
                        width: `${layout.totalWidth}px`,
                        height: `${layout.totalHeight}px`,
                    }}
                >
                    {/* Edge layer (behind nodes) */}
                    <EdgeLayer edges={calculatedEdges} width={layout.totalWidth} height={layout.totalHeight} />

                    {/* Node layer */}
                    <AgentNodeRenderer nodes={layout.nodes} selectedNodeId={selectedNodeId || undefined} onNodeClick={handleNodeClick} />
                </div>
            </PanZoomCanvas>
        </div>
    );
};

export default AgentDiagram;
