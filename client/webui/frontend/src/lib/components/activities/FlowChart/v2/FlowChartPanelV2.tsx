import React, { useCallback, useRef, useState } from "react";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import type { VisualizerStep } from "@/lib/types";
import { PopoverManual } from "@/lib/components/ui";
import { useTaskContext } from "@/lib/hooks";
import { useAgentCards } from "@/lib/hooks";
import { getThemeButtonHtmlStyles } from "@/lib/utils";
import WorkflowRendererV2 from "./WorkflowRendererV2";
import type { LayoutNode, Edge } from "./utils/types";
import { VisualizerStepCard } from "../../VisualizerStepCard";

interface FlowChartPanelV2Props {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

// Stable offset object to prevent unnecessary re-renders
const POPOVER_OFFSET = { x: 16, y: 0 };

const FlowChartPanelV2: React.FC<FlowChartPanelV2Props> = ({
    processedSteps,
    isRightPanelVisible = false
}) => {
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { agentNameMap } = useAgentCards();

    // Popover state
    const [selectedStep, setSelectedStep] = useState<VisualizerStep | null>(null);
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);
    const popoverAnchorRef = useRef<HTMLDivElement>(null);

    // Show detail toggle - controls whether to show nested agent internals
    const [showDetail, setShowDetail] = useState(true);

    // Handle node click
    const handleNodeClick = useCallback(
        (node: LayoutNode) => {
            const stepId = node.data.visualizerStepId;
            if (!stepId) return;

            const step = processedSteps.find(s => s.id === stepId);
            if (!step) return;

            setHighlightedStepId(stepId);

            if (isRightPanelVisible) {
                // Right panel is open, just highlight
            } else {
                // Show popover
                setSelectedStep(step);
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

            const step = processedSteps.find(s => s.id === stepId);
            if (!step) return;

            setHighlightedStepId(stepId);

            if (isRightPanelVisible) {
                // Right panel is open, just highlight
            } else {
                // Show popover
                setSelectedStep(step);
                setIsPopoverOpen(true);
            }
        },
        [processedSteps, isRightPanelVisible, setHighlightedStepId]
    );

    // Handle popover close
    const handlePopoverClose = useCallback(() => {
        setIsPopoverOpen(false);
        setSelectedStep(null);
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
                {({ zoomIn, zoomOut, resetTransform }) => (
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
                                <WorkflowRendererV2
                                    processedSteps={processedSteps}
                                    agentNameMap={agentNameMap}
                                    selectedStepId={highlightedStepId}
                                    onNodeClick={handleNodeClick}
                                    onEdgeClick={handleEdgeClick}
                                    showDetail={showDetail}
                                />
                            </div>
                        </TransformComponent>

                        {/* Popover anchor point */}
                        <div ref={popoverAnchorRef} style={{ position: "absolute", top: "50%", right: "50px" }} />
                    </>
                )}
            </TransformWrapper>

            {/* Edge/Node Information Popover */}
            <PopoverManual
                isOpen={isPopoverOpen}
                onClose={handlePopoverClose}
                anchorRef={popoverAnchorRef}
                offset={POPOVER_OFFSET}
                placement="right-start"
                className="max-w-[500px] min-w-[400px] p-2"
            >
                {selectedStep && <VisualizerStepCard step={selectedStep} variant="popover" />}
            </PopoverManual>
        </div>
    );
};

export default FlowChartPanelV2;
