import React, { useCallback, useRef, useState } from "react";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import type { VisualizerStep } from "@/lib/types";
import { PopoverManual } from "@/lib/components/ui";
import { useTaskContext } from "@/lib/hooks";
import { useAgentCards } from "@/lib/hooks";
// import { getThemeButtonHtmlStyles } from "@/lib/utils";
import WorkflowRenderer from "./WorkflowRenderer";
import type { LayoutNode, Edge } from "./utils/types";
import { findNodeDetails, type NodeDetails } from "./utils/nodeDetailsHelper";
import NodeDetailsCard from "./NodeDetailsCard";

interface FlowChartPanelProps {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

// Stable offset object to prevent unnecessary re-renders
const POPOVER_OFFSET = { x: 16, y: 0 };

const FlowChartPanel: React.FC<FlowChartPanelProps> = ({
    processedSteps,
    isRightPanelVisible = false
}) => {
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { agentNameMap } = useAgentCards();

    // Popover state
    const [selectedNodeDetails, setSelectedNodeDetails] = useState<NodeDetails | null>(null);
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);
    const popoverAnchorRef = useRef<HTMLDivElement>(null);

    // Show detail toggle - controls whether to show nested agent internals
    const [showDetail, setShowDetail] = useState(true);

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
                // Show popover with node details
                setSelectedNodeDetails(nodeDetails);
                setIsPopoverOpen(true);
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

    // Handle popover close
    const handlePopoverClose = useCallback(() => {
        setIsPopoverOpen(false);
        setSelectedNodeDetails(null);
    }, []);

    // Handle pane click (clear selection)
    const handlePaneClick = useCallback(
        (event: React.MouseEvent) => {
            // Only clear if clicking on the wrapper itself, not on nodes
            if (event.target === event.currentTarget) {
                setHighlightedStepId(null);
                handlePopoverClose();
            }
        },
        [setHighlightedStepId, handlePopoverClose]
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
                wheel={{ step: 0.1 }}
            >
                {({ zoomIn: _zoomIn, zoomOut: _zoomOut, resetTransform: _resetTransform }) => (
                    <>
                        {/* Show Detail Toggle Switch */}
                        <div className="absolute top-4 right-4 z-50 flex items-center gap-3 bg-white dark:bg-gray-800 px-4 py-2 rounded-md shadow-md border border-gray-200 dark:border-gray-700">
                            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                                Show Detail
                            </span>
                            <button
                                onClick={() => setShowDetail(!showDetail)}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                    showDetail ? "bg-blue-600" : "bg-gray-300 dark:bg-gray-600"
                                }`}
                                title={showDetail ? "Hide nested agent details" : "Show nested agent details"}
                            >
                                <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                        showDetail ? "translate-x-6" : "translate-x-1"
                                    }`}
                                />
                            </button>
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

                        {/* Popover anchor point - positioned near top to allow room for content to expand */}
                        <div ref={popoverAnchorRef} style={{ position: "absolute", top: "80px", right: "50px" }} />
                    </>
                )}
            </TransformWrapper>

            {/* Node Details Popover */}
            <PopoverManual
                isOpen={isPopoverOpen}
                onClose={handlePopoverClose}
                anchorRef={popoverAnchorRef}
                offset={POPOVER_OFFSET}
                placement="right-start"
                className="max-w-[900px] min-w-[600px] max-h-[80vh] overflow-y-auto"
            >
                {selectedNodeDetails && <NodeDetailsCard nodeDetails={selectedNodeDetails} onClose={handlePopoverClose} />}
            </PopoverManual>
        </div>
    );
};

export default FlowChartPanel;
