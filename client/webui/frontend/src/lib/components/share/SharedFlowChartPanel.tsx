/**
 * SharedFlowChartPanel - Standalone flow chart visualization for shared sessions
 * This is a simplified version of FlowChartPanel that doesn't depend on ChatContext or TaskContext
 */

import { useCallback, useMemo, useRef, useState, useEffect } from "react";
import { Scan } from "lucide-react";

import type { VisualizerStep } from "@/lib/types";
import { Button, Dialog, DialogContent, DialogFooter, VisuallyHidden, DialogTitle, DialogDescription, Tooltip, TooltipTrigger, TooltipContent, Switch } from "@/lib/components/ui";

import WorkflowRenderer from "../activities/FlowChart/WorkflowRenderer";
import type { LayoutNode, Edge } from "../activities/FlowChart/utils/types";
import PanZoomCanvas, { type PanZoomCanvasRef } from "../activities/FlowChart/PanZoomCanvas";
import { SharedVisualizerStepCard } from "./SharedVisualizerStepCard";

interface SharedFlowChartPanelProps {
    processedSteps: VisualizerStep[];
    agentNameDisplayNameMap?: Record<string, string>;
}

const EMPTY_MAP: Record<string, string> = {};

function SharedFlowChartPanel({ processedSteps, agentNameDisplayNameMap = EMPTY_MAP }: SharedFlowChartPanelProps) {
    // Dialog state
    const [selectedStep, setSelectedStep] = useState<VisualizerStep | null>(null);
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    // Show detail toggle - controls whether to show nested agent internals
    const [showDetail, setShowDetail] = useState(true);

    // Selected step for highlighting
    const [selectedStepId, setSelectedStepId] = useState<string | null>(null);

    // Pan/zoom canvas ref
    const canvasRef = useRef<PanZoomCanvasRef>(null);

    // Ref to measure actual rendered content dimensions
    const contentRef = useRef<HTMLDivElement>(null);

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

        // Initial measurement
        measureContent();

        // Watch for size changes
        const resizeObserver = new ResizeObserver(() => {
            measureContent();
        });
        resizeObserver.observe(element);

        return () => {
            resizeObserver.disconnect();
        };
    }, []);

    // Auto-fit when steps change
    useEffect(() => {
        if (processedSteps.length > 0) {
            setTimeout(() => {
                canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
            }, 150);
        }
    }, [processedSteps.length]);

    // Re-fit when showDetail changes
    useEffect(() => {
        setTimeout(() => {
            canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
        }, 150);
    }, [showDetail]);

    // Find step by visualizerStepId
    const findStepById = useCallback(
        (stepId: string): VisualizerStep | null => {
            return processedSteps.find(step => step.id === stepId) || null;
        },
        [processedSteps]
    );

    // Handle node click
    const handleNodeClick = useCallback(
        (node: LayoutNode) => {
            const stepId = node.data.visualizerStepId;

            // Set highlighted step for synchronization
            if (stepId) {
                setSelectedStepId(stepId);
                const step = findStepById(stepId);
                if (step) {
                    setSelectedStep(step);
                    setIsDialogOpen(true);
                }
            }
        },
        [findStepById]
    );

    // Handle edge click
    const handleEdgeClick = useCallback((edge: Edge) => {
        const stepId = edge.visualizerStepId;
        if (stepId) {
            setSelectedStepId(stepId);
        }
    }, []);

    // Handle dialog close
    const handleDialogClose = useCallback(() => {
        setIsDialogOpen(false);
        setSelectedStep(null);
    }, []);

    // Handle pane click (clear selection)
    const handlePaneClick = useCallback((event: React.MouseEvent) => {
        if (event.target === event.currentTarget) {
            setSelectedStepId(null);
        }
    }, []);

    // Handle re-center button click
    const handleRecenter = useCallback(() => {
        canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
    }, []);

    // Memoize the agent name map to prevent unnecessary re-renders
    const memoizedAgentNameMap = useMemo(() => agentNameDisplayNameMap, [agentNameDisplayNameMap]);

    return (
        <div style={{ height: "100%", width: "100%" }} className="bg-card-background relative">
            {/* Controls bar - Show Detail toggle and Re-center button */}
            <div className="bg-background absolute top-4 right-4 z-50 flex items-center gap-3 rounded-sm border px-4 py-2 shadow-md">
                {/* Re-center button */}
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

            <PanZoomCanvas ref={canvasRef} initialScale={1} minScale={0.1} maxScale={4} sidePanelWidth={0}>
                <div
                    style={{
                        minWidth: "100%",
                        minHeight: "100%",
                        padding: "40px",
                    }}
                    onClick={handlePaneClick}
                >
                    <div ref={contentRef} style={{ width: "fit-content" }}>
                        <WorkflowRenderer processedSteps={processedSteps} agentNameMap={memoizedAgentNameMap} selectedStepId={selectedStepId} onNodeClick={handleNodeClick} onEdgeClick={handleEdgeClick} showDetail={showDetail} />
                    </div>
                </div>
            </PanZoomCanvas>

            {/* Step Details Dialog - using SharedVisualizerStepCard which doesn't need context */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent className="flex max-h-[85vh] w-[90vw] !max-w-[800px] flex-col p-0 transition-all duration-200" onPointerDownOutside={e => e.preventDefault()} onInteractOutside={e => e.preventDefault()}>
                    <VisuallyHidden>
                        <DialogTitle>Step Details</DialogTitle>
                        <DialogDescription>Details for the selected workflow step</DialogDescription>
                    </VisuallyHidden>
                    {selectedStep && (
                        <div className="min-h-0 flex-1 overflow-auto p-4">
                            <SharedVisualizerStepCard step={selectedStep} variant="popover" />
                        </div>
                    )}
                    <DialogFooter className="mt-0 flex-shrink-0 border-t border-gray-200 p-4 dark:border-gray-700">
                        <Button variant="outline" onClick={handleDialogClose}>
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

export default SharedFlowChartPanel;
