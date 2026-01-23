import type { FC } from "react";
import type { Edge } from "../utils/types";

interface EdgeLayerProps {
    edges: Edge[];
    width: number;
    height: number;
}

/**
 * EdgeLayer - SVG layer for rendering bezier curve edges between nodes
 */
const EdgeLayer: FC<EdgeLayerProps> = ({ edges, width, height }) => {
    /**
     * Generate SVG path for an edge (bezier curve or straight line)
     * Ends with a short vertical segment so arrowhead always points down
     */
    const generatePath = (edge: Edge): string => {
        const { sourceX, sourceY, targetX, targetY, isStraight } = edge;

        // Straight line for pill -> target edges
        if (isStraight) {
            return `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
        }

        // Add a short vertical landing segment so arrow always points down
        const landingLength = 12;
        const landingY = targetY - landingLength;

        // Calculate control points for smooth bezier curve to the landing point
        const controlOffset = Math.min(Math.abs(landingY - sourceY) * 0.5, 40);

        // Cubic bezier to landing point, then straight down to target
        return `M ${sourceX} ${sourceY} C ${sourceX} ${sourceY + controlOffset}, ${targetX} ${landingY - controlOffset}, ${targetX} ${landingY} L ${targetX} ${targetY}`;
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
                    markerWidth="12"
                    markerHeight="12"
                    refX="9"
                    refY="6"
                    orient="auto"
                    markerUnits="userSpaceOnUse"
                >
                    <path d="M 0 0 L 12 6 L 0 12 z" className="fill-(--color-secondary-w40) dark:fill-(--color-secondary-w80)" />
                </marker>
            </defs>

            {/* Render each edge */}
            {edges.map(edge => {
                // Check if this edge connects to a condition pill (target starts with __condition_)
                const isConditionPillEdge = edge.target.startsWith('__condition_');

                return (
                    <g key={edge.id}>
                        {/* Main edge path */}
                        <path
                            d={generatePath(edge)}
                            className="fill-none stroke-(--color-secondary-w40) dark:stroke-(--color-secondary-w80)"
                            strokeWidth={2}
                            markerEnd={isConditionPillEdge ? undefined : "url(#arrowhead)"}
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
                );
            })}
        </svg>
    );
};

export default EdgeLayer;
