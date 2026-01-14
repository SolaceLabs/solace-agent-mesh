import React from "react";
import type { Edge } from "../utils/types";

interface EdgeLayerProps {
    edges: Edge[];
    width: number;
    height: number;
}

/**
 * EdgeLayer - SVG layer for rendering orthogonal edges between nodes
 */
const EdgeLayer: React.FC<EdgeLayerProps> = ({ edges, width, height }) => {
    /**
     * Generate SVG path for an edge (orthogonal with 90° bends)
     */
    const generatePath = (edge: Edge): string => {
        const { sourceX, sourceY, targetX, targetY, isStraight } = edge;

        // Straight line for pill -> target edges or when source/target are vertically aligned
        if (isStraight || Math.abs(sourceX - targetX) < 1) {
            return `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
        }

        // Orthogonal path with 90° bends
        // Go down from source, then horizontal, then down to target
        const midY = (sourceY + targetY) / 2;
        return `M ${sourceX} ${sourceY} L ${sourceX} ${midY} L ${targetX} ${midY} L ${targetX} ${targetY}`;
    };

    return (
        <svg
            className="pointer-events-none absolute left-0 top-0"
            width={width}
            height={height}
            style={{ overflow: "visible" }}
        >
            {/* Arrow marker definition */}
            <defs>
                <marker
                    id="arrowhead"
                    markerWidth="8"
                    markerHeight="8"
                    refX="6"
                    refY="4"
                    orient="auto"
                    markerUnits="userSpaceOnUse"
                >
                    <path d="M 0 0 L 8 4 L 0 8 z" className="fill-gray-400 dark:fill-gray-500" />
                </marker>
            </defs>

            {/* Render each edge */}
            {edges.map(edge => (
                <g key={edge.id}>
                    {/* Main edge path */}
                    <path
                        d={generatePath(edge)}
                        className="fill-none stroke-gray-400 dark:stroke-gray-500"
                        strokeWidth={2}
                        markerEnd="url(#arrowhead)"
                    />

                    {/* Edge label (if present) */}
                    {edge.label && (
                        <text
                            x={(edge.sourceX + edge.targetX) / 2}
                            y={(edge.sourceY + edge.targetY) / 2 - 8}
                            textAnchor="middle"
                            className="fill-gray-500 text-xs dark:fill-gray-400"
                        >
                            {edge.label}
                        </text>
                    )}
                </g>
            ))}
        </svg>
    );
};

export default EdgeLayer;
