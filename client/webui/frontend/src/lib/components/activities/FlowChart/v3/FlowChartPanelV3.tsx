import React, { useCallback, useMemo, useRef, useState } from "react";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";
import type { VisualizerStep } from "@/lib/types";
import { PopoverManual } from "@/lib/components/ui";
import { useTaskContext } from "@/lib/hooks";
import { useAgentCards } from "@/lib/hooks";
import { getThemeButtonHtmlStyles } from "@/lib/utils";
import { processStepsToSubway } from "./utils/subwayEngine";
import type { SubwayStop, TrackSegment } from "./utils/types";
import SubwayStopComponent from "./components/SubwayStop";
import SubwayTracks from "./components/SubwayTracks";
import { VisualizerStepCard } from "../../VisualizerStepCard";

interface FlowChartPanelV3Props {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

const POPOVER_OFFSET = { x: 16, y: 0 };
const LANE_WIDTH = 40;
const LEFT_MARGIN = 50;

const FlowChartPanelV3: React.FC<FlowChartPanelV3Props> = ({
    processedSteps,
    isRightPanelVisible = false,
}) => {
    const { highlightedStepId, setHighlightedStepId } = useTaskContext();
    const { agentNameMap } = useAgentCards();

    const [selectedStep, setSelectedStep] = useState<VisualizerStep | null>(null);
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);
    const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
    const popoverAnchorRef = useRef<HTMLDivElement>(null);

    // Process steps into subway graph
    const subwayGraph = useMemo(() => {
        if (!processedSteps || processedSteps.length === 0) {
            return { stops: [], tracks: [], branches: [], totalLanes: 1, totalHeight: 600 };
        }

        try {
            return processStepsToSubway(processedSteps, agentNameMap);
        } catch (error) {
            console.error("[FlowChartPanelV3] Error processing steps:", error);
            return { stops: [], tracks: [], branches: [], totalLanes: 1, totalHeight: 600 };
        }
    }, [processedSteps, agentNameMap]);

    // Calculate lane X positions
    const laneXPositions = useMemo(() => {
        const positions: number[] = [];
        for (let i = 0; i < subwayGraph.totalLanes; i++) {
            positions.push(LEFT_MARGIN + i * LANE_WIDTH);
        }
        return positions;
    }, [subwayGraph.totalLanes]);

    // Calculate total width
    const totalWidth = useMemo(() => {
        const laneAreaWidth = subwayGraph.totalLanes * LANE_WIDTH + LEFT_MARGIN;
        const labelAreaWidth = 300;
        return laneAreaWidth + labelAreaWidth + 100; // Add margin
    }, [subwayGraph.totalLanes]);

    // Handle stop click
    const handleStopClick = useCallback(
        (stop: SubwayStop) => {
            const stepId = stop.visualizerStepId;
            if (!stepId) return;

            const step = processedSteps.find(s => s.id === stepId);
            if (!step) return;

            setHighlightedStepId(stepId);

            if (!isRightPanelVisible) {
                setSelectedStep(step);
                setIsPopoverOpen(true);
            }
        },
        [processedSteps, isRightPanelVisible, setHighlightedStepId]
    );

    // Handle track click
    const handleTrackClick = useCallback(
        (track: TrackSegment) => {
            const stepId = track.visualizerStepId;
            if (!stepId) return;

            const step = processedSteps.find(s => s.id === stepId);
            if (!step) return;

            setHighlightedStepId(stepId);
            setSelectedTrackId(track.id);

            if (!isRightPanelVisible) {
                setSelectedStep(step);
                setIsPopoverOpen(true);
            }
        },
        [processedSteps, isRightPanelVisible, setHighlightedStepId]
    );

    const handlePopoverClose = useCallback(() => {
        setIsPopoverOpen(false);
        setSelectedStep(null);
        setSelectedTrackId(null);
    }, []);

    const handlePaneClick = useCallback(
        (event: React.MouseEvent) => {
            if (event.target === event.currentTarget) {
                setHighlightedStepId(null);
                setSelectedTrackId(null);
                handlePopoverClose();
            }
        },
        [setHighlightedStepId, handlePopoverClose]
    );

    if (subwayGraph.stops.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-gray-500 dark:text-gray-400">
                {processedSteps.length > 0 ? "Processing subway graph..." : "No steps to display."}
            </div>
        );
    }

    return (
        <div style={{ height: "100%", width: "100%" }} className="relative">
            <TransformWrapper
                initialScale={1}
                minScale={0.3}
                maxScale={3}
                centerOnInit
                limitToBounds={false}
            >
                {({ zoomIn, zoomOut, resetTransform }) => (
                    <>
                        {/* Zoom Controls */}
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
                            wrapperStyle={{ width: "100%", height: "100%" }}
                            contentStyle={{ width: "100%", height: "100%" }}
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
                                <svg
                                    width={totalWidth}
                                    height={subwayGraph.totalHeight}
                                    style={{ overflow: "visible" }}
                                >
                                    {/* Render tracks */}
                                    <SubwayTracks
                                        tracks={subwayGraph.tracks}
                                        branches={subwayGraph.branches}
                                        laneXPositions={laneXPositions}
                                        selectedTrackId={selectedTrackId}
                                        onTrackClick={handleTrackClick}
                                    />

                                    {/* Render stops */}
                                    {subwayGraph.stops.map(stop => (
                                        <SubwayStopComponent
                                            key={stop.id}
                                            stop={stop}
                                            laneX={laneXPositions[stop.laneIndex] || 0}
                                            isSelected={stop.visualizerStepId === highlightedStepId}
                                            onClick={handleStopClick}
                                        />
                                    ))}
                                </svg>
                            </div>
                        </TransformComponent>

                        <div ref={popoverAnchorRef} style={{ position: "absolute", top: "50%", right: "50px" }} />
                    </>
                )}
            </TransformWrapper>

            {/* Popover */}
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

export default FlowChartPanelV3;
