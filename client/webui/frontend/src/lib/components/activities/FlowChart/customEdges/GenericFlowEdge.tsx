import React, { useState } from "react";

import { type EdgeProps, getBezierPath } from "@xyflow/react";

export interface AnimatedEdgeData {
    visualizerStepId: string;
    isAnimated?: boolean;
    animationType?: "request" | "response" | "static";
    isSelected?: boolean;
    isError?: boolean;
    errorMessage?: string;
}

const GenericFlowEdge: React.FC<EdgeProps> = ({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, style = {}, markerEnd, data }) => {
    const [isHovered, setIsHovered] = useState(false);

    const [edgePath] = getBezierPath({
        sourceX,
        sourceY,
        sourcePosition,
        targetX,
        targetY,
        targetPosition,
    });

    const getEdgeStyle = () => {
        const baseStyle = {
            strokeWidth: isHovered ? 3 : 2,
            stroke: "var(--color-muted-foreground)",
            ...style,
        };

        const edgeData = data as unknown as AnimatedEdgeData;

        // Priority: Error > Selected > Animated > Hover > Default
        if (edgeData?.isError) {
            return {
                ...baseStyle,
                stroke: isHovered ? "var(--color-error-wMain)" : "var(--color-error-w70)",
                strokeWidth: isHovered ? 3 : 2,
            };
        }

        if (edgeData?.isSelected) {
            return {
                ...baseStyle,
                stroke: "#3b82f6", // same as VisualizerStepCard
                strokeWidth: 3,
            };
        }

        // Enhanced logic: handle both animation and hover states
        if (edgeData?.isAnimated) {
            return {
                ...baseStyle,
                stroke: isHovered ? "#1d4ed8" : "#3b82f6",
                strokeWidth: isHovered ? 4 : 3,
            };
        }

        // For non-animated edges, change color on hover
        if (isHovered) {
            return {
                ...baseStyle,
                stroke: "var(--edge-hover-color)",
            };
        }

        return baseStyle;
    };

    const handleMouseEnter = () => setIsHovered(true);
    const handleMouseLeave = () => setIsHovered(false);

    return (
        <>
            {/* Invisible wider path for easier clicking */}
            <path
                id={`${id}-interaction`}
                style={{
                    strokeWidth: 16,
                    stroke: "transparent",
                    fill: "none",
                    cursor: "pointer",
                }}
                className="react-flow__edge-interaction"
                d={edgePath}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
            />
            {/* Visible edge path */}
            <path
                id={id}
                style={{
                    ...getEdgeStyle(),
                    cursor: "pointer",
                    transition: "all 0.2s ease-in-out",
                }}
                className="react-flow__edge-path"
                d={edgePath}
                markerEnd={markerEnd}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
            />
        </>
    );
};

export default GenericFlowEdge;
