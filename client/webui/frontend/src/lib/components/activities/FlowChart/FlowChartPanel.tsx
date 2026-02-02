import { useCallback, useState, useRef, useEffect } from "react";
import { Home } from "lucide-react";
import type { VisualizerStep } from "@/lib/types";
import { Dialog, DialogContent, DialogFooter, VisuallyHidden, DialogTitle, DialogDescription, Button, Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import { useTaskContext } from "@/lib/hooks";
import { useAgentCards } from "@/lib/hooks";
import WorkflowRenderer from "./WorkflowRenderer";
import type { LayoutNode, Edge } from "./utils/types";
import { findNodeDetails, type NodeDetails } from "./utils/nodeDetailsHelper";
import NodeDetailsCard from "./NodeDetailsCard";
import PanZoomCanvas, { type PanZoomCanvasRef } from "./PanZoomCanvas";

// Approximate width of the right side panel when visible
const RIGHT_PANEL_WIDTH = 400;

interface FlowChartPanelProps {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

const FlowChartPanel = ({ processedSteps, isRightPanelVisible = false }: FlowChartPanelProps) => {
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { agentNameMap } = useAgentCards();

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
    // Using a ref so effects don't re-run when it changes
    const contentWidthRef = useRef(800);

    // Use ResizeObserver to automatically detect content size changes
    // This handles node expansions, collapses, and any other layout changes
    useEffect(() => {
        const element = contentRef.current;
        if (!element) return;

        const measureContent = () => {
            if (contentRef.current && canvasRef.current) {
                const rect = contentRef.current.getBoundingClientRect();
                // getBoundingClientRect returns scaled dimensions, so divide by current scale
                // to get the "natural" width at scale 1.0
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

    // Calculate side panel width for auto-fit calculations
    const sidePanelWidth = isRightPanelVisible ? RIGHT_PANEL_WIDTH : 0;

    // Reset interaction flag when a new task starts (step count goes back to near zero)
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
            // New steps added and user hasn't interacted - fit to content with animation
            setTimeout(() => {
                canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
            }, 150); // Longer delay to let content measurement update
        }
        prevStepCount.current = currentCount;
    }, [processedSteps.length]);

    // Re-fit when showDetail changes - only if user hasn't manually adjusted the view
    useEffect(() => {
        if (!hasUserInteracted.current) {
            setTimeout(() => {
                canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true, maxFitScale: 2.5 });
            }, 150); // Longer delay to let content measurement update
        }
    }, [showDetail]);

    // Re-fit when side panel visibility changes (if user hasn't interacted)
    useEffect(() => {
        if (!hasUserInteracted.current) {
            setTimeout(() => {
                canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true });
            }, 150);
        }
    }, [isRightPanelVisible]);

    // Handler to mark user interaction
    const handleUserInteraction = useCallback(() => {
        hasUserInteracted.current = true;
    }, []);

    // Handle node click
    const handleNodeClick = useCallback(
        (node: LayoutNode) => {
            // Mark user interaction to stop auto-fit
            hasUserInteracted.current = true;

            const stepId = node.data.visualizerStepId;

            // Find detailed information about this node
            const nodeDetails = findNodeDetails(node, processedSteps);

            // Set highlighted step for synchronization with other views
            if (stepId) {
                setHighlightedStepId(stepId);
            }

            if (isRightPanelVisible) {
                // Right panel is open, just highlight
            } else {
                // Show dialog with node details
                setSelectedNodeDetails(nodeDetails);
                setIsDialogOpen(true);
            }
        },
        [processedSteps, isRightPanelVisible, setHighlightedStepId]
    );

    // Handle edge click
    const handleEdgeClick = useCallback(
        (edge: Edge) => {
            const stepId = edge.visualizerStepId;
            if (!stepId) return;

            // For edges, just highlight the step
            setHighlightedStepId(stepId);

            // Note: Edges don't have request/result pairs like nodes do,
            // so we don't show a popover for them
        },
        [setHighlightedStepId]
    );

    // Handle dialog close
    const handleDialogClose = useCallback(() => {
        setIsDialogOpen(false);
        setSelectedNodeDetails(null);
        setIsDialogExpanded(false);
    }, []);

    // Handle pane click (clear selection)
    const handlePaneClick = useCallback(
        (event: React.MouseEvent) => {
            // Only clear if clicking on the wrapper itself, not on nodes
            if (event.target === event.currentTarget) {
                setHighlightedStepId(null);
            }
        },
        [setHighlightedStepId]
    );

    // Handle re-center button click - allow zooming in up to 2.5x
    const handleRecenter = useCallback(() => {
        canvasRef.current?.fitToContent(contentWidthRef.current, { animated: true, maxFitScale: 2.5 });
        hasUserInteracted.current = false;
    }, []);

    return (
        <div style={{ height: "100%", width: "100%" }} className="relative">
            {/* Controls bar - Show Detail toggle and Re-center button */}
            <div className="absolute top-4 right-4 z-50 flex items-center gap-3 rounded-md border border-gray-200 bg-white px-4 py-2 shadow-md dark:border-gray-700 dark:bg-gray-800">
                {/* Re-center button (D-6) */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <button onClick={handleRecenter} className="rounded p-1 transition-colors hover:bg-gray-100 dark:hover:bg-gray-700">
                            <Home className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                        </button>
                    </TooltipTrigger>
                    <TooltipContent>Re-center diagram</TooltipContent>
                </Tooltip>

                <div className="h-6 w-px bg-gray-200 dark:bg-gray-600" />

                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Show Detail</span>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <button onClick={() => setShowDetail(!showDetail)} className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${showDetail ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"}`}>
                            <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${showDetail ? "translate-x-6" : "translate-x-1"}`} />
                        </button>
                    </TooltipTrigger>
                    <TooltipContent>{showDetail ? "Hide nested agent details" : "Show nested agent details"}</TooltipContent>
                </Tooltip>
            </div>

            <PanZoomCanvas ref={canvasRef} initialScale={1} minScale={0.1} maxScale={4} onUserInteraction={handleUserInteraction} sidePanelWidth={sidePanelWidth}>
                <div
                    style={{
                        minWidth: "100%",
                        minHeight: "100%",
                        padding: "40px",
                    }}
                    onClick={handlePaneClick}
                >
                    <div ref={contentRef} style={{ width: "fit-content" }}>
                        <WorkflowRenderer processedSteps={processedSteps} agentNameMap={agentNameMap} selectedStepId={highlightedStepId} onNodeClick={handleNodeClick} onEdgeClick={handleEdgeClick} showDetail={showDetail} />
                    </div>
                </div>
            </PanZoomCanvas>

            {/* Node Details Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent
                    className={`w-[90vw] ${isDialogExpanded ? "!max-w-[1600px]" : "!max-w-[1200px]"} flex max-h-[85vh] flex-col p-0 transition-all duration-200`}
                    onPointerDownOutside={e => e.preventDefault()}
                    onInteractOutside={e => e.preventDefault()}
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
                    <DialogFooter className="mt-0 flex-shrink-0 border-t border-gray-200 p-4 dark:border-gray-700">
                        <Button variant="outline" onClick={handleDialogClose}>
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default FlowChartPanel;
