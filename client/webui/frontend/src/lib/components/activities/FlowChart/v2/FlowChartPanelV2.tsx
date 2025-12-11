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
                        <div className="absolute top-4 right-4 z-50 flex flex-col gap-2">
                            <button
                                onClick={() => zoomIn()}
                                className={`${getThemeButtonHtmlStyles()} px-3 py-2 rounded-md`}
                                title="Zoom In"
                            >
                                +
                            </button>
                            <button
                                onClick={() => zoomOut()}
                                className={`${getThemeButtonHtmlStyles()} px-3 py-2 rounded-md`}
                                title="Zoom Out"
                            >
                                −
                            </button>
                            <button
                                onClick={() => resetTransform()}
                                className={`${getThemeButtonHtmlStyles()} px-3 py-2 rounded-md text-xs`}
                                title="Reset View"
                            >
                                Reset
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
                                className="bg-gray-50 dark:bg-gray-900"
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
