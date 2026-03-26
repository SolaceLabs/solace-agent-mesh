/**
 * SharedFlowChartPanel - Standalone flow chart visualization for shared sessions
 * This is a simplified version of FlowChartPanel that doesn't depend on ChatContext or TaskContext
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Scan } from "lucide-react";

import type { VisualizerStep } from "@/lib/types";
import { Button, Dialog, DialogContent, VisuallyHidden, DialogTitle, DialogDescription, Tooltip, TooltipTrigger, TooltipContent, Switch } from "@/lib/components/ui";
import WorkflowRenderer from "../activities/FlowChart/WorkflowRenderer";
import type { LayoutNode, Edge } from "../activities/FlowChart/utils/types";
import { findNodeDetails, type NodeDetails } from "../activities/FlowChart/utils/nodeDetailsHelper";
import NodeDetailsCard from "../activities/FlowChart/NodeDetailsCard";
import PanZoomCanvas, { type PanZoomCanvasRef } from "../activities/FlowChart/PanZoomCanvas";

interface SharedFlowChartPanelProps {
    processedSteps: VisualizerStep[];
    agentNameDisplayNameMap?: Record<string, string>;
}

const EMPTY_MAP: Record<string, string> = {};

const SharedFlowChartPanel: React.FC<SharedFlowChartPanelProps> = ({ processedSteps, agentNameDisplayNameMap = EMPTY_MAP }) => {
    // Local highlighted step state (instead of using TaskContext)
    const [highlightedStepId, setHighlightedStepId] = useState<string | null>(null);

    // Dialog state
    const [selectedNodeDetails, setSelectedNodeDetails] = useState<NodeDetails | null>(null);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [isDialogExpanded, setIsDialogExpanded] = useState(false);

    // Show detail toggle - controls whether to show nested agent internals
    const [showDetail, setShowDetail] = useState(true);

    // Pan/zoom canvas ref
    const canvasRef = useRef<PanZoomCanvasRef>(null);

    // Ref to measure actual rendered content dimensions
    const contentRef = useRef<HTMLDivElement>(null);

    // Track if user has manually interacted with pan/zoom
    const hasUserInteracted = useRef(false);
    const prevStepCount = useRef(processedSteps.length);

    // Track content dimensions (measured from actual DOM, adjusted for current scale)
    const contentWidthRef = useRef(800);

    // Use ResizeObserver to automatically detect content size changes
    useEffect(() => {
        const element = contentRef.current;
        if (!element) return;

        const measureContent = () => {
            if (contentRef.current && canvasRef.current) {
                const rect = contentRef.current.getBoundingClientRect();
                const currentScale = canvasRef.current.getTransform().scale;
                const naturalWidth = rect.width / currentScale;
                contentWidthRef.current = naturalWidth;
            }
        };

        measureContent();

        const resizeObserver = new ResizeObserver(() => {
            measureContent();
        });
        resizeObserver.observe(element);

        return () => {
            resizeObserver.disconnect();
        };
    }, []);

    // Reset interaction flag when a new task starts
    useEffect(() => {
        if (processedSteps.length <= 1) {
            hasUserInteracted.current = false;
            prevStepCount.current = 0;
        }
    }, [processedSteps.length]);

    // Auto-fit when new steps are added - only if user hasn't interacted
    useEffect(() => {
        const currentCount = processedSteps.length;
        if (currentCount > prevStepCount.current && !hasUserInteracted.current) {
            setTimeout(() => {
                canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
            }, 150);
        }
        prevStepCount.current = currentCount;
    }, [processedSteps.length]);

    // Re-fit when showDetail changes
    useEffect(() => {
        if (!hasUserInteracted.current) {
            setTimeout(() => {
                canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
            }, 150);
        }
    }, [showDetail]);

    // Handler to mark user interaction
    const handleUserInteraction = useCallback(() => {
        hasUserInteracted.current = true;
    }, []);

    // Handle node click
    const handleNodeClick = useCallback(
        (node: LayoutNode) => {
            hasUserInteracted.current = true;

            const stepId = node.data.visualizerStepId;
            const nodeDetails = findNodeDetails(node, processedSteps);

            if (stepId) {
                setHighlightedStepId(stepId);
            }

            // Show dialog with node details
            setSelectedNodeDetails(nodeDetails);
            setIsDialogOpen(true);
        },
        [processedSteps]
    );

    // Handle edge click
    const handleEdgeClick = useCallback((edge: Edge) => {
        const stepId = edge.visualizerStepId;
        if (!stepId) return;
        setHighlightedStepId(stepId);
    }, []);

    // Handle dialog close
    const handleDialogClose = useCallback(() => {
        setIsDialogOpen(false);
        setSelectedNodeDetails(null);
        setIsDialogExpanded(false);
    }, []);

    // Handle pane click (clear selection)
    const handlePaneClick = useCallback((event: React.MouseEvent) => {
        if (event.target === event.currentTarget) {
            setHighlightedStepId(null);
        }
    }, []);

    // Handle re-center button click
    const handleRecenter = useCallback(() => {
        canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
        hasUserInteracted.current = false;
    }, []);

    if (!processedSteps || processedSteps.length === 0) {
        return <div className="flex h-full items-center justify-center text-(--secondary-text-wMain)">No steps to display in flow chart.</div>;
    }

    return (
        <div style={{ height: "100%", width: "100%" }} className="relative bg-(--background-w20)">
            {/* Controls bar */}
            <div className="absolute top-4 right-4 z-50 flex items-center gap-3 rounded-sm border bg-(--background-w10) px-4 py-2 shadow-md">
                <Button onClick={handleRecenter} variant="ghost" size="sm" tooltip="Center Workflow">
                    <Scan className="h-4 w-4" />
                </Button>
                <div className="h-6 w-px border-l" />
                <span className="text-sm font-medium">Detail Mode</span>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Switch checked={showDetail} onCheckedChange={() => setShowDetail(!showDetail)} />
                    </TooltipTrigger>
                    <TooltipContent>{showDetail ? "Hide nested agent details" : "Show nested agent details"}</TooltipContent>
                </Tooltip>
            </div>

            <PanZoomCanvas ref={canvasRef} initialScale={1} minScale={0.1} maxScale={4} onUserInteraction={handleUserInteraction}>
                <div
                    style={{
                        minWidth: "100%",
                        minHeight: "100%",
                        padding: "40px",
                    }}
                    onClick={handlePaneClick}
                    role="presentation"
                >
                    <div ref={contentRef} style={{ width: "fit-content" }}>
                        <WorkflowRenderer processedSteps={processedSteps} agentNameMap={agentNameDisplayNameMap} selectedStepId={highlightedStepId} onNodeClick={handleNodeClick} onEdgeClick={handleEdgeClick} showDetail={showDetail} />
                    </div>
                </div>
            </PanZoomCanvas>

            {/* Node Details Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent
                    className={`w-[90vw] ${isDialogExpanded ? "!max-w-[1600px]" : "!max-w-[1200px]"} flex max-h-[85vh] flex-col p-0 transition-all duration-200`}
                    onPointerDownOutside={e => e.preventDefault()}
                    onInteractOutside={e => e.preventDefault()}
                    showCloseButton
                >
                    <VisuallyHidden>
                        <DialogTitle>Node Details</DialogTitle>
                        <DialogDescription>Details for the selected node</DialogDescription>
                    </VisuallyHidden>
                    {selectedNodeDetails && (
                        <div className="min-h-0 flex-1 overflow-hidden">
                            <NodeDetailsCard nodeDetails={selectedNodeDetails} onClose={handleDialogClose} />
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
};

export { SharedFlowChartPanel };
