import React from "react";
import type { LayoutNode } from "../utils/types";

interface LoopNodeV2Props {
    node: LayoutNode;
    isSelected?: boolean;
    onClick?: (node: LayoutNode) => void;
}

const LoopNodeV2: React.FC<LoopNodeV2Props> = ({ node, isSelected, onClick }) => {
    const getStatusColor = () => {
        switch (node.data.status) {
            case "completed":
                return "bg-teal-100 border-teal-500 dark:bg-teal-900/30 dark:border-teal-500";
            case "in-progress":
                return "bg-blue-100 border-blue-500 dark:bg-blue-900/30 dark:border-blue-500";
            case "error":
                return "bg-red-100 border-red-500 dark:bg-red-900/30 dark:border-red-500";
            default:
                return "bg-gray-100 border-gray-400 dark:bg-gray-800 dark:border-gray-600";
        }
    };

    const currentIteration = node.data.currentIteration ?? 0;
    const maxIterations = node.data.maxIterations ?? 100;

    return (
        <div
            className="relative flex items-center justify-center cursor-pointer"
            style={{ width: `${node.width}px`, height: `${node.height}px` }}
            onClick={(e) => {
                e.stopPropagation();
                onClick?.(node);
            }}
            title={node.data.description || `Loop: ${node.data.condition || 'while condition'} (max ${maxIterations})`}
        >
            {/* Stadium/Pill shape with loop indicator */}
            <div
                className={`relative w-20 h-10 rounded-full border-2 shadow-sm transition-all duration-200 ease-in-out hover:scale-105 hover:shadow-md flex items-center justify-center ${getStatusColor()} ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                }`}
            >
                {/* Loop Arrow Icon */}
                <svg
                    className="absolute -top-1 -right-1 w-4 h-4 text-teal-600 dark:text-teal-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                </svg>

                {/* Content */}
                <div className="flex flex-col items-center justify-center text-center pointer-events-none">
                    <div className="text-[10px] font-bold text-gray-800 dark:text-gray-200">
                        {node.data.label}
                    </div>
                </div>
            </div>

            {/* Iteration Counter (if in progress) */}
            {node.data.status === 'in-progress' && currentIteration > 0 && (
                <div className="absolute bottom-[-18px] left-1/2 transform -translate-x-1/2 text-[9px] font-medium text-gray-600 dark:text-gray-300 bg-white/80 dark:bg-gray-900/80 px-1.5 py-0.5 rounded">
                    Iteration {currentIteration}
                </div>
            )}
        </div>
    );
};

export default LoopNodeV2;
