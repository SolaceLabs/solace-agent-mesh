import React from "react";

import type { VisualizerStep } from "@/lib/types";

import { FlowChartPanelV2 } from "./FlowChart/v2";

interface FlowChartPanelProps {
    processedSteps: VisualizerStep[];
    isRightPanelVisible?: boolean;
    isSidePanelTransitioning?: boolean;
}

const FlowChartPanel: React.FC<FlowChartPanelProps> = (props) => {
    return <FlowChartPanelV2 {...props} />;
};

export { FlowChartPanel };
