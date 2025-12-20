import React, { useCallback, useState, useRef, useEffect } from "react";
import { TransformWrapper, TransformComponent, useControls } from "react-zoom-pan-pinch";
import { Home } from "lucide-react";
import type { VisualizerStep } from "@/lib/types";
import { Dialog, DialogContent, DialogFooter, VisuallyHidden, DialogTitle, DialogDescription, Button, Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui";
import { useTaskContext } from "@/lib/hooks";
import { useAgentCards } from "@/lib/hooks";
// import { getThemeButtonHtmlStyles } from "@/lib/utils";
import WorkflowRenderer from "./WorkflowRenderer";
import type { LayoutNode, Edge } from "./utils/types";
import { findNodeDetails, type NodeDetails } from "./utils/nodeDetailsHelper";
import NodeDetailsCard from "./NodeDetailsCard";

// Inner component that has access to transform controls via hook
interface TransformControlsProps {
    processedSteps: VisualizerStep[];
    showDetail: boolean;
    hasUserInteracted: React.MutableRefObject<boolean>;
    prevStepCount: React.MutableRefObject<number>;
}

const TransformControls: React.FC<TransformControlsProps> = ({
    processedSteps,
    showDetail,
    hasUserInteracted,
    prevStepCount,
}) => {
    const { resetTransform } = useControls();

    // Auto-fit when new steps are added (D-2) - only if user hasn't interacted
    useEffect(() => {
        const currentCount = processedSteps.length;
        if (currentCount > prevStepCount.current && !hasUserInteracted.current) {
            // New steps added and user hasn't interacted - reset to center
            setTimeout(() => resetTransform(), 50);
        }
        prevStepCount.current = currentCount;
    }, [processedSteps.length, resetTransform, hasUserInteracted, prevStepCount]);

    // Re-center when showDetail changes (D-3)
    useEffect(() => {
        setTimeout(() => resetTransform(), 50);
    }, [showDetail, resetTransform]);

    return null;
};

interface FlowChartPanelProps {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

const FlowChartPanel: React.FC<FlowChartPanelProps> = ({
    processedSteps,
    isRightPanelVisible = false
}) => {
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { agentNameMap } = useAgentCards();

    // Dialog state
    const [selectedNodeDetails, setSelectedNodeDetails] = useState<NodeDetails | null>(null);
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [isDialogExpanded, setIsDialogExpanded] = useState(false);

    // Show detail toggle - controls whether to show nested agent internals
    const [showDetail, setShowDetail] = useState(true);

    // Track if user has manually interacted with pan/zoom (D-2)
    const hasUserInteracted = useRef(false);
    const prevStepCount = useRef(processedSteps.length);

    // Reset interaction flag when a new task starts (step count goes back to near zero)
    useEffect(() => {
        if (processedSteps.length <= 1) {
            hasUserInteracted.current = false;
            prevStepCount.current = 0;
        }
    }, [processedSteps.length]);

    // Handler to mark user interaction
    const handleUserInteraction = useCallback(() => {
        hasUserInteracted.current = true;
    }, []);

    // Handle node click
    const handleNodeClick = useCallback(
        (node: LayoutNode) => {
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

    // Handle dialog width change from NodeDetailsCard (NP-3)
    const handleDialogWidthChange = useCallback((isExpanded: boolean) => {
        setIsDialogExpanded(isExpanded);
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

    return (
        <div style={{ height: "100%", width: "100%" }} className="relative">
            <TransformWrapper
                initialScale={1}
                minScale={0.2}
                maxScale={2}
                centerOnInit
                limitToBounds={false}
                panning={{ disabled: false }}
                wheel={{ step: 0.2 }}
                doubleClick={{ disabled: true }}
                onPanning={handleUserInteraction}
                onZoom={handleUserInteraction}
            >
                {({ resetTransform }) => (
                    <>
                        {/* TransformControls - handles auto-fit and re-center effects */}
                        <TransformControls
                            processedSteps={processedSteps}
                            showDetail={showDetail}
                            hasUserInteracted={hasUserInteracted}
                            prevStepCount={prevStepCount}
                        />

                        {/* Controls bar - Show Detail toggle and Re-center button */}
                        <div className="absolute top-4 right-4 z-50 flex items-center gap-3 bg-white dark:bg-gray-800 px-4 py-2 rounded-md shadow-md border border-gray-200 dark:border-gray-700">
                            {/* Re-center button (D-6) */}
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        onClick={() => {
                                            resetTransform();
                                            hasUserInteracted.current = false;
                                        }}
                                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                                    >
                                        <Home className="h-4 w-4 text-gray-600 dark:text-gray-400" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent>Re-center diagram</TooltipContent>
                            </Tooltip>

                            <div className="w-px h-6 bg-gray-200 dark:bg-gray-600" />

                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                Show Detail
                            </span>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <button
                                        onClick={() => setShowDetail(!showDetail)}
                                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                            showDetail ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"
                                        }`}
                                    >
                                        <span
                                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                                showDetail ? "translate-x-6" : "translate-x-1"
                                            }`}
                                        />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent>{showDetail ? "Hide nested agent details" : "Show nested agent details"}</TooltipContent>
                            </Tooltip>
                        </div>

                        <TransformComponent
                            wrapperStyle={{
                                width: "100%",
                                height: "100%",
                            }}
                            contentStyle={{
                                width: "100%",
                                height: "100%",
                            }}
                        >
                            <div
                                style={{
                                    minWidth: "100%",
                                    minHeight: "100%",
                                    cursor: "grab",
                                }}
                                onClick={handlePaneClick}
                            >
                                <WorkflowRenderer
                                    processedSteps={processedSteps}
                                    agentNameMap={agentNameMap}
                                    selectedStepId={highlightedStepId}
                                    onNodeClick={handleNodeClick}
                                    onEdgeClick={handleEdgeClick}
                                    showDetail={showDetail}
                                />
                            </div>
                        </TransformComponent>

                    </>
                )}
            </TransformWrapper>

            {/* Node Details Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent
                    className={`w-[90vw] ${isDialogExpanded ? '!max-w-[1600px]' : '!max-w-[1200px]'} max-h-[85vh] p-0 transition-all duration-200 flex flex-col`}
                    onPointerDownOutside={(e) => e.preventDefault()}
                    onInteractOutside={(e) => e.preventDefault()}
                >
                    <VisuallyHidden>
                        <DialogTitle>Node Details</DialogTitle>
                        <DialogDescription>Details for the selected node</DialogDescription>
                    </VisuallyHidden>
                    {selectedNodeDetails && (
                        <div className="flex-1 min-h-0 overflow-hidden">
                            <NodeDetailsCard
                                nodeDetails={selectedNodeDetails}
                                onClose={handleDialogClose}
                                onWidthChange={handleDialogWidthChange}
                            />
                        </div>
                    )}
                    <DialogFooter className="border-t border-gray-200 dark:border-gray-700 p-4 mt-0 flex-shrink-0">
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
