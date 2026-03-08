import React, { useState } from "react";
import type { Edge } from "./utils/types";

interface EdgeLayerProps {
    edges: Edge[];
    selectedEdgeId?: string | null;
    onEdgeClick?: (edge: Edge) => void;
}

const EdgeLayer: React.FC<EdgeLayerProps> = ({ edges, selectedEdgeId, onEdgeClick }) => {
    const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);

    // Calculate bezier curve path
    const getBezierPath = (edge: Edge): string => {
        const { sourceX, sourceY, targetX, targetY } = edge;

        // Calculate control points for bezier curve
        const deltaY = targetY - sourceY;
        const controlOffset = Math.min(Math.abs(deltaY) * 0.5, 100);

        const control1X = sourceX;
        const control1Y = sourceY + controlOffset;
        const control2X = targetX;
        const control2Y = targetY - controlOffset;

        return `M ${sourceX} ${sourceY} C ${control1X} ${control1Y}, ${control2X} ${control2Y}, ${targetX} ${targetY}`;
    };

    // Get edge class name based on state
    const getEdgeClassName = (edge: Edge, isHovered: boolean) => {
        const isSelected = edge.id === selectedEdgeId;

        // Priority: Error > Selected > Hover > Default
        if (edge.isError) {
            return "stroke-(--color-error-wMain)";
        }

        if (isSelected) {
            return "stroke-(--color-accent-n2-wMain)";
        }

        if (isHovered) {
            return "stroke-(--color-secondary-w70)";
        }

        return "stroke-(--color-secondary-w40)";
    };

    // Get edge stroke width
    const getEdgeStrokeWidth = (edge: Edge, isHovered: boolean) => {
        const isSelected = edge.id === selectedEdgeId;

        if (edge.isError && isHovered) return 3;
        if (edge.isError) return 2;
        if (isSelected || isHovered) return 3;
        return 2;
    };

    return (
        <svg
            style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                pointerEvents: "none",
                zIndex: 0,
            }}
        >
            <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L9,3 z" fill="#888" />
                </marker>
                <marker id="arrowhead-selected" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L9,3 z" fill="#3b82f6" />
                </marker>
                <marker id="arrowhead-error" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L0,6 L9,3 z" fill="#ef4444" />
                </marker>
            </defs>

            {edges.map(edge => {
                const isHovered = edge.id === hoveredEdgeId;
                const isSelected = edge.id === selectedEdgeId;
                const path = getBezierPath(edge);
                const className = getEdgeClassName(edge, isHovered);
                const strokeWidth = getEdgeStrokeWidth(edge, isHovered);

                // Determine marker
                let markerEnd = "url(#arrowhead)";
                if (edge.isError) {
                    markerEnd = "url(#arrowhead-error)";
                } else if (isSelected) {
                    markerEnd = "url(#arrowhead-selected)";
                }

                return (
                    <g key={edge.id}>
                        {/* Invisible wider path for easier clicking */}
                        <path
                            d={path}
                            fill="none"
                            stroke="transparent"
                            strokeWidth="16"
                            style={{
                                pointerEvents: "stroke",
                                cursor: "pointer",
                            }}
                            onMouseEnter={() => setHoveredEdgeId(edge.id)}
                            onMouseLeave={() => setHoveredEdgeId(null)}
                            onClick={() => onEdgeClick?.(edge)}
                        />

                        {/* Visible edge path */}
                        <path
                            d={path}
                            fill="none"
                            className={className}
                            strokeWidth={strokeWidth}
                            markerEnd={markerEnd}
                            style={{
                                pointerEvents: "none",
                                transition: "all 0.2s ease-in-out",
                            }}
                        />

                        {/* Label */}
                        {edge.label && isHovered && (
                            <text x={(edge.sourceX + edge.targetX) / 2} y={(edge.sourceY + edge.targetY) / 2} fill="#374151" fontSize="12" textAnchor="middle" style={{ pointerEvents: "none" }}>
                                {edge.label}
                            </text>
                        )}
                    </g>
                );
            })}
        </svg>
    );
};

export default EdgeLayer;
