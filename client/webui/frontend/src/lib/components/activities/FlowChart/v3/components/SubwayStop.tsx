import React from "react";
import type { SubwayStop as SubwayStopType } from "../utils/types";

interface SubwayStopProps {
    stop: SubwayStopType;
    laneX: number; // X position of this lane
    isSelected?: boolean;
    onClick?: (stop: SubwayStopType) => void;
}

const SubwayStop: React.FC<SubwayStopProps> = ({ stop, laneX, isSelected, onClick }) => {
    const getStopColor = () => {
        if (stop.type === 'user') return '#9333ea'; // Purple
        if (stop.type === 'llm') return '#0d9488'; // Teal
        if (stop.type === 'tool') return '#0891b2'; // Cyan
        return stop.trackColor || '#3b82f6'; // Default blue
    };

    const getStatusColor = () => {
        switch (stop.status) {
            case 'completed': return '#10b981'; // Green
            case 'in-progress': return '#3b82f6'; // Blue
            case 'error': return '#ef4444'; // Red
            default: return getStopColor();
        }
    };

    const stopColor = getStatusColor();
    const labelX = laneX + 200; // Label area starts 200px to the right of lanes

    // Different icon for conditional nodes
    if (stop.type === 'conditional') {
        return (
            <>
                {/* Diamond for conditional */}
                <g onClick={() => onClick?.(stop)} style={{ cursor: 'pointer' }}>
                    <rect
                        x={laneX - 6}
                        y={stop.y - 6}
                        width="12"
                        height="12"
                        fill={stopColor}
                        stroke={isSelected ? '#3b82f6' : stopColor}
                        strokeWidth={isSelected ? 3 : 1.5}
                        transform={`rotate(45 ${laneX} ${stop.y})`}
                    />
                    <text
                        x={labelX}
                        y={stop.y + 5}
                        fill="currentColor"
                        fontSize="14"
                        fontWeight="600"
                        className="dark:fill-gray-200 fill-gray-800"
                    >
                        {stop.label}
                    </text>
                    {stop.conditionResult !== undefined && (
                        <text
                            x={labelX + 120}
                            y={stop.y + 5}
                            fill="#6b7280"
                            fontSize="11"
                            className="dark:fill-gray-400"
                        >
                            {stop.conditionResult ? '✓ True' : '✗ False'}
                        </text>
                    )}
                </g>
            </>
        );
    }

    // Workflow start/end use different symbols
    const isWorkflowBoundary = stop.type === 'workflow-start' || stop.type === 'workflow-end';

    return (
        <>
            {/* Stop circle */}
            <g onClick={() => onClick?.(stop)} style={{ cursor: 'pointer' }}>
                <circle
                    cx={laneX}
                    cy={stop.y}
                    r={isWorkflowBoundary ? 10 : 8}
                    fill={stopColor}
                    stroke={isSelected ? '#3b82f6' : '#fff'}
                    strokeWidth={isSelected ? 3 : 2}
                />

                {/* Outer ring for workflow boundaries */}
                {isWorkflowBoundary && (
                    <circle
                        cx={laneX}
                        cy={stop.y}
                        r={13}
                        fill="none"
                        stroke={stopColor}
                        strokeWidth={2}
                    />
                )}

                {/* Label */}
                <text
                    x={labelX}
                    y={stop.y + 5}
                    fill="currentColor"
                    fontSize="14"
                    fontWeight={stop.type === 'agent' || stop.type === 'user' ? '600' : '400'}
                    className="dark:fill-gray-200 fill-gray-800"
                >
                    {stop.label}
                </text>

                {/* Type indicator */}
                {(stop.type === 'tool' || stop.type === 'llm') && (
                    <text
                        x={labelX}
                        y={stop.y + 18}
                        fill="#6b7280"
                        fontSize="11"
                        className="dark:fill-gray-400"
                    >
                        {stop.type === 'llm' ? '🤖 LLM' : '🔧 Tool'}
                    </text>
                )}
            </g>
        </>
    );
};

export default SubwayStop;
