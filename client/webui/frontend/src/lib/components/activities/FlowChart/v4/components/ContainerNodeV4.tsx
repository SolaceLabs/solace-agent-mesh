import React from "react";
import type { ContainerNode, Stop } from "../utils/types";
import StopNodeV4 from "./StopNodeV4";

interface ContainerNodeV4Props {
    container: ContainerNode;
    laneX: number; // X position of the track lane
    isSelected?: boolean;
    onClick?: (container: ContainerNode) => void;
}

const ContainerNodeV4: React.FC<ContainerNodeV4Props> = ({
    container,
    laneX,
    isSelected = false,
    onClick,
}) => {
    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onClick?.(container);
    };

    const renderStop = (stop: Stop) => (
        <StopNodeV4
            key={stop.id}
            stop={stop}
            laneX={laneX}
            containerX={container.x}
        />
    );

    const renderChild = (child: ContainerNode) => (
        <ContainerNodeV4
            key={child.id}
            container={child}
            laneX={laneX}
            onClick={onClick}
        />
    );

    const isWorkflow = container.type === 'workflow-group';

    // Container styles
    const containerClasses = isWorkflow
        ? "border-2 border-dashed border-purple-400 dark:border-purple-500 bg-purple-50/30 dark:bg-purple-900/10 rounded-lg"
        : "border-2 border-blue-700 dark:border-blue-400 bg-white dark:bg-gray-800 rounded-md shadow-md";

    const headerClasses = isWorkflow
        ? "bg-purple-100 dark:bg-purple-900/30 border-b-2 border-dashed border-purple-300 dark:border-purple-600"
        : "bg-gradient-to-r from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-800/30 border-b border-gray-200 dark:border-gray-700";

    return (
        <div
            className={`
                ${containerClasses}
                transition-all duration-200 ease-in-out
                hover:shadow-xl
                ${isSelected ? "ring-4 ring-blue-500 ring-opacity-50" : ""}
            `}
            style={{
                position: "absolute",
                left: container.x,
                top: container.y,
                width: container.width,
                height: container.height,
                cursor: "pointer",
            }}
            onClick={handleClick}
        >
            {/* Header */}
            <div
                className={`
                    ${headerClasses}
                    px-4 py-2
                    flex items-center justify-between
                    rounded-t-md
                    ${isWorkflow ? "rounded-t-lg" : ""}
                `}
                style={{
                    height: isWorkflow ? "40px" : "50px",
                }}
            >
                <span className="font-semibold text-sm text-gray-900 dark:text-gray-100">
                    {container.label}
                </span>
                {isWorkflow && (
                    <span className="text-xs text-purple-600 dark:text-purple-400 font-medium">
                        Workflow
                    </span>
                )}
            </div>

            {/* Content Area */}
            <div className="relative" style={{ height: container.height - (isWorkflow ? 40 : 50) }}>
                {/* Track line running through container */}
                <svg
                    className="absolute inset-0 pointer-events-none"
                    style={{
                        width: "100%",
                        height: "100%",
                    }}
                >
                    {/* Vertical track line */}
                    <line
                        x1={laneX - container.x}
                        y1={0}
                        x2={laneX - container.x}
                        y2={container.height - (isWorkflow ? 40 : 50)}
                        stroke={container.trackColor}
                        strokeWidth={3}
                        opacity={0.6}
                    />
                </svg>

                {/* Stops and Children */}
                <div className="p-4 flex flex-col gap-3 items-center relative">
                    {/* Render stops */}
                    {container.stops.map(renderStop)}

                    {/* Render child containers */}
                    {container.children.map(renderChild)}

                    {/* Render parallel branches */}
                    {container.parallelBranches && (
                        <div className="flex gap-4 w-full justify-center">
                            {container.parallelBranches.map((branch, branchIdx) => (
                                <div key={branchIdx} className="flex flex-col gap-3">
                                    {branch.map(renderChild)}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default ContainerNodeV4;
