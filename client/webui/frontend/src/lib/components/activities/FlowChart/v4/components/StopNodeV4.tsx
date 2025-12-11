import React from "react";
import type { Stop } from "../utils/types";

interface StopNodeV4Props {
    stop: Stop;
    laneX: number; // Absolute X position of the lane
    containerX: number; // Absolute X position of the container
    isSelected?: boolean;
    onClick?: (stop: Stop) => void;
}

const StopNodeV4: React.FC<StopNodeV4Props> = ({
    stop,
    laneX,
    containerX,
    isSelected = false,
    onClick,
}) => {
    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onClick?.(stop);
    };

    // Get stop styling based on type
    const getStopStyle = () => {
        switch (stop.type) {
            case 'user':
                return {
                    borderColor: 'border-purple-600 dark:border-purple-400',
                    bgColor: 'bg-purple-50 dark:bg-purple-900/20',
                    textColor: 'text-purple-900 dark:text-purple-100',
                    circleColor: '#9333ea', // purple-600
                };
            case 'llm':
                return {
                    borderColor: 'border-teal-600 dark:border-teal-400',
                    bgColor: 'bg-teal-50 dark:bg-teal-900/20',
                    textColor: 'text-teal-900 dark:text-teal-100',
                    circleColor: '#0d9488', // teal-600
                };
            case 'tool':
                return {
                    borderColor: 'border-cyan-600 dark:border-cyan-400',
                    bgColor: 'bg-cyan-50 dark:bg-cyan-900/20',
                    textColor: 'text-cyan-900 dark:text-cyan-100',
                    circleColor: '#0891b2', // cyan-600
                };
            case 'conditional':
                return {
                    borderColor: 'border-amber-500 dark:border-amber-400',
                    bgColor: 'bg-amber-50 dark:bg-amber-900/20',
                    textColor: 'text-amber-900 dark:text-amber-100',
                    circleColor: '#f59e0b', // amber-500
                };
            case 'agent':
                return {
                    borderColor: 'border-blue-600 dark:border-blue-400',
                    bgColor: 'bg-blue-50 dark:bg-blue-900/20',
                    textColor: 'text-blue-900 dark:text-blue-100',
                    circleColor: '#2563eb', // blue-600
                };
            default:
                return {
                    borderColor: 'border-gray-400 dark:border-gray-500',
                    bgColor: 'bg-gray-50 dark:bg-gray-800',
                    textColor: 'text-gray-900 dark:text-gray-100',
                    circleColor: '#6b7280', // gray-500
                };
        }
    };

    const style = getStopStyle();

    // Status indicator color
    const getStatusColor = () => {
        switch (stop.status) {
            case 'completed':
                return 'bg-green-500';
            case 'in-progress':
                return 'bg-blue-500 animate-pulse';
            case 'error':
                return 'bg-red-500';
            default:
                return 'bg-gray-400';
        }
    };

    // Calculate position relative to container
    const relativeX = laneX - containerX;

    return (
        <div
            className="relative flex items-center justify-center"
            style={{
                width: "100%",
                minHeight: "40px",
            }}
        >
            {/* Stop circle on the track */}
            <svg
                className="absolute pointer-events-none"
                style={{
                    left: relativeX - 8,
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: 16,
                    height: 16,
                }}
            >
                <circle
                    cx={8}
                    cy={8}
                    r={stop.type === 'conditional' ? 6 : 7}
                    fill="white"
                    stroke={style.circleColor}
                    strokeWidth={stop.type === 'conditional' ? 3 : 2.5}
                />
                {stop.type === 'conditional' && (
                    <path
                        d="M 8 2 L 14 8 L 8 14 L 2 8 Z"
                        fill="none"
                        stroke={style.circleColor}
                        strokeWidth={2}
                    />
                )}
            </svg>

            {/* Stop label card */}
            <div
                className={`
                    ${style.borderColor} ${style.bgColor}
                    border rounded-md px-3 py-2
                    min-w-[120px] max-w-[200px]
                    transition-all duration-200 ease-in-out
                    hover:shadow-md
                    ${isSelected ? "ring-2 ring-blue-500" : ""}
                `}
                style={{
                    cursor: "pointer",
                    marginLeft: relativeX + 16, // Position to the right of the circle
                }}
                onClick={handleClick}
            >
                <div className="flex items-center justify-between gap-2">
                    <span className={`text-xs font-medium ${style.textColor}`}>
                        {stop.label}
                    </span>
                    {stop.status && (
                        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
                    )}
                </div>
                {stop.condition && (
                    <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                        {stop.condition}
                    </div>
                )}
            </div>
        </div>
    );
};

export default StopNodeV4;
